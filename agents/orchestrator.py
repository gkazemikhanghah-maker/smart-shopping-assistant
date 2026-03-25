"""
Orchestrator — Coordinates all agents end-to-end.

Two modes:
  - single: one product search (laptop, phone, sofa...)
  - multi:  multiple items with portfolio optimization
"""
from __future__ import annotations
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent                        import BaseAgent, AgentResult, AgentStatus
from agents.workers.ebay_agent                import EbayAgent
from agents.workers.scorer_agent              import ScorerAgent
from agents.intelligence.portfolio_agent      import PortfolioAgent
from core.message_bus                         import MessageBus

# keywords that indicate interior/multi-item requests
INTERIOR_KEYWORDS = ["room", "bedroom", "living room", "bathroom", "kitchen",
                     "furnish", "interior", "apartment", "decor"]


def detect_mode(query: str) -> str:
    """Detect if this is a single product or multi-item request."""
    q = query.lower()
    if any(kw in q for kw in INTERIOR_KEYWORDS):
        return "multi"
    return "single"


class Orchestrator(BaseAgent):
    """
    Coordinates agents for shopping requests.

    Single mode flow:
        eBay search → Score → Negotiate → Result

    Multi mode flow:
        eBay search (parallel) → Score (parallel) → Portfolio Optimizer → 3 Options
    """

    def __init__(self):
        super().__init__(name="orchestrator", description="Coordinates all agents")
        self.bus      = MessageBus()
        self.ebay     = EbayAgent(self.bus)
        self.scorer   = ScorerAgent(self.bus)
        self.portfolio = PortfolioAgent(self.bus)

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data: {
            "query":    str,
            "budget":   int,
            "user_id":  str (optional)
            "priorities": list (optional)
        }
        """
        self.set_status(AgentStatus.RUNNING)
        self.bus.clear_all()

        query  = input_data.get("query", "")
        budget = input_data.get("budget", 0)

        self.logger.info(f"Query: '{query}' | Budget: ${budget:,}")

        result = await self._run_single(query, budget,
                                        input_data.get("priorities", []))
        self.set_status(AgentStatus.DONE)
        return result

    async def run_multi(self, input_data: dict) -> AgentResult:
        """
        input_data: {
            "items":   ["sofa", "tv", "coffee table"],
            "budget":  5000,
            "style":   "modern",
            "user_id": "user_001"
        }
        """
        self.set_status(AgentStatus.RUNNING)
        self.bus.clear_all()

        items  = input_data.get("items", [])
        budget = input_data.get("budget", 0)
        style  = input_data.get("style", "")

        if not items:
            return self.failure("No items provided")

        self.logger.info(f"Multi-item: {items} | Budget: ${budget:,} | Style: {style}")

        # Step 1: search all items in parallel
        search_tasks = [
            self.ebay.run({"query": item, "style": style, "budget": None, "limit": 10})
            for item in items
        ]
        search_results = await asyncio.gather(*search_tasks)

        # Step 2: score each item's products in parallel
        score_tasks = []
        valid_items = []
        for i, item in enumerate(items):
            products = search_results[i].data if search_results[i].success else []
            if products:
                valid_items.append(item)
                score_tasks.append(self.scorer.run({"products": products}))

        scored_results = await asyncio.gather(*score_tasks)

        # Step 3: build items_data for portfolio optimizer
        items_data = {}
        for i, item in enumerate(valid_items):
            if scored_results[i].success:
                items_data[item] = scored_results[i].data

        if not items_data:
            return self.failure("No products found for any item")

        # Step 4: portfolio optimization
        portfolio_result = await self.portfolio.run({
            "budget":     budget,
            "style":      style,
            "items_data": items_data,
        })

        if not portfolio_result.success:
            return self.failure(portfolio_result.error)

        self.set_status(AgentStatus.DONE)
        return self.success(data={
            "mode":    "multi",
            "budget":  budget,
            "style":   style,
            "options": portfolio_result.data.get("options", []),
        })

    async def _run_single(self, query: str, budget: int, priorities: list) -> AgentResult:
        """Single product search pipeline."""

        # search
        search_result = await self.ebay.run({
            "query": query, "budget": None, "limit": 10
        })
        if not search_result.success or not search_result.data:
            return self.failure(f"No products found for '{query}'")

        # score
        scored_result = await self.scorer.run({"products": search_result.data})
        if not scored_result.success:
            return self.failure("Scoring failed")

        scored = scored_result.data

        # pick best within budget
        within = [s for s in scored if s["product"]["price"] <= budget] if budget else scored
        over   = [s for s in scored if s["product"]["price"] >  budget] if budget else []

        recommended = within[0] if within else None
        stretch     = None
        if not recommended and over:
            stretch = min(over, key=lambda s: s["product"]["price"])
        elif recommended and over:
            close = [s for s in over if s["product"]["price"] <= budget * 1.2]
            if close:
                stretch = close[0]

        message = self._build_message(recommended, stretch, budget, query)

        return self.success(data={
            "mode":          "single",
            "query":         query,
            "budget":        budget,
            "message":       message,
            "recommended":   recommended,
            "stretch":       stretch,
            "alternatives":  within[1:3] if within else [],
        })

    def _build_message(self, rec, stretch, budget, query) -> str:
        if rec:
            p = rec["product"]
            msg = f"Best match: {p['name'][:40]} at ${p['price']:,.2f}."
            if stretch:
                diff = stretch["product"]["price"] - budget
                msg += f" For ${diff:,.0f} more, consider {stretch['product']['name'][:30]}."
        elif stretch:
            p = stretch["product"]
            msg = f"Nothing within ${budget:,}. Closest: {p['name'][:40]} at ${p['price']:,.2f}."
        else:
            msg = f"No products found for '{query}'."
        return msg