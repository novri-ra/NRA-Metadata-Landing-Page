# ponytail: rough estimation based on average vision API cost. Per-model pricing if multi-model scales.


class APITracker:
    def __init__(self):
        self.calls = 0
        self.estimated_cost_usd = 0.0
        self.estimated_tokens = 0

    def add_call(self):
        self.calls += 1
        # average cost per vision request (Gemini/OpenAI) roughly $0.002
        self.estimated_cost_usd += 0.002
        # rough estimate ~1000 tokens per vision call (prompt+response)
        self.estimated_tokens += 1000


tracker = APITracker()
