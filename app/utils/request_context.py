from contextvars import ContextVar

_request_id: ContextVar[str] = ContextVar("request_id", default="-")

def set_request_id(rid: str) -> None:
    _request_id.set(rid)

def get_request_id() -> str:
    return _request_id.get()

def clear_request_id() -> None:
    _request_id.set("-")