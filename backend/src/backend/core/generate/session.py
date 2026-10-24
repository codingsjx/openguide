"""Bounded, expiring page-session model settings. Never persist credentials."""
from collections import OrderedDict
from contextvars import ContextVar
from threading import RLock
from time import monotonic

active_session: ContextVar[str | None] = ContextVar('openguide_llm_session', default=None)
_settings: OrderedDict[str, tuple[float, tuple[str, str, str]]] = OrderedDict()
_lock = RLock()
TTL_SECONDS = 1800
MAX_SESSIONS = 128


def _expire(now: float) -> None:
    for key in [key for key, (seen, _) in _settings.items() if now - seen >= TTL_SECONDS]:
        del _settings[key]


def session_settings() -> tuple[str, str, str] | None:
    """None means CLI/no page; an unknown page never inherits CLI overrides."""
    session = active_session.get()
    if session is None:
        return None
    with _lock:
        now = monotonic()
        _expire(now)
        if session not in _settings:
            return ('', '', '')
        _, config = _settings[session]
        _settings[session] = (now, config)
        _settings.move_to_end(session)
        return config


def configure_session(api_key: str, base_url: str, model: str) -> bool:
    session = active_session.get()
    if session is None:
        return False
    with _lock:
        now = monotonic()
        _expire(now)
        prior = _settings.get(session, (now, ('', '', '')))[1]
        _settings[session] = (now, (api_key or prior[0], base_url.rstrip('/') or prior[1], model or prior[2]))
        _settings.move_to_end(session)
        while len(_settings) > MAX_SESSIONS:
            _settings.popitem(last=False)
    return True


class ModelSessionMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        import re
        from starlette.responses import JSONResponse
        headers = dict(scope.get('headers', []))
        session = headers.get(b'x-openguide-session', b'').decode('ascii', errors='replace')
        if session and not re.fullmatch(r'[a-f0-9]{32}', session):
            return await JSONResponse({'detail': '页面会话标识无效，请刷新页面'}, status_code=400)(scope, receive, send)
        token = active_session.set(session or None)
        try:
            await self.app(scope, receive, send)
        finally:
            active_session.reset(token)
