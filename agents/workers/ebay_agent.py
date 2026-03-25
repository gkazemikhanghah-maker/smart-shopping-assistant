"""
eBay Agent — Searches real eBay listings using Browse API.

Uses Client Credentials (App ID + Cert ID) — no OAuth needed.
"""
from __future__ import annotations
import asyncio, base64, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import httpx
from agents.base_agent import BaseAgent, AgentResult, AgentStatus, Message
from core.message_bus  import MessageBus
from config            import EBAY_APP_ID, EBAY_CERT_ID

EBAY_TOKEN_URL  = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

# map item keywords to specific eBay search queries
QUERY_MAP = {
    "mirror":       "bedroom wall mirror full length",
    "rug":          "area rug bedroom",
    "lamp":         "floor lamp",
    "curtain":      "window curtain panel",
    "nightstand":   "nightstand bedside table",
    "tv stand":     "tv stand entertainment center",
    "tv":           "smart tv 4k",
    "sofa":         "sofa couch living room",
    "coffee table": "coffee table living room",
}


class EbayAgent(BaseAgent):
    """Searches eBay using Browse API with Client Credentials auth."""

    def __init__(self, bus: MessageBus):
        super().__init__(name="ebay_agent", description="Real eBay product search")
        self.bus        = bus
        self._token     = None
        self._token_exp = 0

    async def run(self, input_data: dict) -> AgentResult:
        """
        input_data: {
            "query":  str,
            "style":  str | None,
            "budget": int | None,
            "limit":  int (default 10)
        }
        """
        self.set_status(AgentStatus.RUNNING)

        query  = input_data.get("query", "").lower().strip()
        style  = input_data.get("style", "")
        budget = input_data.get("budget")
        limit  = input_data.get("limit", 10)

        if not EBAY_APP_ID or not EBAY_CERT_ID:
            self.set_status(AgentStatus.FAILED)
            return self.failure("EBAY_APP_ID or EBAY_CERT_ID not set in .env")

        try:
            token         = await self._get_token()
            ebay_query    = self._build_query(query, style)
            results       = await self._search(token, ebay_query, budget, limit)

            await self.bus.publish("search_results", sender=self.name, content=results)
            self.set_status(AgentStatus.DONE)
            return self.success(data=results, query=ebay_query, count=len(results), source="ebay")

        except Exception as e:
            self.logger.error(f"eBay search failed: {e}")
            self.set_status(AgentStatus.FAILED)
            return self.failure(str(e))

    def _build_query(self, item: str, style: str) -> str:
        """Build a specific eBay query from item name and style."""
        # check QUERY_MAP for better search terms
        for key, mapped in QUERY_MAP.items():
            if key in item:
                return f"{style} {mapped}".strip() if style else mapped
        # default: add style prefix
        return f"{style} {item}".strip() if style else item

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        credentials = base64.b64encode(f"{EBAY_APP_ID}:{EBAY_CERT_ID}".encode()).decode()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                EBAY_TOKEN_URL,
                headers={
                    "Content-Type":  "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {credentials}",
                },
                data={
                    "grant_type": "client_credentials",
                    "scope":      "https://api.ebay.com/oauth/api_scope",
                },
            )
            r.raise_for_status()
            data = r.json()
        self._token     = data["access_token"]
        self._token_exp = int(time.time()) + data.get("expires_in", 7200)
        self.logger.info("eBay token obtained")
        return self._token

    async def _search(self, token: str, query: str, budget: int | None, limit: int) -> list[dict]:
        filters = "conditionIds:{1000|1500|2000|2500}"
        if budget:
            filters += f",price:[0..{int(budget)}],priceCurrency:USD"
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                EBAY_SEARCH_URL,
                headers={
                    "Authorization":           f"Bearer {token}",
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                },
                params={"q": query, "limit": limit, "sort": "relevance", "filter": filters},
            )
            r.raise_for_status()
            data = r.json()
        items = data.get("itemSummaries", [])
        self.logger.info(f"eBay: {len(items)} results for '{query}'")
        return [self._normalize(p) for p in items]

    def _normalize(self, p: dict) -> dict:
        price = float(p.get("price", {}).get("value", 0))
        # extract brand from aspects
        brand = "Unknown"
        for aspect in p.get("localizedAspects", []):
            if aspect.get("name", "").lower() in ("brand", "manufacturer"):
                brand = aspect.get("value", "Unknown")
                break
        if brand == "Unknown":
            brand = p.get("title", "").split()[0]
        return {
            "id":          p.get("itemId", ""),
            "name":        p.get("title", ""),
            "price":       round(price, 2),
            "brand":       brand,
            "category":    p.get("categoryPath", ""),
            "rating":      min(5.0, float(p.get("seller", {}).get("feedbackPercentage", "0").rstrip("%") or 0) / 20),
            "description": p.get("shortDescription", ""),
            "thumbnail":   p.get("image", {}).get("imageUrl", ""),
            "url":         p.get("itemWebUrl", ""),
            "condition":   p.get("condition", "New"),
            "source":      "ebay",
            "specs":       {
                "seller":   p.get("seller", {}).get("username", ""),
                "shipping": p.get("shippingOptions", [{}])[0].get("shippingCost", {}).get("value", "0") if p.get("shippingOptions") else "0",
            }
        }