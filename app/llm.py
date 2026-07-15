"""Anthropic client + the one structured-output helper all LLM steps use.

Structured outputs via client.messages.parse() (GA, no beta header): the
response is guaranteed to validate against the given Pydantic model, so the
pipeline needs no JSON-repair or retry logic (ADR #6). The plan/letter
models (Opus 4.8) take no sampling parameters; steering happens purely via
the prompts in app/prompts/.

Prompt caching: every system block carries a cache_control marker, and the
call sites order blocks stable-first — the profile pool comes FIRST (byte-
identical across match/plan/letter/revise), the step prompt second, the
volatile posting last in the user message. Within one pipeline run the
first pool-carrying step writes the cache and the following steps read it;
repeated runs inside the TTL reuse both blocks. USAGE_LOG records per-call
token/cache metrics for verification and cost reporting.
"""

from functools import cache
from pathlib import Path

from anthropic import Anthropic, APIConnectionError, APIStatusError
from pydantic import BaseModel

from app.config import load_dotenv, model_for

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_MAX_TOKENS = 16000

# one dict per API call: step, model, input/output/cache token counts
USAGE_LOG: list[dict] = []


def reset_usage_log() -> None:
    USAGE_LOG.clear()


class LLMError(Exception):
    """The Anthropic API failed or returned no parseable structured output.

    Wraps SDK exceptions so every surface (CLI stderr, web 502) shows the
    actual API message — e.g. an exhausted credit balance — instead of an
    unhandled 500."""


def load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


@cache
def _client() -> Anthropic:
    load_dotenv()  # ANTHROPIC_API_KEY from .env unless already exported
    return Anthropic()


def call_structured[TModel: BaseModel](
    step: str, system_blocks: list[str], user: str, output_type: type[TModel]
) -> TModel:
    """One structured LLM call: system blocks + user message → validated model."""
    # every stable block is a breakpoint (max 4 allowed; we use <= 2):
    # a shared first block (profile pool) yields cache reads across steps
    system: list[dict] = [
        {"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}
        for text in system_blocks
    ]
    model = model_for(step)
    try:
        response = _client().messages.parse(
            model=model,
            max_tokens=_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=output_type,
        )
    except APIStatusError as exc:
        message = exc.body.get("error", {}).get("message", str(exc)) \
            if isinstance(exc.body, dict) else str(exc)
        raise LLMError(f"Anthropic API ({exc.status_code}): {message}") from exc
    except APIConnectionError as exc:
        raise LLMError(f"Keine Verbindung zur Anthropic API: {exc}") from exc
    usage = response.usage
    USAGE_LOG.append({
        "step": step,
        "model": model,
        "input_tokens": usage.input_tokens,
        "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
        "output_tokens": usage.output_tokens,
    })

    parsed = response.parsed_output
    if parsed is None:
        raise LLMError(f"{step}: no structured output (stop_reason={response.stop_reason})")
    return parsed
