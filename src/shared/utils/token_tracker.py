"""
Token Usage Tracker

Request-scoped token usage aggregation for all LLM calls across the pipeline.
Uses Python's ContextVar so the tracker threads through async tasks without
polluting any function signatures.

Usage
-----
# At pipeline entry point (e.g. process_document / run_validation):
    tracker = create_tracker()

# Any code deeper in the stack can record tokens:
    record_tokens(step="document_extraction", provider="anthropic",
                  model="claude-sonnet-4-6", input_tokens=8200, output_tokens=1400)

# At the end, retrieve the summary:
    summary = tracker.get_summary()
    # -> {"total_input_tokens": ..., "total_output_tokens": ...,
    #     "estimated_cost_usd": ..., "breakdown": [...]}
"""

from __future__ import annotations

import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Cost table — price per ONE MILLION tokens (USD)
# Keep sorted alphabetically for readability; prefix-match is used as fallback.
# ---------------------------------------------------------------------------
_COST_PER_MILLION: Dict[str, Tuple[float, float]] = {
    # Anthropic ─ (input, output)
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-haiku-4-5": (0.25, 1.25),
    "claude-haiku-4-5-20251001": (0.25, 1.25),
    "claude-opus-4-6": (15.00, 75.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    # Google Gemini
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-flash-exp": (0.10, 0.40),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.00),
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated USD cost for a single LLM call."""
    # Exact match first
    model_lower = model.lower()
    rates = _COST_PER_MILLION.get(model_lower)

    # Prefix match fallback (handles versioned model IDs)
    if rates is None:
        for key, value in _COST_PER_MILLION.items():
            if model_lower.startswith(key) or key.startswith(model_lower.split("-20")[0]):
                rates = value
                break

    if rates is None:
        return 0.0  # Unknown model — cost unknown

    input_cost = (input_tokens / 1_000_000) * rates[0]
    output_cost = (output_tokens / 1_000_000) * rates[1]
    return round(input_cost + output_cost, 6)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TokenRecord:
    """A single LLM call's token usage."""
    step: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "step": self.step,
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "cost_usd": self.cost_usd,
        }


class TokenUsageTracker:
    """
    Accumulates token usage records for a single pipeline run.

    Thread-safe for asyncio concurrent tasks sharing the same context.
    """

    def __init__(self) -> None:
        self._records: List[TokenRecord] = []

    def record(
        self,
        step: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record token usage from one LLM call."""
        cost = _estimate_cost(model, input_tokens, output_tokens)
        self._records.append(
            TokenRecord(
                step=step,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            )
        )

    def get_summary(self) -> Dict:
        """Return aggregated token usage summary."""
        total_input = sum(r.input_tokens for r in self._records)
        total_output = sum(r.output_tokens for r in self._records)
        total_cost = sum(r.cost_usd for r in self._records)

        # Per-model rollup
        by_model: Dict[str, Dict] = {}
        for r in self._records:
            key = f"{r.provider}/{r.model}"
            if key not in by_model:
                by_model[key] = {
                    "provider": r.provider,
                    "model": r.model,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "calls": 0,
                }
            by_model[key]["input_tokens"] += r.input_tokens
            by_model[key]["output_tokens"] += r.output_tokens
            by_model[key]["total_tokens"] += r.input_tokens + r.output_tokens
            by_model[key]["cost_usd"] += r.cost_usd
            by_model[key]["calls"] += 1

        return {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "estimated_cost_usd": round(total_cost, 6),
            "call_count": len(self._records),
            "by_model": list(by_model.values()),
            "breakdown": [r.to_dict() for r in self._records],
        }

    @property
    def records(self) -> List[TokenRecord]:
        return list(self._records)


# ---------------------------------------------------------------------------
# Context-var based request scope
# ---------------------------------------------------------------------------

_current_tracker: ContextVar[Optional[TokenUsageTracker]] = ContextVar(
    "token_tracker", default=None
)

_current_step: ContextVar[str] = ContextVar("token_tracker_step", default="unknown")


def create_tracker() -> TokenUsageTracker:
    """
    Create a new tracker and install it as the current request-scoped tracker.

    Returns the tracker so the caller can retrieve the summary after the
    pipeline run completes.
    """
    tracker = TokenUsageTracker()
    _current_tracker.set(tracker)
    return tracker


def get_current_tracker() -> Optional[TokenUsageTracker]:
    """Return the active tracker for the current async context, or None."""
    return _current_tracker.get()


def set_step(step_name: str) -> None:
    """Label the current pipeline step so subsequent LLM calls are tagged."""
    _current_step.set(step_name)


def get_step() -> str:
    """Return the current pipeline step label."""
    return _current_step.get()


def aggregate_token_usages(usages: list) -> dict:
    """
    Merge multiple token-usage summary dicts (e.g. one per extracted document
    plus one for the validation workflow) into a single combined summary.

    Args:
        usages: List of dicts returned by ``TokenUsageTracker.get_summary()``.
                None / empty items are silently skipped.

    Returns:
        Combined summary dict in the same shape as ``get_summary()``.
    """
    combined = TokenUsageTracker()
    for usage in usages:
        if not usage:
            continue
        for record in usage.get("breakdown", []):
            combined.record(
                step=record.get("step", "unknown"),
                provider=record.get("provider", "unknown"),
                model=record.get("model", "unknown"),
                input_tokens=record.get("input_tokens", 0),
                output_tokens=record.get("output_tokens", 0),
            )
    return combined.get_summary()


def record_tokens(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    step: Optional[str] = None,
) -> None:
    """
    Record token usage into the active tracker (no-op if no tracker is set).

    Args:
        provider:      Provider name, e.g. "anthropic", "google", "openai"
        model:         Model ID, e.g. "claude-sonnet-4-6"
        input_tokens:  Number of prompt/input tokens consumed
        output_tokens: Number of completion/output tokens generated
        step:          Pipeline step label; defaults to the current ContextVar step
    """
    tracker = get_current_tracker()
    if tracker is None:
        return
    effective_step = step or get_step()
    tracker.record(
        step=effective_step,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
