
# ---- test runner (appended after the candidate's code) ----
import json as _json, sys as _sys, io as _io, time as _time, copy as _copy, traceback as _tb


def _run_tests():
    data = _json.loads(_sys.stdin.read())
    real_out = _sys.__stdout__
    fn = globals().get(data["fn"])
    if not callable(fn):
        real_out.write("__R__" + data["token"] + _json.dumps({"fatal": f"Function '{data['fn']}' was not found. Keep the given function name."}) + "\n")
        return
    for args in data["tests"]:
        buf = _io.StringIO()
        _sys.stdout = buf
        start = _time.perf_counter()
        try:
            rec = {"ok": True, "output": fn(*_copy.deepcopy(args))}
        except Exception as e:
            rec = {"ok": False, "error": "".join(_tb.format_exception_only(type(e), e)).strip()}
        finally:
            _sys.stdout = real_out
        rec["ms"] = round((_time.perf_counter() - start) * 1000, 2)
        rec["stdout"] = buf.getvalue()[-2000:]
        try:
            line = _json.dumps(rec)
        except (TypeError, ValueError):
            rec["output"] = repr(rec.get("output"))
            rec["unserializable"] = True
            line = _json.dumps(rec)
        real_out.write("__R__" + data["token"] + line + "\n")
        real_out.flush()


_run_tests()
