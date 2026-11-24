"""
Runs candidate code. Two backends, picked with CODE_EXECUTOR in .env:

- piston: a self-hosted Piston container (Docker). Sandboxed; use this whenever it is available.
- local:  a plain subprocess with a timeout (C, C++ and Go are compiled first). NOT a sandbox, so it
          only runs when DEBUG is on and ALLOW_LOCAL_EXECUTOR=1. Meant for development on your own machine.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

import requests
from django.conf import settings

MAX_OUTPUT = 256 * 1024
TIME_LIMIT_SEC = 5


class ExecutorError(Exception):
    pass


@dataclass
class ExecResult:
    stdout: str
    stderr: str
    timed_out: bool
    exit_code: int
    compile_error: bool = False


def _exe_name():
    return 'main.exe' if os.name == 'nt' else 'main'


class _CompileError(Exception):
    pass


class LocalExecutor:
    FILES = {'python': 'main.py', 'javascript': 'main.js', 'c': 'main.c', 'cpp': 'main.cpp',
             'java': 'Main.java', 'go': 'main.go'}
    TOOLS = {'javascript': 'node', 'c': 'gcc', 'cpp': 'g++', 'java': 'java', 'go': 'go'}
    INSTALL = {'javascript': 'Node.js', 'c': 'gcc (MinGW on Windows)', 'cpp': 'g++ (MinGW on Windows)',
               'java': 'a JDK (Java 11 or newer)', 'go': 'Go'}
    COMPILE_TIMEOUT = 30
    # Deep recursion needs more than the 1 MB default stack on Windows.
    STACK = ['-Wl,--stack,268435456'] if os.name == 'nt' else []

    def __init__(self):
        if not (settings.DEBUG and os.getenv('ALLOW_LOCAL_EXECUTOR') == '1'):
            raise ExecutorError("Local code execution is disabled. Set up Piston, or set "
                                "ALLOW_LOCAL_EXECUTOR=1 for local development.")

    @classmethod
    def available(cls):
        """{language: None if it can run here, else what needs installing}."""
        return {lang: (None if lang == 'python' or shutil.which(cls.TOOLS[lang]) else cls.INSTALL[lang])
                for lang in cls.FILES}

    def _tool(self, language):
        tool = shutil.which(self.TOOLS[language])
        if not tool:
            raise ExecutorError(f"{self.INSTALL[language]} is not installed on this computer, "
                                "so this language can't run here.")
        return tool

    @staticmethod
    def _env(compile_step=False):
        # Keep the environment minimal so candidate code can't read our secrets (.env values).
        keys = ['PATH', 'SYSTEMROOT']
        if compile_step:
            # Compilers need temp and cache folders. They never run the candidate's code.
            keys += ['TEMP', 'TMP', 'HOME', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'GOROOT', 'GOPATH', 'GOCACHE']
        env = {k: os.environ[k] for k in keys if k in os.environ}
        env['PYTHONIOENCODING'] = 'utf-8'
        return env

    def _compile(self, language, path, tmp):
        exe = os.path.join(tmp, _exe_name())
        src = os.path.basename(path)
        if language == 'c':
            cmd = [self._tool('c'), '-std=c11', '-O2', src, '-o', exe, '-lm'] + self.STACK
        elif language == 'cpp':
            cmd = [self._tool('cpp'), '-std=c++17', '-O2', src, '-o', exe] + self.STACK
        else:
            cmd = [self._tool('go'), 'build', '-o', exe, src]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                                  timeout=self.COMPILE_TIMEOUT, cwd=tmp, env=self._env(compile_step=True))
        except subprocess.TimeoutExpired:
            raise _CompileError("Compilation took too long.")
        if proc.returncode != 0:
            out = (proc.stderr + proc.stdout).replace(tmp + os.sep, '').replace(tmp, '')
            raise _CompileError("Compilation failed:\n" + out.strip())
        return exe

    def _command(self, language, path, tmp):
        if language == 'python':
            return [sys.executable, '-I', '-X', 'utf8', path], TIME_LIMIT_SEC
        if language == 'javascript':
            return [self._tool('javascript'), path], TIME_LIMIT_SEC
        if language == 'java':
            # Source-file mode compiles and runs in one step, so allow for the compile time.
            return [self._tool('java'), '-Xss256m', os.path.basename(path)], TIME_LIMIT_SEC + 5
        return [self._compile(language, path, tmp)], TIME_LIMIT_SEC

    def execute(self, language, source, stdin):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, self.FILES[language])
            with open(path, 'w', encoding='utf-8') as f:
                f.write(source)
            try:
                cmd, limit = self._command(language, path, tmp)
            except _CompileError as e:
                return ExecResult('', str(e)[:MAX_OUTPUT], False, 1, compile_error=True)
            try:
                proc = subprocess.run(
                    cmd, input=stdin, capture_output=True, text=True,
                    encoding='utf-8', errors='replace', timeout=limit, cwd=tmp, env=self._env(),
                )
                stderr = proc.stderr.replace(tmp + os.sep, '').replace(tmp, '')
                return ExecResult(proc.stdout[:MAX_OUTPUT], stderr[:MAX_OUTPUT], False, proc.returncode)
            except subprocess.TimeoutExpired as e:
                out = e.stdout.decode('utf-8', 'replace') if isinstance(e.stdout, bytes) else (e.stdout or '')
                return ExecResult(out[:MAX_OUTPUT], '', True, -1)


class PistonExecutor:
    LANGS = {'python': 'python', 'javascript': 'javascript', 'c': 'c', 'cpp': 'c++', 'java': 'java', 'go': 'go'}
    FILES = LocalExecutor.FILES
    _runtimes = (0.0, None)  # (fetched at, set of runtime names and aliases)

    def __init__(self):
        self.url = os.getenv('PISTON_URL', 'http://localhost:2000').rstrip('/')
        # Piston has no login of its own. When it runs on another server behind a reverse proxy,
        # the proxy checks this token, so only our backend can run code there.
        token = os.getenv('PISTON_TOKEN', '').strip()
        self.headers = {'Authorization': f'Bearer {token}'} if token else {}

    def available(self):
        fetched, names = PistonExecutor._runtimes
        if names is None or time.time() - fetched > 300:
            try:
                resp = requests.get(f'{self.url}/api/v2/runtimes', headers=self.headers, timeout=3)
                names = set()
                for r in resp.json():
                    names.add(r.get('language'))
                    names.update(r.get('aliases') or [])
                PistonExecutor._runtimes = (time.time(), names)
            except (requests.RequestException, ValueError, AttributeError):
                return {lang: None for lang in self.LANGS}  # can't tell; a clear error shows when code runs
        return {lang: (None if name in names else f'the {name} runtime in Piston')
                for lang, name in self.LANGS.items()}

    def execute(self, language, source, stdin):
        payload = {
            'language': self.LANGS[language],
            'version': '*',
            'files': [{'name': self.FILES[language], 'content': source}],
            'stdin': stdin,
            'compile_timeout': 20000,
            'run_timeout': TIME_LIMIT_SEC * 1000,
            'run_memory_limit': 256 * 1024 * 1024,
        }
        try:
            resp = requests.post(f'{self.url}/api/v2/execute', json=payload, headers=self.headers,
                                 timeout=TIME_LIMIT_SEC + 30)
        except requests.RequestException:
            raise ExecutorError("Can't reach the code runner (Piston). Is the Docker container running?")
        if resp.status_code != 200:
            raise ExecutorError(f"Code runner error: {resp.text[:200]}")
        data = resp.json()
        comp = data.get('compile')
        if comp and comp.get('code') not in (0, None):
            out = (comp.get('stderr') or '') + (comp.get('stdout') or '')
            return ExecResult('', ("Compilation failed:\n" + out.strip())[:MAX_OUTPUT], False, comp.get('code'),
                              compile_error=True)
        run = data.get('run', {})
        timed_out = run.get('signal') == 'SIGKILL'
        return ExecResult((run.get('stdout') or '')[:MAX_OUTPUT], (run.get('stderr') or '')[:MAX_OUTPUT],
                          timed_out, run.get('code') if run.get('code') is not None else -1)


class DisabledExecutor:
    """CODE_EXECUTOR=off: no code runner on this server (e.g. a host without Docker for Piston).
    The coding round shows a clear message instead of trying to run code."""
    MESSAGE = "Running code isn't available on this server yet, so the coding round is switched off."

    @classmethod
    def available(cls):
        return {lang: 'a code runner on the server' for lang in LocalExecutor.FILES}

    def execute(self, language, source, stdin):
        raise ExecutorError(self.MESSAGE)


def get_executor():
    kind = os.getenv('CODE_EXECUTOR', 'piston').lower()
    if kind == 'local':
        return LocalExecutor()
    if kind == 'off':
        return DisabledExecutor()
    return PistonExecutor()
