"""
All tests — run with: python tests/test_all.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent            import BaseAgent, AgentResult, AgentStatus, Message
from agents.workers.scorer_agent  import ScorerAgent
from core.message_bus             import MessageBus


# ── Base Agent ────────────────────────────────────────────────────────────────

class EchoAgent(BaseAgent):
    async def run(self, input_data) -> AgentResult:
        self.set_status(AgentStatus.RUNNING)
        self.set_status(AgentStatus.DONE)
        return self.success(data=f"Echo: {input_data}")


async def test_base_agent():
    print("-- Test: Base Agent")
    agent  = EchoAgent(name="echo")
    result = await agent.run("hello")
    assert result.success and result.data == "Echo: hello"
    print("  PASS")


# ── Message Bus ───────────────────────────────────────────────────────────────

async def test_message_bus():
    print("-- Test: Message Bus")
    bus = MessageBus()
    await bus.publish("ch1", "agent_a", {"data": 1})
    await bus.publish("ch1", "agent_b", {"data": 2})
    await bus.publish("ch2", "agent_a", {"data": 3})

    assert len(bus.get_messages("ch1")) == 2
    assert len(bus.get_messages("ch2")) == 1
    assert bus.get_latest("ch1").content["data"] == 2
    bus.clear_all()
    assert len(bus.get_messages("ch1")) == 0
    print("  PASS")


# ── Scorer Agent ──────────────────────────────────────────────────────────────

async def test_scorer():
    print("-- Test: Scorer Agent")
    bus   = MessageBus()
    agent = ScorerAgent(bus)

    products = [
        {"id": "1", "name": "Laptop A", "price": 599, "brand": "ASUS",   "rating": 4.2},
        {"id": "2", "name": "Laptop B", "price": 999, "brand": "Apple",  "rating": 4.7},
        {"id": "3", "name": "Laptop C", "price": 399, "brand": "Lenovo", "rating": 4.0},
    ]
    result = await agent.run({"products": products})
    assert result.success
    assert len(result.data) == 3
    # should be sorted by score
    scores = [p["score"] for p in result.data]
    assert scores == sorted(scores, reverse=True)
    print(f"  PASS  ({len(result.data)} products scored)")
    for p in result.data:
        print(f"    {p['product']['name']:12}  score:{p['score']:5.1f}  {p['price_insight']}")


# ── eBay Auth ─────────────────────────────────────────────────────────────────

async def test_ebay_auth():
    print("-- Test: eBay Auth")
    from config import EBAY_APP_ID, EBAY_CERT_ID
    if not EBAY_APP_ID or not EBAY_CERT_ID:
        print("  SKIP  (EBAY credentials not set)")
        return

    bus   = MessageBus()
    from agents.workers.ebay_agent import EbayAgent
    agent = EbayAgent(bus)
    token = await agent._get_token()
    assert token and len(token) > 50
    print(f"  PASS  (token: {token[:30]}...)")


# ── eBay Search ───────────────────────────────────────────────────────────────

async def test_ebay_search():
    print("-- Test: eBay Search")
    from config import EBAY_APP_ID, EBAY_CERT_ID
    if not EBAY_APP_ID or not EBAY_CERT_ID:
        print("  SKIP  (EBAY credentials not set)")
        return

    bus   = MessageBus()
    from agents.workers.ebay_agent import EbayAgent
    agent = EbayAgent(bus)

    result = await agent.run({"query": "sofa couch", "budget": 1000, "limit": 3})
    assert result.success
    assert len(result.data) > 0
    assert result.data[0]["source"] == "ebay"
    print(f"  PASS  ({len(result.data)} results)")
    for p in result.data:
        print(f"    ${p['price']:8.2f}  {p['name'][:50]}")


# ── Run all ───────────────────────────────────────────────────────────────────

async def main():
    print("=" * 50)
    print("  Smart Shopping Assistant — All Tests")
    print("=" * 50)

    await test_base_agent()
    await test_message_bus()
    await test_scorer()
    await test_ebay_auth()
    await test_ebay_search()

    print("\n" + "=" * 50)
    print("  ALL TESTS PASSED")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())