"""C, C++, Java and Go support for the coding round.

Python and JavaScript receive the test arguments as JSON. The typed languages need a real function
signature, so the parameter and return types are worked out from the problem's own test data
(`signature`). Values go to the program as whitespace-separated tokens (strings hex-encoded, arrays
prefixed with their length), and the result comes back the same way and is decoded here.

Supported types: int, long, double, bool, string, and 1-D / 2-D arrays of them. A problem whose data
doesn't fit (mixed lists, nulls, 3-D lists) is offered in Python and JavaScript only.
"""
import re

LABELS = {'python': 'Python', 'javascript': 'JavaScript', 'cpp': 'C++', 'c': 'C', 'java': 'Java', 'go': 'Go'}
TYPED = ('cpp', 'c', 'java', 'go')

# Parameter names that are keywords or common type/builtin names in one of the typed languages.
RESERVED = {
    'auto', 'bool', 'boolean', 'break', 'byte', 'case', 'catch', 'chan', 'char', 'class', 'const', 'continue',
    'default', 'defer', 'delete', 'do', 'double', 'else', 'enum', 'extern', 'false', 'final', 'float', 'for',
    'func', 'go', 'goto', 'if', 'import', 'int', 'interface', 'len', 'cap', 'long', 'main', 'map', 'max', 'min',
    'namespace', 'new', 'null', 'operator', 'package', 'private', 'protected', 'public', 'range', 'register',
    'return', 'select', 'set', 'short', 'signed', 'sizeof', 'static', 'string', 'struct', 'switch', 'template',
    'this', 'throw', 'true', 'try', 'type', 'typedef', 'union', 'unsigned', 'using', 'var', 'vector', 'void',
    'volatile', 'while', 'list', 'copy', 'error', 'abs', 'time',
}


# ---------------------------------------------------------------- type inference

class _Mixed(Exception):
    pass


NUMERIC = ['int', 'long', 'double']


def _kind(value):
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, int):
        return 'int' if -2**31 <= value < 2**31 else 'long'
    if isinstance(value, float):
        return 'double'
    if isinstance(value, str):
        return 'string'
    if isinstance(value, list):
        inner = None
        for x in value:
            inner = _merge(inner, _kind(x))
        return ('list', inner)
    raise _Mixed


def _merge(a, b):
    if a is None:
        return b
    if b is None or a == b:
        return a
    if a in NUMERIC and b in NUMERIC:
        return max(a, b, key=NUMERIC.index)
    if isinstance(a, tuple) and isinstance(b, tuple):
        return ('list', _merge(a[1], b[1]))
    raise _Mixed


def _type_name(kind):
    if kind is None:
        return 'int'  # only empty lists seen; int is the usual case
    if isinstance(kind, tuple):
        inner = kind[1]
        if isinstance(inner, tuple):
            if isinstance(inner[1], tuple):
                raise _Mixed  # 3-D lists aren't supported
            return _type_name(inner[1]) + '[][]'
        return _type_name(inner) + '[]'
    return kind


def signature(problem):
    """{'params': [type, ...], 'returns': type}, or None when the data can't be typed."""
    n = len(problem.get('params') or [])
    kinds, ret = [None] * n, None
    try:
        for sample in list(problem.get('examples') or []) + list(problem.get('tests') or []):
            args = sample.get('args')
            if not isinstance(args, list) or len(args) != n:
                continue
            for i, a in enumerate(args):
                kinds[i] = _merge(kinds[i], _kind(a))
            ret = _merge(ret, _kind(sample.get('expected')))
        params, returns = [_type_name(k) for k in kinds], _type_name(ret)
    except _Mixed:
        return None
    if problem.get('compare') == 'float' and returns in ('int', 'long'):
        returns = 'double'
    return {'params': params, 'returns': returns}


def languages_for(problem, sig=None):
    sig = sig if sig is not None else signature(problem)
    return ['python', 'javascript'] + (list(TYPED) if sig else [])


def param_names(problem):
    return [p + '_' if p in RESERVED else p for p in problem['params']]


# ---------------------------------------------------------------- token encoding

def _enc(value, t, out):
    if t.endswith('[]'):
        out.append(str(len(value)))
        for x in value:
            _enc(x, t[:-2], out)
    elif t == 'string':
        out.append(value.encode('utf-8').hex() or '-')
    elif t == 'bool':
        out.append('1' if value else '0')
    elif t == 'double':
        out.append(repr(float(value)))
    else:
        out.append(str(int(value)))


def encode_stdin(tests, sig, token):
    lines = [token, str(len(tests))]
    for test in tests:
        out = []
        for value, t in zip(test['args'], sig['params']):
            _enc(value, t, out)
        lines.append(' '.join(out))
    return '\n'.join(lines) + '\n'


def _dec(tokens, t):
    if t.endswith('[]'):
        return [_dec(tokens, t[:-2]) for _ in range(int(next(tokens)))]
    tok = next(tokens)
    if t == 'string':
        return '' if tok == '-' else bytes.fromhex(tok).decode('utf-8', 'replace')
    if t == 'bool':
        return tok != '0'
    if t == 'double':
        return float(tok)
    return int(tok)


def parse_output(stdout, token, returns):
    """Result lines look like `__R__<token> ok <ms> <value tokens>` or `... err <ms> <hex message>`.
    Anything else the program printed before a result line is that test's stdout."""
    marker = '__R__' + token + ' '
    records, printed = [], []
    for line in stdout.split('\n'):
        if not line.startswith(marker):
            printed.append(line.rstrip('\r'))
            continue
        rec = {'stdout': '\n'.join(printed).strip('\n')[-2000:]}
        printed = []
        parts = line[len(marker):].split()
        try:
            rec['ms'] = round(float(parts[1]), 2)
            if parts[0] == 'ok':
                tokens = iter(parts[2:])
                rec['output'] = _dec(tokens, returns)
                if next(tokens, None) is not None:
                    raise ValueError('extra tokens')
                rec['ok'] = True
            else:
                msg = parts[2] if len(parts) > 2 else '-'
                rec.update(ok=False, error=('' if msg == '-' else bytes.fromhex(msg).decode('utf-8', 'replace'))
                           or 'Runtime error')
        except (ValueError, IndexError, StopIteration):
            rec.update(ok=False, error="The returned value couldn't be read.")
        records.append(rec)
    return records


# ---------------------------------------------------------------- per-language types

def _depth(t):
    return t.count('[]')


def _base(t):
    return t.replace('[]', '')


CPP = {'int': 'int', 'long': 'long long', 'double': 'double', 'bool': 'bool', 'string': 'string'}
C = {'int': 'int', 'long': 'long long', 'double': 'double', 'bool': 'bool', 'string': 'char*'}
JAVA = {'int': 'int', 'long': 'long', 'double': 'double', 'bool': 'boolean', 'string': 'String'}
GO = {'int': 'int', 'long': 'int', 'double': 'float64', 'bool': 'bool', 'string': 'string'}


def cpp_type(t):
    return f'vector<{cpp_type(t[:-2])}>' if t.endswith('[]') else CPP[t]


def java_type(t):
    return JAVA[_base(t)] + '[]' * _depth(t)


def go_type(t):
    return '[]' * _depth(t) + GO[_base(t)]


def _c_params(sig, names):
    out = []
    for t, n in zip(sig['params'], names):
        base, d = C[_base(t)], _depth(t)
        if d == 0:
            out.append(f'{base} {n}')
        elif d == 1:
            out.append(f'{base}* {n}, int {n}Size')
        else:
            out.append(f'{base}** {n}, int {n}Size, int* {n}ColSize')
    r = sig['returns']
    if _depth(r) == 1:
        out.append('int* returnSize')
    elif _depth(r) == 2:
        out += ['int* returnSize', 'int** returnColumnSizes']
    return ', '.join(out)


def _c_return(t):
    return C[_base(t)] + '*' * _depth(t)


# ---------------------------------------------------------------- starter code

def starter_code(problem, language, sig=None):
    names = problem['params']
    if language == 'python':
        return f"def {problem['function']}({', '.join(names)}):\n    # Write your solution here\n    pass\n"
    if language == 'javascript':
        return f"function {problem['js_function']}({', '.join(names)}) {{\n    // Write your solution here\n}}\n"

    sig = sig or signature(problem)
    if not sig:
        return ''
    fn, names, r = problem['js_function'], param_names(problem), sig['returns']

    if language == 'cpp':
        params = ', '.join(f'{cpp_type(t)}& {n}' if (t.endswith('[]') or t == 'string') else f'{cpp_type(t)} {n}'
                           for t, n in zip(sig['params'], names))
        return (f"class Solution {{\npublic:\n    {cpp_type(r)} {fn}({params}) {{\n"
                f"        // Write your solution here\n        return {{}};\n    }}\n}};\n")

    if language == 'c':
        if _depth(r) == 0:
            body = '    return "";' if r == 'string' else ('    return false;' if r == 'bool' else '    return 0;')
            note = ''
        else:
            body = '    *returnSize = 0;\n'
            if _depth(r) == 2:
                body += '    *returnColumnSizes = NULL;\n'
            body += '    return NULL;'
            note = ('// Return an array allocated with malloc and set *returnSize'
                    + (' and *returnColumnSizes' if _depth(r) == 2 else '') + '.\n')
        return f"{note}{_c_return(r)} {fn}({_c_params(sig, names)}) {{\n    // Write your solution here\n{body}\n}}\n"

    if language == 'java':
        params = ', '.join(f'{java_type(t)} {n}' for t, n in zip(sig['params'], names))
        if _depth(r):
            default = f"new {JAVA[_base(r)]}[0]" + '[]' * (_depth(r) - 1)
        else:
            default = {'bool': 'false', 'string': '""'}.get(r, '0')
        return (f"class Solution {{\n    public {java_type(r)} {fn}({params}) {{\n"
                f"        // Write your solution here\n        return {default};\n    }}\n}}\n")

    if language == 'go':
        params = ', '.join(f'{n} {go_type(t)}' for t, n in zip(sig['params'], names))
        default = 'nil' if _depth(r) else {'bool': 'false', 'string': '""'}.get(r, '0')
        return f"func {fn}({params}) {go_type(r)} {{\n\t// Write your solution here\n\treturn {default}\n}}\n"
    return ''


# ---------------------------------------------------------------- harness: C++

CPP_PRELUDE = '#include <bits/stdc++.h>\nusing namespace std;\n#line 1 "solution.cpp"\n'

CPP_HARNESS = r'''
#line 1 "judge.cpp"
namespace judge_io {
using namespace std;
inline void rd(int& x) { long long t; cin >> t; x = (int) t; }
inline void rd(long long& x) { cin >> x; }
inline void rd(double& x) { string s; cin >> s; x = strtod(s.c_str(), nullptr); }
inline void rd(bool& x) { int t; cin >> t; x = t != 0; }
inline void rd(string& x) {
    string h; cin >> h; x.clear();
    if (h == "-") return;
    for (size_t i = 0; i + 1 < h.size(); i += 2) x.push_back((char) strtol(h.substr(i, 2).c_str(), nullptr, 16));
}
inline void rd(vector<bool>& v) { int n; cin >> n; v.assign(n, false); for (int i = 0; i < n; i++) { int t; cin >> t; v[i] = t != 0; } }
template <class T> void rd(vector<T>& v) { int n; cin >> n; v.assign(n, T()); for (auto& e : v) rd(e); }
inline string to_hex(const string& s) {
    if (s.empty()) return "-";
    static const char* d = "0123456789abcdef";
    string o;
    for (unsigned char c : s) { o += d[c >> 4]; o += d[c & 15]; }
    return o;
}
inline void wr(ostream& o, int x) { o << x << ' '; }
inline void wr(ostream& o, long long x) { o << x << ' '; }
inline void wr(ostream& o, double x) { o << setprecision(17) << x << ' '; }
inline void wr(ostream& o, bool x) { o << (x ? 1 : 0) << ' '; }
inline void wr(ostream& o, const string& x) { o << to_hex(x) << ' '; }
template <class T> void wr(ostream& o, const vector<T>& v) { o << v.size() << ' '; for (const auto& e : v) wr(o, e); }
}

int main() {
    std::string judge_token; int judge_count = 0;
    if (!(std::cin >> judge_token >> judge_count)) return 0;
    for (int judge_t = 0; judge_t < judge_count; judge_t++) {
__DECLS__
        std::ostringstream judge_out; std::string judge_err; bool judge_ok = true;
        __RET__ judge_r{};
        auto judge_start = std::chrono::steady_clock::now();
        try {
            judge_r = Solution().__FN__(__ARGS__);
        } catch (const std::exception& e) { judge_ok = false; judge_err = e.what(); }
        catch (...) { judge_ok = false; judge_err = "exception thrown"; }
        double judge_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - judge_start).count();
        if (judge_ok) judge_io::wr(judge_out, judge_r);
        std::cout.flush(); fflush(stdout);
        std::cout << "\n__R__" << judge_token << (judge_ok ? " ok " : " err ") << judge_ms << ' '
                  << (judge_ok ? judge_out.str() : judge_io::to_hex(judge_err)) << std::endl;
    }
    return 0;
}
'''


def _cpp_source(problem, sig, code):
    decls = '\n'.join(f'        {cpp_type(t)} judge_a{i}; judge_io::rd(judge_a{i});' for i, t in enumerate(sig['params']))
    args = ', '.join(f'judge_a{i}' for i in range(len(sig['params'])))
    harness = (CPP_HARNESS.replace('__DECLS__', decls).replace('__RET__', cpp_type(sig['returns']))
               .replace('__FN__', problem['js_function']).replace('__ARGS__', args))
    return CPP_PRELUDE + code + '\n' + harness


# ---------------------------------------------------------------- harness: C

C_PRELUDE = ('#define __USE_MINGW_ANSI_STDIO 1\n'
             + ''.join(f'#include <{h}.h>\n' for h in
                       ('stdio', 'stdlib', 'string', 'stdbool', 'stdint', 'math', 'limits', 'ctype', 'time'))
             + '#line 1 "solution.c"\n')

C_HARNESS = r'''
#line 1 "judge.c"
static char* jh_tok(void) {
    int c = getchar();
    while (c == ' ' || c == '\n' || c == '\r' || c == '\t') c = getchar();
    size_t cap = 32, n = 0;
    char* s = (char*) malloc(cap);
    while (c != EOF && c != ' ' && c != '\n' && c != '\r' && c != '\t') {
        if (n + 1 >= cap) { cap *= 2; s = (char*) realloc(s, cap); }
        s[n++] = (char) c;
        c = getchar();
    }
    s[n] = 0;
    return s;
}
static long long jh_ll(void) { char* t = jh_tok(); long long v = strtoll(t, NULL, 10); free(t); return v; }
static double jh_d(void) { char* t = jh_tok(); double v = strtod(t, NULL); free(t); return v; }
static int jh_hexval(char c) { return c <= '9' ? c - '0' : (c | 32) - 'a' + 10; }
static char* jh_s(void) {
    char* t = jh_tok();
    size_t n = strlen(t);
    if (strcmp(t, "-") == 0) { t[0] = 0; return t; }
    char* s = (char*) malloc(n / 2 + 1);
    for (size_t i = 0; i + 1 < n; i += 2) s[i / 2] = (char) (jh_hexval(t[i]) * 16 + jh_hexval(t[i + 1]));
    s[n / 2] = 0;
    free(t);
    return s;
}
static void jh_wll(long long v) { printf("%lld ", v); }
static void jh_wd(double v) { printf("%.17g ", v); }
static void jh_ws(const char* s) {
    if (!s || !*s) { printf("- "); return; }
    for (const unsigned char* p = (const unsigned char*) s; *p; p++) printf("%02x", *p);
    printf(" ");
}

int main(void) {
    char* jh_token = jh_tok();
    int jh_count = (int) jh_ll();
    for (int jh_t = 0; jh_t < jh_count; jh_t++) {
__DECLS__
        clock_t jh_start = clock();
__CALL__
        double jh_ms = (double) (clock() - jh_start) * 1000.0 / CLOCKS_PER_SEC;
        fflush(stdout);
        printf("\n__R__%s ok %.3f ", jh_token, jh_ms);
__WRITE__
        printf("\n");
        fflush(stdout);
    }
    return 0;
}
'''

C_READ = {'int': '(int) jh_ll()', 'long': 'jh_ll()', 'double': 'jh_d()', 'bool': '(jh_ll() != 0)', 'string': 'jh_s()'}
C_WRITE = {'int': 'jh_wll({})', 'long': 'jh_wll({})', 'double': 'jh_wd({})', 'bool': 'jh_wll(({}) ? 1 : 0)',
           'string': 'jh_ws({})'}


def _c_source(problem, sig, code):
    decls, args = [], []
    for i, t in enumerate(sig['params']):
        v, base, d = f'jh_a{i}', _base(t), _depth(t)
        ct, rd = C[base], C_READ[base]
        if d == 0:
            decls.append(f'{ct} {v} = {rd};')
            args.append(v)
        elif d == 1:
            decls.append(f'int {v}Size = (int) jh_ll(); {ct}* {v} = ({ct}*) malloc(sizeof({ct}) * ({v}Size + 1)); '
                         f'for (int i = 0; i < {v}Size; i++) {v}[i] = {rd};')
            args += [v, f'{v}Size']
        else:
            decls.append(f'int {v}Size = (int) jh_ll(); {ct}** {v} = ({ct}**) malloc(sizeof({ct}*) * ({v}Size + 1)); '
                         f'int* {v}Col = (int*) malloc(sizeof(int) * ({v}Size + 1)); '
                         f'for (int i = 0; i < {v}Size; i++) {{ {v}Col[i] = (int) jh_ll(); '
                         f'{v}[i] = ({ct}*) malloc(sizeof({ct}) * ({v}Col[i] + 1)); '
                         f'for (int j = 0; j < {v}Col[i]; j++) {v}[i][j] = {rd}; }}')
            args += [v, f'{v}Size', f'{v}Col']

    r = sig['returns']
    base, d, w = _base(r), _depth(r), C_WRITE[_base(r)]
    fn = problem['js_function']
    if d == 0:
        call = f'{C[base]} jh_r = {fn}({", ".join(args)});'
        write = w.format('jh_r') + ';'
    elif d == 1:
        call = f'int jh_rSize = 0; {C[base]}* jh_r = {fn}({", ".join(args + ["&jh_rSize"])});'
        write = f'jh_wll(jh_rSize); for (int i = 0; i < jh_rSize; i++) {w.format("jh_r[i]")};'
    else:
        call = (f'int jh_rSize = 0; int* jh_rCols = NULL; '
                f'{C[base]}** jh_r = {fn}({", ".join(args + ["&jh_rSize", "&jh_rCols"])});')
        write = (f'jh_wll(jh_rSize); for (int i = 0; i < jh_rSize; i++) {{ int jh_c = jh_rCols ? jh_rCols[i] : 0; '
                 f'jh_wll(jh_c); for (int j = 0; j < jh_c; j++) {w.format("jh_r[i][j]")}; }}')
    harness = (C_HARNESS.replace('__DECLS__', '\n'.join('        ' + x for x in decls))
               .replace('__CALL__', '        ' + call).replace('__WRITE__', '        ' + write))
    return C_PRELUDE + code + '\n' + harness


# ---------------------------------------------------------------- harness: Java

JAVA_HARNESS = r'''
public class Main {
    static String[] judgeTokens; static int judgePos = 0; static StringBuilder judgeSb;
    static String nx() { return judgeTokens[judgePos++]; }
    static int ri() { return (int) Long.parseLong(nx()); }
    static long rl() { return Long.parseLong(nx()); }
    static double rd() { return Double.parseDouble(nx()); }
    static boolean rb() { return !nx().equals("0"); }
    static String rs() {
        String h = nx();
        if (h.equals("-")) return "";
        byte[] b = new byte[h.length() / 2];
        for (int i = 0; i < b.length; i++) b[i] = (byte) Integer.parseInt(h.substring(2 * i, 2 * i + 2), 16);
        return new String(b, java.nio.charset.StandardCharsets.UTF_8);
    }
    static String hx(String s) {
        if (s == null || s.isEmpty()) return "-";
        StringBuilder o = new StringBuilder();
        for (byte b : s.getBytes(java.nio.charset.StandardCharsets.UTF_8)) o.append(String.format("%02x", b & 255));
        return o.toString();
    }
    static void w(long v) { judgeSb.append(v).append(' '); }
    static void w(double v) { judgeSb.append(v).append(' '); }
    static void w(boolean v) { judgeSb.append(v ? 1 : 0).append(' '); }
    static void w(String v) { judgeSb.append(hx(v)).append(' '); }

    public static void main(String[] args) throws Exception {
        String all = new String(System.in.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8).trim();
        judgeTokens = all.split("\\s+");
        String token = nx();
        int count = ri();
        for (int t = 0; t < count; t++) {
__DECLS__
            judgeSb = new StringBuilder();
            boolean ok = true; String err = ""; double ms;
            long start = System.nanoTime();
            try {
                __RET__ r = new Solution().__FN__(__ARGS__);
                ms = (System.nanoTime() - start) / 1e6;
                __WRITE__
            } catch (Throwable e) {
                ms = (System.nanoTime() - start) / 1e6;
                ok = false; err = e.toString();
            }
            System.out.flush();
            System.out.print("\n__R__" + token + (ok ? " ok " : " err ") + ms + " " + (ok ? judgeSb.toString() : hx(err)) + "\n");
            System.out.flush();
        }
    }
}
'''

JAVA_READ = {'int': 'ri()', 'long': 'rl()', 'double': 'rd()', 'bool': 'rb()', 'string': 'rs()'}
JAVA_IMPORT = re.compile(r'^[ \t]*(import\s+(?:static\s+)?[\w.]+(?:\.\*)?\s*;)[ \t]*$', re.M)
JAVA_PACKAGE = re.compile(r'^[ \t]*package\s+[\w.]+\s*;[ \t]*$', re.M)


def _java_source(problem, sig, code):
    imports = ['import java.util.*;', 'import java.io.*;']
    for m in JAVA_IMPORT.finditer(code):
        stmt = re.sub(r'\s+', ' ', m.group(1))
        if stmt not in imports:
            imports.append(stmt)
    # Blank out (not delete) moved lines so line numbers in errors still match.
    body = JAVA_IMPORT.sub('', JAVA_PACKAGE.sub('', code))
    # Main must be the file's only public class.
    body = re.sub(r'\bpublic\s+(?=(?:final\s+)?class\s)', '', body)

    decls, args = [], []
    for i, t in enumerate(sig['params']):
        v, base, d, jt = f'a{i}', _base(t), _depth(t), JAVA[_base(t)]
        rd = JAVA_READ[base]
        if d == 0:
            decls.append(f'{jt} {v} = {rd};')
        elif d == 1:
            decls.append(f'{jt}[] {v} = new {jt}[ri()]; for (int i = 0; i < {v}.length; i++) {v}[i] = {rd};')
        else:
            decls.append(f'{jt}[][] {v} = new {jt}[ri()][]; for (int i = 0; i < {v}.length; i++) {{ '
                         f'{v}[i] = new {jt}[ri()]; for (int j = 0; j < {v}[i].length; j++) {v}[i][j] = {rd}; }}')
        args.append(v)
    r = sig['returns']
    if _depth(r) == 0:
        write = 'w(r);'
    elif _depth(r) == 1:
        write = 'w(r.length); for (int i = 0; i < r.length; i++) w(r[i]);'
    else:
        write = ('w(r.length); for (int i = 0; i < r.length; i++) { w(r[i].length); '
                 'for (int j = 0; j < r[i].length; j++) w(r[i][j]); }')
    harness = (JAVA_HARNESS.replace('__DECLS__', '\n'.join('            ' + x for x in decls))
               .replace('__RET__', java_type(r)).replace('__FN__', problem['js_function'])
               .replace('__ARGS__', ', '.join(args)).replace('__WRITE__', write))
    head = '\n'.join(imports) + '\n' + harness
    return head + body, head.count('\n')


# ---------------------------------------------------------------- harness: Go

GO_IMPORTS = ['"bufio"', '"fmt"', '"os"', '"strconv"', '"strings"', '"time"']

GO_HARNESS = r'''
//line judge.go:1
var judgeIn *bufio.Scanner

func judgeNext() string { judgeIn.Scan(); return judgeIn.Text() }
func judgeInt() int { v, _ := strconv.ParseInt(judgeNext(), 10, 64); return int(v) }
func judgeFloat() float64 { v, _ := strconv.ParseFloat(judgeNext(), 64); return v }
func judgeBool() bool { return judgeNext() != "0" }
func judgeStr() string {
	h := judgeNext()
	if h == "-" {
		return ""
	}
	b := make([]byte, len(h)/2)
	for i := range b {
		v, _ := strconv.ParseUint(h[2*i:2*i+2], 16, 8)
		b[i] = byte(v)
	}
	return string(b)
}
func judgeHex(s string) string {
	if s == "" {
		return "-"
	}
	return fmt.Sprintf("%x", s)
}
func judgeW(sb *strings.Builder, v interface{}) {
	switch x := v.(type) {
	case int:
		sb.WriteString(strconv.Itoa(x))
	case float64:
		sb.WriteString(strconv.FormatFloat(x, 'g', 17, 64))
	case bool:
		if x {
			sb.WriteString("1")
		} else {
			sb.WriteString("0")
		}
	case string:
		sb.WriteString(judgeHex(x))
	}
	sb.WriteByte(' ')
}

func main() {
	judgeIn = bufio.NewScanner(os.Stdin)
	judgeIn.Buffer(make([]byte, 1024*1024), 64*1024*1024)
	judgeIn.Split(bufio.ScanWords)
	token := judgeNext()
	count := judgeInt()
	for t := 0; t < count; t++ {
__DECLS__
		var sb strings.Builder
		ok, errMsg := true, ""
		var r __RET__
		start := time.Now()
		func() {
			defer func() {
				if e := recover(); e != nil {
					ok, errMsg = false, fmt.Sprint(e)
				}
			}()
			r = __FN__(__ARGS__)
		}()
		ms := float64(time.Since(start).Nanoseconds()) / 1e6
		status, payload := " err ", judgeHex(errMsg)
		if ok {
			__WRITE__
			status, payload = " ok ", sb.String()
		}
		os.Stdout.Sync()
		fmt.Print("\n__R__" + token + status + strconv.FormatFloat(ms, 'f', 3, 64) + " " + payload + "\n")
	}
}
'''

GO_READ = {'int': 'judgeInt()', 'long': 'judgeInt()', 'double': 'judgeFloat()', 'bool': 'judgeBool()',
           'string': 'judgeStr()'}
GO_IMPORT_BLOCK = re.compile(r'^[ \t]*import[ \t]*\((.*?)\)', re.M | re.S)
GO_IMPORT_LINE = re.compile(r'^[ \t]*import[ \t]+([^\n(]+?)[ \t]*$', re.M)
GO_PACKAGE = re.compile(r'^[ \t]*package[ \t]+\w+[ \t]*$', re.M)


def _blank(match):
    return '\n' * match.group(0).count('\n')


def _go_source(problem, sig, code):
    imports = list(GO_IMPORTS)

    def add(spec):
        spec = spec.split('//')[0].strip().rstrip(';').strip()
        if spec and spec not in imports:
            imports.append(spec)

    for m in GO_IMPORT_BLOCK.finditer(code):
        for line in m.group(1).splitlines():
            add(line)
    body = GO_IMPORT_BLOCK.sub(_blank, code)
    for m in GO_IMPORT_LINE.finditer(body):
        add(m.group(1))
    body = GO_IMPORT_LINE.sub('', GO_PACKAGE.sub('', body))

    decls, args = [], []
    for i, t in enumerate(sig['params']):
        v, base, d, gt = f'a{i}', _base(t), _depth(t), GO[_base(t)]
        rd = GO_READ[base]
        if d == 0:
            decls.append(f'{v} := {rd}')
        elif d == 1:
            decls.append(f'{v} := make([]{gt}, judgeInt())\n\t\tfor i := range {v} {{ {v}[i] = {rd} }}')
        else:
            decls.append(f'{v} := make([][]{gt}, judgeInt())\n\t\tfor i := range {v} {{ {v}[i] = make([]{gt}, judgeInt()); '
                         f'for j := range {v}[i] {{ {v}[i][j] = {rd} }} }}')
        args.append(v)
    r = sig['returns']
    if _depth(r) == 0:
        write = 'judgeW(&sb, r)'
    elif _depth(r) == 1:
        write = 'judgeW(&sb, len(r)); for _, e := range r { judgeW(&sb, e) }'
    else:
        write = 'judgeW(&sb, len(r)); for _, row := range r { judgeW(&sb, len(row)); for _, e := range row { judgeW(&sb, e) } }'
    harness = (GO_HARNESS.replace('__DECLS__', '\n'.join('\t\t' + x for x in decls))
               .replace('__RET__', go_type(r)).replace('__FN__', problem['js_function'])
               .replace('__ARGS__', ', '.join(args)).replace('__WRITE__', write))
    head = 'package main\n\nimport (\n' + ''.join(f'\t{s}\n' for s in imports) + ')\n\n//line solution.go:1\n'
    return head + body + '\n' + harness


def build_source(language, problem, sig, code):
    """Returns (source, line_offset). line_offset is how many lines come before the candidate's code
    where the language has no #line directive (Java), so error line numbers can be corrected."""
    if language == 'cpp':
        return _cpp_source(problem, sig, code), 0
    if language == 'c':
        return _c_source(problem, sig, code), 0
    if language == 'java':
        return _java_source(problem, sig, code)
    if language == 'go':
        return _go_source(problem, sig, code), 0
    raise ValueError(language)


JAVA_LINE = re.compile(r'[^\s:]*?(?:\w+)\.java:(\d+)')


def clean_errors(text, language, offset):
    """Point compiler messages at the candidate's own line numbers."""
    if language == 'java':
        def fix(m):
            n = int(m.group(1)) - offset
            return f'Solution.java:{n}' if n > 0 else 'Main.java'
        text = JAVA_LINE.sub(fix, text)
    return text
