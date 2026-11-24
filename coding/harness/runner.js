
// ---- test runner (appended after the candidate's code) ----
(() => {
    const fs = require('fs');
    const data = JSON.parse(fs.readFileSync(0, 'utf8'));
    const write = (obj) => fs.writeSync(1, '__R__' + data.token + JSON.stringify(obj) + '\n');
    let fn;
    try { fn = eval(data.fn); } catch (e) { fn = undefined; }
    if (typeof fn !== 'function') {
        write({ fatal: `Function '${data.fn}' was not found. Keep the given function name.` });
        return;
    }
    const realLog = console.log;
    for (const args of data.tests) {
        let printed = '';
        console.log = (...parts) => { printed += parts.map(p => typeof p === 'string' ? p : JSON.stringify(p)).join(' ') + '\n'; };
        const start = process.hrtime.bigint();
        let rec;
        try {
            const output = fn(...structuredClone(args));
            rec = { ok: true, output: output === undefined ? null : output };
        } catch (e) {
            rec = { ok: false, error: String(e && e.stack ? e.stack.split('\n')[0] : e) };
        }
        console.log = realLog;
        rec.ms = Number(process.hrtime.bigint() - start) / 1e6;
        rec.stdout = printed.slice(-2000);
        try {
            write(rec);
        } catch (e) {
            write({ ok: true, output: String(rec.output), unserializable: true, ms: rec.ms, stdout: rec.stdout });
        }
    }
})();
