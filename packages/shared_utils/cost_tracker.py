"""Unified cost tracking for AI metadata calls (single source of truth).

Replaces the former ``tracker.py`` (a flat $0.002/call counter) and the
duplicate ``CostTracker`` instances that provider_router.py used to build.
One module singleton ``cost_tracker`` accumulates app-wide cost/tokens from
real provider token usage; batch code reads deltas off it.
"""

# Input/Output USD per 1k tokens by provider/model.
RATES = {
    "OpenAI": {"gpt-4o-mini": (0.00015, 0.0006), "gpt-4o": (0.005, 0.015)},
    "Gemini": {"gemini-1.5-flash": (0.000075, 0.0003)},
    "Mistral": {"mistral-large-latest": (0.002, 0.006)},
    "Groq": {"llama3-8b-8192": (0.00005, 0.00008)},
}
DEFAULT_RATE = (0.001, 0.002)

# ponytail: flat estimate for the vision prompt when a provider reports no
# token usage; revisit per-provider when usage becomes reliable everywhere.
IMAGE_TOKENS = 1000


class CostTracker:
    def __init__(self):
        self.estimated_cost_usd = 0.0
        self.estimated_tokens = 0
        self.last_cost = 0.0

    def rate_for(self, provider: str, model: str) -> tuple:
        return RATES.get(provider, {}).get(model, DEFAULT_RATE)

    def _add(self, provider, model, prompt_tokens, completion_tokens) -> float:
        in_rate, out_rate = self.rate_for(provider, model)
        cost = (
            prompt_tokens * in_rate / 1000.0
            + completion_tokens * out_rate / 1000.0
        )
        self.estimated_cost_usd += cost
        self.estimated_tokens += prompt_tokens + completion_tokens
        self.last_cost = cost
        return cost

    def record_usage(
        self, provider: str, model: str, prompt_tokens: int = 0, completion_tokens: int = 0
    ) -> float:
        """Accumulate one call from actual token usage (prompt*in + completion*out).

        When the provider reports no usage at all, falls back to the
        IMAGE_TOKENS estimate so a successful call is never recorded as $0.
        Returns the cost for this call.
        """
        if prompt_tokens <= 0 and completion_tokens <= 0:
            prompt_tokens = IMAGE_TOKENS
        return self._add(provider, model, prompt_tokens, completion_tokens)

    def calculate(
        self, provider: str, model: str, in_chars: int, out_chars: int
    ) -> float:
        """Estimate cost from character counts (1 token ~ 4 chars). Kept for
        callers/tests that don't have provider-reported usage."""
        in_tokens = max(1, in_chars // 4) + IMAGE_TOKENS
        out_tokens = max(1, out_chars // 4)
        return self._add(provider, model, in_tokens, out_tokens)


cost_tracker = CostTracker()