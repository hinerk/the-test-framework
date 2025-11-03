import datetime
import json
import traceback
import logging


# From logging docs + CPython source; used to detect "extras"
_STANDARD_ATTRS = {
    'name','msg','args','levelname','levelno','pathname','filename','module',
    'exc_info','exc_text','stack_info','lineno','funcName','created','msecs',
    'relativeCreated','thread','threadName','process','processName',
    'taskName'  # present when using asyncio
}

def _safe_jsonable(obj):
    """Return obj if JSON-serializable; else a repr() fallback."""
    try:
        json.dumps(obj)
        return obj
    except Exception:
        try:
            return repr(obj)
        except Exception:
            return f"<unreprable {type(obj).__name__}>"

def log_record_to_dict(r: logging.LogRecord) -> dict:
    # Render message with args
    try:
        rendered = r.getMessage()
    except Exception:
        rendered = f"{r.msg} {r.args}"

    # Exception block (if any)
    exc = None
    if r.exc_info:
        etype, evalue, etb = r.exc_info
        exc = {
            "type": getattr(etype, "__name__", str(etype)),
            "message": str(evalue),
            "traceback": "".join(traceback.format_exception(etype, evalue, etb)),
        }

    # Extras (anything user supplied via `extra=...`)
    extras = {
        k: _safe_jsonable(v)
        for k, v in r.__dict__.items()
        if k not in _STANDARD_ATTRS
    }

    # Epoch and ISO timestamps
    ts = r.created
    ts_iso = datetime.datetime.fromtimestamp(ts).isoformat(timespec="milliseconds")

    return {
        "timestamp": ts,
        "timestamp_iso": ts_iso,
        "name": r.name,
        "level": r.levelno,
        "level_name": r.levelname,
        "pathname": r.pathname,
        "filename": r.filename,
        "module": r.module,
        "func": r.funcName,
        "lineno": r.lineno,
        "process_id": r.process,
        "process_name": r.processName,
        "thread_id": r.thread,
        "thread_name": r.threadName,
        "task_name": getattr(r, "taskName", None),   # asyncio, if available
        "message": rendered,                         # msg with args applied
        "msg_template": r.msg if isinstance(r.msg, str) else repr(r.msg),
        "msg_args": _safe_jsonable(r.args),   # keep machine-readable form too
        "stack_info": r.stack_info,
        "exception": exc,
        "extras": extras,
    }
