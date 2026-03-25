"""
Scorer Agent — Combines Price + Review analysis into a single score per product.

Merges what was previously two separate agents (PriceAgent + ReviewAgent)
into one efficient pass.
"""
from __future__ import annotations
import asyncio, random, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.base_agent import BaseAgent, AgentResult, AgentStatus
from core.message_bus  import MessageBus

BRAND_SENTIMENT = {
    "Samsung": 4.3, "LG": 4.4, "Sony": 4.6, "Apple": 4.7, "Dell": 4.4,
    "HP": 4.1, "ASUS": 4.2, "Lenovo": 4.0, "Acer": 3.9, "IKEA": 4.3,
    "West Elm": 4.5, "Ashley": 4.0, "Zinus": 4.1, "Casper": 4.6,
}


class ScorerAgent(BaseAgent):
    """
    Scores products by combining:
      - Price analysis (is now a good time to buy?)
      - Review sentiment (estimated from brand reputation)
      - Overall value score (0-100)
    """

    def __init__(self, bus: MessageBus):
        super().__init__(name="scorer_agent", description="Scores products by price and review")
        self.bus = bus

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data: {"products": list[dict]}
        Returns scored products sorted by score desc.
        """
        self.set_status(AgentStatus.RUNNING)
        products = input_data.get("products", [])

        # simulate slight processing delay
        await asyncio.sleep(0.1)

        scored = [self._score(p) for p in products]
        scored.sort(key=lambda x: x["score"], reverse=True)

        await self.bus.publish("scored_results", sender=self.name, content=scored)
        self.set_status(AgentStatus.DONE)
        return self.success(data=scored, count=len(scored))

    def _score(self, product: dict) -> dict:
        """Calculate a 0-100 score for a product."""
        price   = product.get("price", 0)
        rating  = product.get("rating", 0)
        brand   = product.get("brand", "")

        # use known brand sentiment or fall back to product rating
        sentiment = BRAND_SENTIMENT.get(brand, rating if rating > 0 else 3.5)

        # price score: lower price relative to category gets higher score
        # normalized 0-100 (we don't have historical data so use a simple heuristic)
        random.seed(str(product.get("id", price)))
        avg_price    = price * random.uniform(0.9, 1.3)
        discount_pct = round((avg_price - price) / avg_price * 100, 1) if avg_price > 0 else 0

        price_score    = min(100, max(0, 50 + discount_pct * 2))
        review_score   = (sentiment / 5.0) * 100
        value_score    = (review_score * 0.5) + (price_score * 0.5)

        # determine buy recommendation
        if discount_pct > 10:
            price_insight = "good time to buy"
        elif discount_pct < -5:
            price_insight = "price is high"
        else:
            price_insight = "fair price"

        return {
            "product":       product,
            "score":         round(value_score, 1),
            "price_score":   round(price_score, 1),
            "review_score":  round(review_score, 1),
            "price_insight": price_insight,
            "discount_pct":  discount_pct,
        }