import contextvars
import uuid

_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

def get_request_id() -> str:
    return _request_id_ctx.get()

def set_request_id(value: str) -> None:
    _request_id_ctx.set(value)

def new_request_id() -> str:
    return str(uuid.uuid4())