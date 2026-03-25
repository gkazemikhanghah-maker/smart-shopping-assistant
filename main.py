"""
Smart Shopping Assistant — Main entry point.

Usage:
    python main.py         interactive mode
    python main.py --demo  quick demo
"""
import asyncio, os, sys
import anthropic
from agents.orchestrator import Orchestrator
from core.message_bus    import MessageBus
from config              import ANTHROPIC_API_KEY, MODEL_NAME


# ── Conversational profiler ───────────────────────────────────────────────────

PROFILER_SYSTEM = """You are a smart shopping assistant doing a quick intake interview.
Gather: (1) what they want, (2) budget, (3) style/preferences.

Ask ONE question at a time. Be warm and concise.

When ready, output ONLY JSON:

Single item:
{"ready": true, "mode": "single", "query": "laptop for programming", "budget": 700, "priorities": ["lightweight"], "notes": "..."}

Multiple items:
{"ready": true, "mode": "multi", "items": ["sofa", "coffee table", "tv"], "budget": 5000, "style": "modern", "notes": "..."}

No JSON until you have enough info."""


async def profile(client: anthropic.Anthropic, first_message: str) -> dict:
    """Chat with user to gather shopping requirements."""
    import json, re
    history = [{"role": "user", "content": first_message}]

    while True:
        response = client.messages.create(
            model=MODEL_NAME, max_tokens=300,
            system=PROFILER_SYSTEM, messages=history,
        )
        reply = response.content[0].text.strip()
        history.append({"role": "assistant", "content": reply})

        if '"ready": true' in reply or '"ready":true' in reply:
            match = re.search(r'\{.*\}', reply, re.DOTALL)
            if match:
                return json.loads(match.group())

        print(f"\n  Assistant: {reply}\n")
        try:
            user_input = input("  You: ").strip()
        except (KeyboardInterrupt, EOFError):
            return {}

        if user_input.lower() in ("quit", "exit", "q"):
            return {}

        history.append({"role": "user", "content": user_input})


# ── Output display ────────────────────────────────────────────────────────────

def sep():
    print("\n" + "─" * 55)


def show_single(result: dict):
    sep()
    rec  = result.get("recommended")
    str_ = result.get("stretch")
    alts = result.get("alternatives", [])

    print(f"\n  {result.get('message', '')}")

    if rec:
        p = rec["product"]
        print(f"\n  RECOMMENDED")
        print(f"    {p['name'][:55]}")
        print(f"    Price:  ${p['price']:,.2f}  |  Score: {rec['score']}/100")
        print(f"    {rec.get('price_insight', '')}")
        if p.get("url"):
            print(f"    {p['url'][:70]}")

    if str_:
        p = str_["product"]
        print(f"\n  STRETCH PICK")
        print(f"    {p['name'][:55]}  —  ${p['price']:,.2f}")
        if p.get("url"):
            print(f"    {p['url'][:70]}")

    if alts:
        print(f"\n  ALTERNATIVES")
        for a in alts:
            p = a["product"]
            print(f"    - {p['name'][:50]}  ${p['price']:,.2f}")

    sep()


def show_multi(result: dict):
    sep()
    budget  = result["budget"]
    options = result.get("options", [])

    print(f"\n  Shopping Plan  —  Budget: ${budget:,}")
    if result.get("style"):
        print(f"  Style: {result['style']}")

    for i, opt in enumerate(options):
        total   = opt.get("total", 0)
        savings = budget - total
        picks   = opt.get("picks", {})

        print(f"\n  Option {i+1} — {opt['name']}: {opt.get('tagline', '')}")
        print(f"  {opt.get('explanation', '')}")
        print(f"  Total: ${total:,.2f}  |  Savings: ${savings:,.2f}\n")

        for item, pick in picks.items():
            print(f"    {item.upper():20}  ${pick['price']:>8.2f}  {pick['name'][:45]}")
            if pick.get("reason"):
                print(f"    {'':20}  → {pick['reason']}")
            if pick.get("url"):
                print(f"    {'':20}  {pick['url'][:60]}")

        if i < len(options) - 1:
            print()

    sep()


# ── Interactive mode ──────────────────────────────────────────────────────────

async def interactive():
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    orch   = Orchestrator()

    print("=" * 55)
    print("  Smart Shopping Assistant")
    print("=" * 55)
    print("  Tell me what you're looking for.")
    print("  Type 'quit' to exit.")
    print("=" * 55)

    while True:
        print()
        try:
            first = input("  You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Goodbye!")
            break

        if not first or first.lower() in ("quit", "exit", "q"):
            print("\n  Goodbye!")
            break

        prof = await profile(client, first)
        if not prof:
            print("\n  Goodbye!")
            break

        mode   = prof.get("mode", "single")
        budget = prof.get("budget", 0)
        style  = prof.get("style", "")

        if mode == "multi":
            items = prof.get("items", [])
            print(f"\n  Searching {len(items)} items within ${budget:,}...")
            result = await orch.run_multi({
                "items": items, "budget": budget, "style": style, "user_id": "user_001"
            })
            if result.success:
                show_multi(result.data)
            else:
                print(f"\n  Error: {result.error}")
        else:
            query = prof.get("query", first)
            print(f"\n  Searching for: {query} (budget: ${budget:,})...")
            result = await orch.run({
                "query": query, "budget": budget,
                "priorities": prof.get("priorities", []), "user_id": "user_001"
            })
            if result.success:
                show_single(result.data)
            else:
                print(f"\n  Error: {result.error}")

        try:
            again = input("\n  Search for something else? (yes/no): ").strip().lower()
            if again not in ("yes", "y"):
                print("\n  Goodbye!")
                break
        except (KeyboardInterrupt, EOFError):
            break


# ── Demo mode ─────────────────────────────────────────────────────────────────

async def demo():
    orch = Orchestrator()
    print("=" * 55)
    print("  Smart Shopping Assistant — Demo")
    print("=" * 55)

    # single item
    print("\n  [Single] laptop for programming, budget $700")
    r = await orch.run({"query": "laptop for programming", "budget": 700})
    if r.success:
        show_single(r.data)

    await asyncio.sleep(0.5)

    # multi item
    print("\n  [Multi] living room furniture, budget $3000")
    r = await orch.run_multi({
        "items": ["sofa", "coffee table", "tv"],
        "budget": 3000, "style": "modern", "user_id": "demo"
    })
    if r.success:
        show_multi(r.data)


if __name__ == "__main__":
    if "--demo" in sys.argv:
        asyncio.run(demo())
    else:
        asyncio.run(interactive())