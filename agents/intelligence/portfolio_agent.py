"""
Portfolio Optimizer Agent — Finds the best product combinations within budget.

Uses Claude API to analyze scored products and suggest 3 optimized bundles.
"""
from __future__ import annotations
import asyncio, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import anthropic
from agents.base_agent import BaseAgent, AgentResult, AgentStatus
from core.message_bus  import MessageBus
from config            import ANTHROPIC_API_KEY, MODEL_NAME

SYSTEM_PROMPT = """You are a smart shopping portfolio optimizer.

Given a total budget and scored products for each item category, suggest 3 optimized purchase combinations.

Rules:
- Every combination MUST have total cost <= total_budget
- Each combination must include exactly one product per category
- The product you pick MUST actually be that category item (e.g. "sofa" pick must be an actual sofa, not a tapestry or decoration)
- If a product name doesn't match the category, skip it and pick the next best
- Suggest meaningfully different combinations
- Keep explanations concise (1-2 sentences max)
- Respond with valid JSON only. No extra text."""


class PortfolioAgent(BaseAgent):
    """Finds 3 best product combinations within budget using Claude API."""

    def __init__(self, bus: MessageBus):
        super().__init__(name="portfolio_agent", description="Optimizes product combinations within budget")
        self.bus    = bus
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data: {
            "budget":     int,
            "style":      str,
            "items_data": {"sofa": [scored_products], "tv": [...], ...}
        }
        """
        self.set_status(AgentStatus.RUNNING)

        budget     = input_data.get("budget", 0)
        style      = input_data.get("style", "")
        items_data = input_data.get("items_data", {})

        if not items_data:
            return self.failure("No product data provided")

        try:
            result = await asyncio.to_thread(self._optimize, budget, style, items_data)
            await self.bus.publish("portfolio_results", sender=self.name, content=result)
            self.set_status(AgentStatus.DONE)
            return self.success(data=result)
        except Exception as e:
            self.set_status(AgentStatus.FAILED)
            return self.failure(f"Optimization failed: {str(e)}")

    def _optimize(self, budget: int, style: str, items_data: dict) -> dict:
        # top 5 per category for Claude
        summary = {}
        for item, products in items_data.items():
            sorted_p = sorted(products, key=lambda p: p.get("score", 0), reverse=True)
            summary[item] = [
                {
                    "id":    p["product"].get("id", ""),
                    "name":  p["product"].get("name", "")[:40],
                    "price": p["product"].get("price", 0),
                    "score": p.get("score", 0),
                    "url":   p["product"].get("url", ""),
                }
                for p in sorted_p[:4]
            ]

        prompt = f"""Total budget: ${budget:,}
Style: {style or "no preference"}

Products per category:
{json.dumps(summary, indent=2)}

Suggest exactly 3 purchase combinations. Each must:
1. Include one product from EVERY category
2. Have total <= ${budget:,}
3. Be meaningfully different

Return this JSON:
{{
  "options": [
    {{
      "name": "Balanced",
      "tagline": "Best overall value",
      "picks": {{
        "<category>": {{
          "id": "<id>",
          "name": "<name>",
          "price": <price>,
          "url": "<url>",
          "reason": "<one short reason>"
        }}
      }},
      "total": <sum>,
      "savings": <budget - total>,
      "explanation": "<1-2 sentences>"
    }},
    {{ "name": "Premium Pick", "tagline": "...", ... }},
    {{ "name": "Best Value", "tagline": "...", ... }}
  ]
}}"""

        response = self.client.messages.create(
            model=MODEL_NAME,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())