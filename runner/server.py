"""
PeakCV code runner: a small, Piston-compatible code execution service.

Railway can't run Piston (it needs privileged Docker), so this service runs on Railway as a separate container
and the backend talks to it exactly as it would to Piston (PISTON_URL + PISTON_TOKEN).

API (the subset of Piston's v2 API the backend uses):
    GET  /                    health check, no token needed
    GET  /api/v2/runtimes     languages this container can run
    POST /api/v2/execute      {language, files: [{name, content}], stdin, run_timeout, compile_timeout}
                              -> {run: {stdout, stderr, code, signal}, compile?: {stdout, stderr, code}}

Safety (this is a separate container with no database, volume or secrets except its token):
    - every request needs "Authorization: Bearer <RUNNER_TOKEN>" (the service refuses to start without one,
      unless RUNNER_ALLOW_NO_TOKEN=1 for local testing)
    - submitted code runs as an unprivileged "sandbox" user, never as the server's user
    - limits per run: wall-clock and CPU time, number of processes (MAX_PROCS, off by default), file size, open files, memory where the
      runtime allows it, and output size
    - at most MAX_CONCURRENT runs at once; request bodies are capped
"""
import hmac
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.getenv('RUNNER_TOKEN', '').strip()
ALLOW_NO_TOKEN = os.getenv('RUNNER_ALLOW_NO_TOKEN') == '1'
MAX_CONCURRENT = int(os.getenv('MAX_CONCURRENT', '4'))
MAX_BODY = 512 * 1024            # request body
MAX_OUTPUT = 256 * 1024          # stdout / stderr returned
MAX_FILE = 16 * 1024 * 1024      # largest file a program may write
# Process cap for submitted programs. Linux counts it per user across the whole host, so on shared hosts
# (Railway) any value can already be used up by others; 0 turns it off (the timeout still kills the group).
MAX_PROCS = int(os.getenv('MAX_PROCS', '0'))
MEMORY = 512 * 1024 * 1024       # address-space limit for C, C++ and Python
GO_CACHE = os.getenv('GOCACHE_DIR', '/var/cache/go-build')
IS_POSIX = os.name == 'posix'
EXE = 'main.exe' if os.name == 'nt' else 'main'

# Each language: default file name, optional compile command, run command, whether an address-space limit
# is safe (the JVM, Node and Go reserve large virtual ranges, so they rely on the other limits), extra seconds.
LANGS = {
    'python': {'file': 'main.py', 'run': [sys.executable if not IS_POSIX else 'python3', '-I', '-X', 'utf8', '{file}'],
               'tool': 'python3' if IS_POSIX else sys.executable, 'limit_memory': True, 'aliases': ['py', 'python3']},
    'javascript': {'file': 'main.js', 'run': ['node', '{file}'], 'tool': 'node', 'limit_memory': False,
                   'aliases': ['js', 'node']},
    'c': {'file': 'main.c', 'compile': ['gcc', '-std=c11', '-O2', '{file}', '-o', EXE, '-lm'], 'run': ['./' + EXE],
          'tool': 'gcc', 'limit_memory': True, 'aliases': []},
    'c++': {'file': 'main.cpp', 'compile': ['g++', '-std=c++17', '-O2', '{file}', '-o', EXE], 'run': ['./' + EXE],
            'tool': 'g++', 'limit_memory': True, 'aliases': ['cpp']},
    'java': {'file': 'Main.java', 'run': ['java', '-Xss64m', '-Xmx256m', '-XX:+UseSerialGC', '-XX:TieredStopAtLevel=1',
                                          '{file}'],
             'tool': 'java', 'limit_memory': False, 'extra_time': 5, 'aliases': []},
    'go': {'file': 'main.go', 'compile': ['go', 'build', '-o', EXE, '{file}'], 'run': ['./' + EXE], 'tool': 'go',
           'limit_memory': False, 'aliases': ['golang']},
}
ALIASES = {alias: name for name, spec in LANGS.items() for alias in [name] + spec['aliases']}
SAFE_NAME = re.compile(r'^[A-Za-z0-9_.-]{1,64}$')
slots = threading.BoundedSemaphore(MAX_CONCURRENT)


def available():
    return [name for name, spec in LANGS.items() if shutil.which(spec['tool'])]


def _sandbox_ids():
    if not IS_POSIX or os.geteuid() != 0:
        return None  # local testing without root: no user switch
    import pwd
    try:
        entry = pwd.getpwnam('sandbox')
        return entry.pw_uid, entry.pw_gid
    except KeyError:
        return None


SANDBOX = _sandbox_ids()


def _limits(seconds, limit_memory, limit_procs):
    """Runs in the child just before exec: drop privileges, then cap resources."""
    def apply():
        import resource
        os.setsid()
        if SANDBOX:
            os.setgroups([])
            os.setgid(SANDBOX[1])
            os.setuid(SANDBOX[0])
        resource.setrlimit(resource.RLIMIT_CPU, (seconds + 1, seconds + 2))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE, MAX_FILE))
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
        if limit_procs and MAX_PROCS > 0:
            resource.setrlimit(resource.RLIMIT_NPROC, (MAX_PROCS, MAX_PROCS))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if limit_memory:
            resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))
    return apply if IS_POSIX else None


def _run(cmd, workdir, stdin, seconds, limit_memory, env, limit_procs=True):
    """Run one command with limits. Output goes to files (so the file-size limit also caps it)."""
    out_path, err_path = os.path.join(workdir, '.stdout'), os.path.join(workdir, '.stderr')
    with open(out_path, 'wb') as out, open(err_path, 'wb') as err:
        if SANDBOX:
            for path in (out_path, err_path):
                os.chown(path, *SANDBOX)
        proc = subprocess.Popen(cmd, cwd=workdir, stdin=subprocess.PIPE, stdout=out, stderr=err, env=env,
                                preexec_fn=_limits(seconds, limit_memory, limit_procs))
        sig = None
        try:
            proc.communicate(stdin.encode('utf-8', 'replace'), timeout=seconds)
        except subprocess.TimeoutExpired:
            sig = 'SIGKILL'
            try:
                os.killpg(proc.pid, signal.SIGKILL) if IS_POSIX else proc.kill()
            except (ProcessLookupError, PermissionError):
                proc.kill()
            proc.wait()
    code = proc.returncode
    if code is not None and code < 0:
        name = signal.Signals(-code).name
        # Running out of CPU time is a time-limit failure, reported the way Piston reports it.
        sig = 'SIGKILL' if name in ('SIGKILL', 'SIGXCPU') else name
        code = None
    read = lambda p: open(p, 'rb').read(MAX_OUTPUT).decode('utf-8', 'replace')
    return {'stdout': read(out_path), 'stderr': read(err_path), 'code': code, 'signal': sig,
            'output': (read(out_path) + read(err_path))[:MAX_OUTPUT]}


def execute(body):
    name = ALIASES.get(str(body.get('language', '')).lower())
    if not name or name not in available():
        return 400, {'message': f"Language '{body.get('language')}' is not available on this runner."}
    spec = LANGS[name]
    files = body.get('files') or []
    if not files or not isinstance(files[0], dict) or not isinstance(files[0].get('content'), str):
        return 400, {'message': 'files[0].content is required.'}
    filename = files[0].get('name') or spec['file']
    if not SAFE_NAME.match(filename) or filename.startswith('.'):
        filename = spec['file']
    stdin = body.get('stdin') if isinstance(body.get('stdin'), str) else ''
    run_seconds = min(max(int(body.get('run_timeout') or 5000), 1000), 15000) / 1000 + spec.get('extra_time', 0)
    compile_seconds = min(max(int(body.get('compile_timeout') or 20000), 1000), 60000) / 1000

    workdir = tempfile.mkdtemp(prefix='run-')
    try:
        with open(os.path.join(workdir, filename), 'w', encoding='utf-8') as f:
            f.write(files[0]['content'])
        if SANDBOX:
            for path in [workdir] + [os.path.join(workdir, p) for p in os.listdir(workdir)]:
                os.chown(path, *SANDBOX)
            os.chmod(workdir, 0o700)
        env = {'PATH': os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin'), 'HOME': workdir, 'LANG': 'C.UTF-8',
               'GOCACHE': GO_CACHE, 'GOPATH': os.path.join(workdir, 'gopath'), 'GO111MODULE': 'off',
               'SYSTEMROOT': os.environ.get('SYSTEMROOT', ''), 'TEMP': workdir, 'TMP': workdir, 'TMPDIR': workdir}
        result = {}
        if spec.get('compile'):
            cmd = [part.replace('{file}', filename) for part in spec['compile']]
            # The compiler is trusted and starts helper processes (cc1plus, go tools), so no process cap here.
            compiled = _run(cmd, workdir, '', int(compile_seconds), False, env, limit_procs=False)
            result['compile'] = compiled
            if compiled['code'] != 0:
                return 200, result
        cmd = [part.replace('{file}', filename) for part in spec['run']]
        if cmd[0].startswith('./'):
            cmd[0] = os.path.join(workdir, cmd[0][2:])
        result['run'] = _run(cmd, workdir, stdin, int(round(run_seconds)) or 1, spec['limit_memory'], env)
        result['language'] = name
        return 200, result
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    server_version = 'PeakCVRunner/1.0'

    def _send(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorised(self):
        if not TOKEN:
            return ALLOW_NO_TOKEN
        given = self.headers.get('Authorization', '')
        return hmac.compare_digest(given.encode(), f'Bearer {TOKEN}'.encode())

    def do_GET(self):
        if self.path in ('/', '/health'):
            return self._send(200, {'status': 'ok', 'languages': available()})
        if not self._authorised():
            return self._send(401, {'message': 'Unauthorized'})
        if self.path.rstrip('/') == '/api/v2/runtimes':
            return self._send(200, [{'language': n, 'version': 'system', 'aliases': LANGS[n]['aliases']}
                                    for n in available()])
        self._send(404, {'message': 'Not found'})

    def do_POST(self):
        if not self._authorised():
            return self._send(401, {'message': 'Unauthorized'})
        if self.path.rstrip('/') != '/api/v2/execute':
            return self._send(404, {'message': 'Not found'})
        length = int(self.headers.get('Content-Length') or 0)
        if length <= 0 or length > MAX_BODY:
            return self._send(413, {'message': 'Request too large.'})
        try:
            body = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            return self._send(400, {'message': 'Invalid JSON.'})
        if not slots.acquire(timeout=30):
            return self._send(503, {'message': 'The runner is busy, try again.'})
        try:
            status, payload = execute(body)
        except Exception as e:  # never leak a traceback to the caller
            print('execute failed:', repr(e), file=sys.stderr)
            status, payload = 500, {'message': 'The runner failed to run this code.'}
        finally:
            slots.release()
        self._send(status, payload)

    def log_message(self, fmt, *args):
        print('%s - %s' % (self.address_string(), fmt % args), flush=True)


class Server(ThreadingHTTPServer):
    daemon_threads = True


def main():
    if not TOKEN and not ALLOW_NO_TOKEN:
        sys.exit('RUNNER_TOKEN is not set; refusing to start without it.')
    port = int(os.getenv('PORT', '8080'))
    # Railway's private network is IPv6; '::' also accepts IPv4 on Linux (dual stack).
    import socket
    if socket.has_ipv6 and IS_POSIX:
        Server.address_family = socket.AF_INET6
        server = Server(('::', port), Handler)
    else:
        server = Server(('0.0.0.0', port), Handler)
    print(f'runner listening on port {port}; languages: {", ".join(available())}; '
          f'sandbox user: {"yes" if SANDBOX else "no"}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
