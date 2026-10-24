"""LLM settings + client facade.

Credentials are never persisted in code. The backend reads defaults from `.env`
(Settings), but the frontend can override them at runtime via the settings API
so each page can bring its own relay Base URL + API key. Browser overrides use
an isolated expiring memory store; CLI defaults are separate. Never persisted.
"""

from __future__ import annotations

import json
import re
import logging
from typing import Any

from backend.config import get_settings
from backend.core.generate.session import configure_session, session_settings

_OVERRIDE_KEY = ""
_OVERRIDE_BASE = ""
_OVERRIDE_MODEL = ""


class LLMUnavailable(RuntimeError):
    pass


def parse_json_object(content: str, *, allow_literal_linebreaks: bool = False) -> tuple[dict[str, Any], str]:
    """Accept a whole JSON object, optionally one complete JSON fence.

    Strict by default; product compatibility may retain literal LF/CR/TAB
    inside strings. No values or missing syntax are invented. The original
    response remains in the trace.
    """
    if not isinstance(content, str):
        raise LLMUnavailable('LLM 响应正文不是文本')
    fence = re.fullmatch(r'\s*```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```\s*', content, re.I)
    text = fence.group(1) if fence else content
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        # Product-only compatibility for providers that put literal LF/CR/TAB
        # inside strings. Preserve those exact characters; never fill missing
        # braces, change quotes, or accept other control characters. Research
        # clients keep strict JSON parsing by default.
        if not allow_literal_linebreaks or any(ord(ch) < 32 and ch not in '\n\r\t' for ch in text):
            raise LLMUnavailable('LLM 返回的内容不是完整、合法的 JSON') from exc
        try:
            parsed = json.loads(text, strict=False)
        except json.JSONDecodeError as second:
            raise LLMUnavailable('LLM 返回的内容不是完整、合法的 JSON') from second
        return_mode = 'literal_string_linebreaks'
    else:
        return_mode = 'none'
    if not isinstance(parsed, dict):
        raise LLMUnavailable('LLM 必须返回 JSON 对象')
    mode = ('single_json_fence+' if fence else '') + return_mode
    return parsed, 'single_json_fence' if mode == 'single_json_fence+none' else mode


def configure_llm(api_key: str = "", base_url: str = "", model: str = "") -> None:
    """Page overrides are isolated; CLI callers retain explicit process defaults."""
    if configure_session(api_key, base_url, model):
        return
    global _OVERRIDE_KEY, _OVERRIDE_BASE, _OVERRIDE_MODEL
    if api_key:
        _OVERRIDE_KEY = api_key
    if base_url:
        _OVERRIDE_BASE = base_url.rstrip("/")
    if model:
        _OVERRIDE_MODEL = model


def llm_configured() -> bool:
    s = get_settings()
    config = session_settings()
    return bool((config[0] if config is not None else _OVERRIDE_KEY) or s.llm_api_key)


class LLMClient:
    def __init__(self, *, timeout_s: float = 300.0, retry_limit: int = 2, allow_literal_linebreaks: bool = False) -> None:
        s = get_settings()
        config = session_settings()
        key, base, model = config if config is not None else (_OVERRIDE_KEY, _OVERRIDE_BASE, _OVERRIDE_MODEL)
        self._key = key or s.llm_api_key
        self._base = (base or s.llm_base_url).rstrip("/")
        self._model = model or s.llm_model
        self.trace: list[dict] = []
        self.attempt_count = 0
        self.request_events: list[dict] = []
        self._timeout_s = timeout_s
        self._retry_limit = retry_limit
        self._allow_literal_linebreaks = allow_literal_linebreaks

    def public_config(self) -> dict:
        """Non-secret experiment metadata. Never include credentials or URL query."""
        from urllib.parse import urlsplit
        url = urlsplit(self._base)
        return {"model": self._model, "endpoint_host": url.hostname}

    def available(self) -> bool:
        return bool(self._key)

    def _request_event(self, elapsed: float, error: Exception | None = None) -> None:
        """Timing/status only: never log prompts, provider bodies, URLs or keys."""
        import httpx
        event = {'elapsed_ms': round(elapsed * 1000), 'attempt': self.attempt_count,
                 'status': error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None,
                 'result': 'timeout' if isinstance(error, httpx.TimeoutException) else 'request_failed' if error else 'response_received'}
        self.request_events.append(event)
        if error:
            logging.getLogger(__name__).warning('Model request result=%s elapsed_ms=%s status=%s attempt=%s',
                event['result'], event['elapsed_ms'], event['status'], event['attempt'])

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        retries: int = 2,
    ) -> dict[str, Any]:
        """Return parsed JSON object from a chat completion.

        Retries transient network/timeout errors with backoff so a slow relay
        doesn't drop an entire stage (which would fall back to heuristic).
        """
        if not self.available():
            raise LLMUnavailable("未配置 LLM_API_KEY（请在 设置 里填写）")
        import time

        import httpx

        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        last_exc: Exception | None = None
        retries = min(retries, self._retry_limit)
        for attempt in range(retries + 1):
            self.attempt_count += 1
            started = time.perf_counter()
            try:
                resp = httpx.post(
                    f"{self._base}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_s,
                )
                resp.raise_for_status()
            except Exception as exc:  # noqa: BLE001 - network/API errors surfaced
                self._request_event(time.perf_counter() - started, exc)
                last_exc = exc
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMUnavailable(f"LLM 调用失败: {exc}") from exc
            self._request_event(time.perf_counter() - started)
            try:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise LLMUnavailable("LLM 响应结构无效") from exc
            self.trace.append({"messages": messages, "content": content,
                               "usage": data.get("usage", {}), "model": data.get("model", self._model),
                               "response_id": data.get("id"), "attempt": attempt + 1})
            parsed, normalization = parse_json_object(content, allow_literal_linebreaks=self._allow_literal_linebreaks)
            self.trace[-1]['format_normalization'] = normalization
            return parsed
        raise LLMUnavailable(f"LLM 调用失败: {last_exc}")

    def chat_text(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        retries: int = 2,
    ) -> str:
        """Return a plain-text completion (for explanations / diagnosis)."""
        if not self.available():
            raise LLMUnavailable("未配置 LLM_API_KEY（请在 设置 里填写）")
        import time

        import httpx

        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        last_exc: Exception | None = None
        retries = min(retries, self._retry_limit)
        for attempt in range(retries + 1):
            self.attempt_count += 1
            try:
                resp = httpx.post(
                    f"{self._base}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_s,
                )
                resp.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMUnavailable(f"LLM 调用失败: {exc}") from exc
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        raise LLMUnavailable(f"LLM 调用失败: {last_exc}")
