"""Chat Completions transport of the host bridge.

The deepseek-chat dialect is OpenAI chat completions with tools plus thinking: every request carries
"thinking": {"type": "enabled"} and "reasoning_effort", and each assistant turn's reasoning_content is sent back
upstream. The tasks were validated with Kimi K3 (effort high) through such an endpoint.
The openai-chat protocol sends standard Chat Completions fields, including
reasoning_effort and max_completion_tokens, without thinking or reasoning_content.

The model, effort and endpoint are bridge configuration, not part of a frozen bundle. Credentials never
enter observations or logs.
"""
import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

PROTOCOLS = {"deepseek-chat", "openai-chat"}


class ModelError(RuntimeError):
    pass


class BudgetExceeded(ModelError):
    """The evaluator's own call or token budget is used up (never caused by provider trouble)."""


class ProviderUnavailable(ModelError):
    """The provider or the bridge did not answer within the request deadline; the run is invalid."""


@dataclass
class Budget:
    max_calls: int = 480
    max_tokens: int = 400_000
    calls: int = 0
    tokens: int = 0


def _error_kind(exc):
    """' (<type or code>)' from a JSON error body, letters, digits and _.- only; '' when there is none."""
    try:
        body = json.loads(exc.read(65536) or b'{}')
        error = body.get('error') if isinstance(body, dict) else None
        kind = next((str(error[k]) for k in ('type', 'code') if isinstance(error, dict) and error.get(k)), '')
    except Exception:
        return ''
    kind = ''.join(c for c in kind if c.isascii() and (c.isalnum() or c in '_.-'))[:64]
    return f' ({kind})' if kind else ''


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ModelError("API redirect refused; configure the final trusted base URL")


def outgoing(message, *, protocol="openai-chat"):
    """Conversation entry as sent upstream.

    Thinking mode with tools requires every earlier reasoning_content to be
    returned; tool-call identities are reduced to the public request fields.
    """
    fields = ("role", "content", "tool_call_id")
    if protocol == "deepseek-chat":
        fields += ("reasoning_content",)
    item = {k: message[k] for k in fields if k in message}
    if message.get("tool_calls"):
        item["tool_calls"] = [{"id": c["id"], "type": "function", "function": {
            "name": c["function"]["name"], "arguments": c["function"]["arguments"]}} for c in message["tool_calls"]]
    return item


def explicit_enum_types(value):
    """Add equivalent primitive types to enums for providers requiring typed schemas."""
    if isinstance(value, list):
        return [explicit_enum_types(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: explicit_enum_types(item) for key, item in value.items()}
    choices = result.get('enum')
    if 'type' not in result and isinstance(choices, list) and choices:
        def primitive(item):
            if item is None: return 'null'
            if isinstance(item, bool): return 'boolean'
            if isinstance(item, str): return 'string'
            if isinstance(item, int): return 'integer'
            if isinstance(item, float): return 'number'
            return None
        kinds = {primitive(item) for item in choices}
        if kinds <= {'integer', 'number'}:
            result['type'] = 'number' if 'number' in kinds else 'integer'
        elif len(kinds) == 1 and None not in kinds:
            result['type'] = kinds.pop()
    return result


class ModelClient:
    def __init__(self, key, *, base_url, model="kimi-k3", effort="high", max_tokens=16384,
                 timeout=180, budget=None, protocol="openai-chat"):
        parsed = urllib.parse.urlsplit(base_url or "")
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("base URL must be an HTTPS URL without credentials, query or fragment")
        if not key or any(c in key for c in "\r\n"):
            raise ValueError("missing or malformed API credential")
        if protocol not in PROTOCOLS:
            raise ValueError("unsupported API protocol")
        self._key = key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.budget = budget or Budget()
        self.protocol = protocol
        self.opener = urllib.request.build_opener(NoRedirect())

    def complete(self, messages, tools, *, timeout=None):
        if self.budget.calls >= self.budget.max_calls or self.budget.tokens >= self.budget.max_tokens:
            raise BudgetExceeded("run model budget exhausted")
        # Send the explicitly configured effort in either protocol.
        wire_tools = explicit_enum_types(tools) if self.protocol == 'openai-chat' else tools
        payload = {"model": self.model, "messages": [outgoing(m, protocol=self.protocol) for m in messages], "tools": wire_tools,
                   "tool_choice": "auto", "stream": False,
                   "reasoning_effort": self.effort}
        token_limit = min(self.max_tokens, self.budget.max_tokens - self.budget.tokens)
        if self.protocol == "deepseek-chat":
            payload.update(max_tokens=token_limit, thinking={"type": "enabled"})
        else:
            payload["max_completion_tokens"] = token_limit
        req = urllib.request.Request(self.base_url + "/chat/completions",
                                     data=json.dumps(payload).encode(),
                                     headers={"Authorization": "Bearer " + self._key,
                                              "Content-Type": "application/json",
                                              "User-Agent": "program-bench-pro-verifier/1.0.0"})
        self.budget.calls += 1
        started = time.monotonic()
        try:
            with self.opener.open(req, timeout=min(self.timeout, timeout or self.timeout)) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            # Do not log arbitrary upstream bodies; they can echo requests/credentials. Only the error type or
            # code of a JSON error body is reported, reduced to a short identifier.
            raise ModelError(f"model HTTP {exc.code} at {urllib.parse.urlsplit(self.base_url).netloc}"
                             + _error_kind(exc)) from None
        except (OSError, ValueError, http.client.HTTPException) as exc:
            # Includes truncated bodies (IncompleteRead) and dropped connections.
            raise ModelError(f"model transport failed ({type(exc).__name__})") from None
        usage = data.get("usage") or {}
        tokens = usage.get("total_tokens")
        if type(tokens) is not int or tokens < 0:
            # Guessing only output tokens can silently remove the input budget.
            raise ModelError("model response has no valid total-token accounting")
        self.budget.tokens += tokens
        try:
            choice = data["choices"][0]
            message = choice["message"]
            if not isinstance(message, dict):
                raise ValueError()
        except (KeyError, IndexError, TypeError, ValueError):
            raise ModelError("model response has no assistant message") from None
        allowed = outgoing({**message, "role": "assistant"}, protocol=self.protocol)
        allowed.setdefault("content", "")
        return allowed, {"total_tokens": tokens, "prompt_tokens": usage.get("prompt_tokens"),
                         "completion_tokens": usage.get("completion_tokens"),
                         "cached_tokens": usage.get("prompt_cache_hit_tokens"),
                         "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                         "finish_reason": choice.get("finish_reason"),
                         "model": data.get("model", self.model),
                         "system_fingerprint": data.get("system_fingerprint"),
                         "upstream_seconds": round(time.monotonic() - started, 3)}


def credential(path=None, variable="VERIFIER_API_KEY"):
    if path:
        from pathlib import Path
        p = Path(path)
        if not p.is_file() or p.stat().st_mode & 0o077:
            raise ValueError("credential file must be a regular owner-only file (chmod 600)")
        return p.read_text().strip()
    return os.environ.get(variable, "").strip()
