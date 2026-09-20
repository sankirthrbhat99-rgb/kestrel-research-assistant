"""Tests for LLMClient retry/backoff behaviour and provider auto-detection.

All tests run without an API key and without making real network calls.
``urllib.request.urlopen`` is patched at the module level.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Project root on sys.path for direct test invocation.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Clear any ambient LLM keys so tests start from a clean slate.
import os
for _var in (
    "KESTREL_LLM_API_KEY",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
):
    os.environ.pop(_var, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_response(body: dict, status: int = 200) -> MagicMock:
    """Return a context-manager mock that behaves like urllib's response."""
    resp = MagicMock()
    raw = json.dumps(body).encode("utf-8")
    resp.read.return_value = raw
    resp.status = status
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _http_error(code: int, body: str = "error") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="http://x", code=code, msg=str(code),
        hdrs=None, fp=BytesIO(body.encode()),  # type: ignore[arg-type]
    )


_OK_BODY = {
    "choices": [{"message": {"content": "The answer is 42."}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
}


# ---------------------------------------------------------------------------
# 1. 429 retry: succeeds on second attempt
# ---------------------------------------------------------------------------


def test_429_triggers_one_retry_and_succeeds():
    """HTTP 429 should trigger exactly one retry, then succeed."""
    from kestrel.llm import LLMClient, LLMConfig

    cfg = LLMConfig(api_key="sk-test", base_url="https://api.openai.com/v1",
                    model="gpt-4o-mini", timeout=10.0)
    client = LLMClient(config=cfg)

    call_count = 0

    def fake_urlopen(req, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _http_error(429)
        return _fake_response(_OK_BODY)

    with patch("kestrel.llm.time.sleep") as mock_sleep, \
         patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = client.complete("Hello?")

    assert result == "The answer is 42."
    assert call_count == 2, f"Expected 2 calls (1 + 1 retry); got {call_count}"
    # Backoff must have been called once with a positive delay.
    mock_sleep.assert_called_once()
    assert mock_sleep.call_args[0][0] > 0


# ---------------------------------------------------------------------------
# 2. 429 twice → raises RuntimeError after exhausting retries
# ---------------------------------------------------------------------------


def test_429_twice_raises_after_max_retries():
    """After MAX_RETRIES retries all fail → RuntimeError is raised."""
    from kestrel.llm import LLMClient, LLMConfig, MAX_RETRIES

    cfg = LLMConfig(api_key="sk-test", base_url="https://api.openai.com/v1",
                    model="gpt-4o-mini", timeout=10.0)
    client = LLMClient(config=cfg)

    call_count = 0

    def always_429(req, timeout=None):
        nonlocal call_count
        call_count += 1
        raise _http_error(429)

    with patch("kestrel.llm.time.sleep"), \
         patch("urllib.request.urlopen", side_effect=always_429):
        with pytest.raises(RuntimeError, match="429"):
            client.complete("Hello?")

    # Should have attempted MAX_RETRIES + 1 times total.
    assert call_count == MAX_RETRIES + 1


# ---------------------------------------------------------------------------
# 3. 503 is also retried
# ---------------------------------------------------------------------------


def test_503_triggers_retry_and_succeeds():
    """HTTP 503 is in the retryable set and should also be retried."""
    from kestrel.llm import LLMClient, LLMConfig

    cfg = LLMConfig(api_key="sk-test", base_url="https://api.openai.com/v1",
                    model="gpt-4o-mini", timeout=10.0)
    client = LLMClient(config=cfg)

    call_count = 0

    def fake_urlopen(req, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _http_error(503)
        return _fake_response(_OK_BODY)

    with patch("kestrel.llm.time.sleep"), \
         patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = client.complete("Hello?")

    assert call_count == 2
    assert "42" in result


# ---------------------------------------------------------------------------
# 4. Non-retryable errors are raised immediately (no retry)
# ---------------------------------------------------------------------------


def test_404_raises_immediately_without_retry():
    """HTTP 404 is not retryable; must raise RuntimeError on first attempt."""
    from kestrel.llm import LLMClient, LLMConfig

    cfg = LLMConfig(api_key="sk-test", base_url="https://api.openai.com/v1",
                    model="gpt-4o-mini", timeout=10.0)
    client = LLMClient(config=cfg)

    call_count = 0

    def fake_urlopen(req, timeout=None):
        nonlocal call_count
        call_count += 1
        raise _http_error(404, "Not found")

    with patch("kestrel.llm.time.sleep") as mock_sleep, \
         patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with pytest.raises(RuntimeError, match="404"):
            client.complete("Hello?")

    assert call_count == 1, "404 should not be retried"
    mock_sleep.assert_not_called()


def test_401_raises_immediately_without_retry():
    """HTTP 401 (bad key) must not be retried."""
    from kestrel.llm import LLMClient, LLMConfig

    cfg = LLMConfig(api_key="sk-bad", base_url="https://api.openai.com/v1",
                    model="gpt-4o-mini", timeout=10.0)
    client = LLMClient(config=cfg)
    call_count = 0

    def fake_urlopen(req, timeout=None):
        nonlocal call_count
        call_count += 1
        raise _http_error(401)

    with patch("kestrel.llm.time.sleep") as mock_sleep, \
         patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with pytest.raises(RuntimeError, match="401"):
            client.complete("Hello?")

    assert call_count == 1
    mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Token usage is captured
# ---------------------------------------------------------------------------


def test_token_usage_captured_after_success():
    """last_usage should reflect the usage dict from the API response."""
    from kestrel.llm import LLMClient, LLMConfig

    cfg = LLMConfig(api_key="sk-test", base_url="https://api.openai.com/v1",
                    model="gpt-4o-mini", timeout=10.0)
    client = LLMClient(config=cfg)

    with patch("urllib.request.urlopen", return_value=_fake_response(_OK_BODY)):
        client.complete("Hello?")

    assert client.last_usage is not None
    assert client.last_usage.get("total_tokens") == 15


def test_usage_is_none_before_any_call():
    from kestrel.llm import LLMClient, LLMConfig

    cfg = LLMConfig(api_key="sk-test", base_url="https://api.openai.com/v1",
                    model="gpt-4o-mini", timeout=10.0)
    assert LLMClient(config=cfg).last_usage is None


# ---------------------------------------------------------------------------
# 6. max_tokens is included in the request payload
# ---------------------------------------------------------------------------


def test_max_tokens_included_in_payload():
    """max_tokens must appear in the JSON payload sent to the API."""
    from kestrel.llm import LLMClient, LLMConfig, DEFAULT_MAX_TOKENS

    cfg = LLMConfig(api_key="sk-test", base_url="https://api.openai.com/v1",
                    model="gpt-4o-mini", timeout=10.0)
    client = LLMClient(config=cfg)

    captured: list[bytes] = []

    def fake_urlopen(req, timeout=None):
        captured.append(req.data)
        return _fake_response(_OK_BODY)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        client.complete("Hello?", max_tokens=512)

    payload = json.loads(captured[0])
    assert payload["max_tokens"] == 512


def test_no_max_tokens_when_passed_none():
    """Passing max_tokens=None should omit the field from the payload."""
    from kestrel.llm import LLMClient, LLMConfig

    cfg = LLMConfig(api_key="sk-test", base_url="https://api.openai.com/v1",
                    model="gpt-4o-mini", timeout=10.0)
    client = LLMClient(config=cfg)
    captured: list[bytes] = []

    def fake_urlopen(req, timeout=None):
        captured.append(req.data)
        return _fake_response(_OK_BODY)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        client.complete("Hello?", max_tokens=None)

    payload = json.loads(captured[0])
    assert "max_tokens" not in payload


# ---------------------------------------------------------------------------
# 7. Provider auto-detection
# ---------------------------------------------------------------------------


def test_provider_detection_groq(monkeypatch):
    """GROQ_API_KEY should select the Groq endpoint and default model."""
    from kestrel.llm import LLMConfig, _GROQ_BASE_URL, _GROQ_DEFAULT_MODEL

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test123")
    # Remove others so priority is unambiguous.
    for v in ("KESTREL_LLM_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.delenv("KESTREL_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("KESTREL_LLM_MODEL", raising=False)

    cfg = LLMConfig.from_env()
    assert cfg.provider == "groq"
    assert cfg.base_url == _GROQ_BASE_URL
    assert cfg.model == _GROQ_DEFAULT_MODEL
    assert cfg.api_key == "gsk_test123"
    assert cfg.configured is True


def test_provider_detection_gemini(monkeypatch):
    """GEMINI_API_KEY should select the Gemini endpoint and default model."""
    from kestrel.llm import LLMConfig, _GEMINI_BASE_URL, _GEMINI_DEFAULT_MODEL

    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy_test")
    for v in ("KESTREL_LLM_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.delenv("KESTREL_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("KESTREL_LLM_MODEL", raising=False)

    cfg = LLMConfig.from_env()
    assert cfg.provider == "gemini"
    assert cfg.base_url == _GEMINI_BASE_URL
    assert cfg.model == _GEMINI_DEFAULT_MODEL
    assert cfg.configured is True


def test_provider_detection_groq_beats_gemini(monkeypatch):
    """KESTREL > GROQ > GEMINI priority: when both GROQ and GEMINI set, Groq wins."""
    from kestrel.llm import LLMConfig

    monkeypatch.setenv("GROQ_API_KEY", "gsk_abc")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza_abc")
    for v in ("KESTREL_LLM_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.delenv("KESTREL_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("KESTREL_LLM_MODEL", raising=False)

    cfg = LLMConfig.from_env()
    assert cfg.provider == "groq"


def test_provider_detection_no_key_is_unconfigured(monkeypatch):
    """No API keys → configured is False, provider is 'none'."""
    from kestrel.llm import LLMConfig

    for v in ("KESTREL_LLM_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY",
              "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(v, raising=False)

    cfg = LLMConfig.from_env()
    assert cfg.configured is False
    assert cfg.provider == "none"


def test_provider_detection_kestrel_override_beats_groq(monkeypatch):
    """KESTREL_LLM_API_KEY has highest priority."""
    from kestrel.llm import LLMConfig

    monkeypatch.setenv("KESTREL_LLM_API_KEY", "kestrel-key")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_abc")
    monkeypatch.delenv("KESTREL_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("KESTREL_LLM_MODEL", raising=False)

    cfg = LLMConfig.from_env()
    assert cfg.provider == "custom"
    assert cfg.api_key == "kestrel-key"


# ---------------------------------------------------------------------------
# 8. LLMNotConfigured when no key
# ---------------------------------------------------------------------------


def test_complete_raises_not_configured_without_key():
    from kestrel.llm import LLMClient, LLMConfig, LLMNotConfigured

    cfg = LLMConfig(api_key=None, base_url="https://api.openai.com/v1",
                    model="x", timeout=10.0)
    with pytest.raises(LLMNotConfigured):
        LLMClient(config=cfg).complete("Hello?")
