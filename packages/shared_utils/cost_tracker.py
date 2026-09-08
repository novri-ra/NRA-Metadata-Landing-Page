class CostTracker:
    def __init__(self):
        self.estimated_cost_usd = 0.0
        # Estimates in USD per 1k tokens (Input, Output)
        self.RATES = {
            "OpenAI": {"gpt-4o-mini": (0.00015, 0.0006), "gpt-4o": (0.005, 0.015)},
            "Gemini": {"gemini-1.5-flash": (0.000075, 0.0003)},
            "Mistral": {"mistral-large-latest": (0.002, 0.006)},
            "9router": {"9router/auto": (0.0, 0.0)},
            "Groq": {"llama3-8b-8192": (0.00005, 0.00008)},
        }
        self.default_rate = (0.001, 0.002)

    def calculate(
        self, provider: str, model: str, in_chars: int, out_chars: int
    ) -> float:
        # 1 token ~ 4 chars approximation
        in_tokens = max(1, in_chars // 4)
        out_tokens = max(1, out_chars // 4)
        rates = self.RATES.get(provider, {}).get(model, self.default_rate)

        # Base image cost approximation (if visual) + text prompt
        # For simplicity, treating average image as 1000 input tokens
        in_tokens += 1000

        cost = (in_tokens / 1000.0) * rates[0] + (out_tokens / 1000.0) * rates[1]
        self.estimated_cost_usd += cost
        return cost
