# Smart Shopping Assistant — Multi-Agent System

A conversational shopping assistant built with a **Multi-Agent System** architecture from scratch in Python — no frameworks like LangChain or CrewAI. Every agent, message bus, and orchestration pattern is hand-crafted to demonstrate how real multi-agent systems work under the hood.

---

## What It Does

The assistant conducts a natural conversation to understand what you need, then searches eBay for real products and returns optimized recommendations.

**Two modes:**

- **Single item** — "I want a laptop for programming, budget $700" → searches, scores, and recommends the best match with alternatives
- **Multi-item** — "I want to furnish my living room" → searches all items in parallel, scores each, and returns 3 optimized purchase combinations (Balanced / Premium / Best Value) within your total budget

---

## Architecture

This project was built incrementally across 5 phases, each introducing a new concept:

```
Phase 1 — Base Agent
  Every agent in the system inherits from BaseAgent.
  Handles state (IDLE → RUNNING → DONE/FAILED), memory, and tool registration.

Phase 2 — Message Bus
  Agents don't call each other directly.
  They publish to channels; other agents subscribe and read.
  Decouples agents and enables parallel execution.

Phase 3 — Worker Agents (Parallel)
  Multiple agents run simultaneously using asyncio.gather().
  eBay Agent searches real listings. Scorer Agent evaluates each product.
  Running them in parallel cuts response time by ~60%.

Phase 4 — Orchestrator + Intelligence
  Orchestrator coordinates the full flow — decides which agents run and when.
  Portfolio Optimizer Agent uses Claude API to find the 3 best product combinations
  that fit within the total budget.

Phase 5 — Real Data + Conversational Interface
  eBay Browse API provides real, live product listings.
  Claude API powers the intake interview — asking one question at a time
  to build a complete user profile before searching.
```

### Agent Map

```
main.py
  └── Profiler (Claude API) — intake interview
        └── Orchestrator
              ├── EbayAgent × N    (parallel search per item)
              ├── ScorerAgent × N  (parallel scoring per item)
              └── PortfolioAgent   (Claude API — finds best combinations)
```

### Communication Patterns Used

| Pattern | Where |
|---|---|
| Sequential | Profiler → Orchestrator → Output |
| Parallel | EbayAgent + ScorerAgent run simultaneously per item |
| Hierarchical | Orchestrator manages all worker agents |
| Message Bus | Agents publish results to named channels |
| Iterative | Profiler asks follow-up questions until profile is complete |

---

## Project Structure

```
shopping-v2/
├── agents/
│   ├── base_agent.py              # Base class for all agents
│   ├── orchestrator.py            # Coordinates the full pipeline
│   ├── workers/
│   │   ├── ebay_agent.py          # eBay Browse API search
│   │   └── scorer_agent.py        # Price + review scoring
│   └── intelligence/
│       └── portfolio_agent.py     # Claude-powered combination optimizer
├── core/
│   └── message_bus.py             # Async pub/sub communication layer
├── tests/
│   └── test_all.py                # All tests in one file
├── main.py                        # Entry point
├── config.py                      # Environment config
├── requirements.txt
└── .env.example                   # Environment variables template
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Anthropic API key → [console.anthropic.com](https://console.anthropic.com)
- eBay Developer account → [developer.ebay.com](https://developer.ebay.com)

### Installation

```bash
git clone https://github.com/gkazemikhanghah-maker/smart-shopping-assistant.git
cd smart-shopping-assistant
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Environment Setup

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```env
ANTHROPIC_API_KEY=sk-ant-...
EBAY_APP_ID=your-app-id
EBAY_CERT_ID=your-cert-id
```

**Getting eBay keys:**
1. Go to [developer.ebay.com/my/keys](https://developer.ebay.com/my/keys)
2. Create a Production keyset
3. Apply for exemption from Marketplace Account Deletion notifications
4. Copy App ID and Cert ID

### Run

```bash
# Interactive mode
python main.py

# Quick demo (no user input)
python main.py --demo

# Run all tests
python tests/test_all.py
```

---

## Example Sessions

**Single item:**
```
You: I want a laptop for programming
Assistant: What's your budget?
You: $700
Assistant: Any size preference — portable or large screen?
You: portable

Searching...

RECOMMENDED
  Acer Swift Go 14" Laptop Intel Core Ultra 7
  Price: $399.99  |  Score: 84.2/100
  good time to buy
  https://www.ebay.com/itm/...
```

**Multi-item:**
```
You: I want to furnish my living room
Assistant: What pieces are you looking for?
You: sofa, coffee table, TV stand, bookshelf
Assistant: What's your total budget?
You: $3,000
Assistant: What style?
You: Scandinavian

Searching 4 items...

Option 1 — Balanced: Best overall value
  SOFA          $899.00  Scandinavian fabric 3-seater sofa
  COFFEE TABLE  $189.99  Solid wood coffee table with storage
  TV STAND      $149.99  Minimalist oak TV console
  BOOKSHELF     $129.00  5-shelf birch bookcase
  Total: $1,367.98  |  Savings: $1,632.02
```

---

## Key Design Decisions

**Why no framework?**
Building from scratch forces you to understand exactly what happens at each step. Once you've hand-rolled a message bus and orchestrator, frameworks like LangGraph make complete sense.

**Why eBay API?**
Free, no credit card required for Browse API, and it has real products across every category. The trade-off is that results are sorted by relevance rather than price, so budget-friendly options sometimes appear lower in results.

**Why Claude for portfolio optimization?**
Finding the best combination of N products across M categories within a budget constraint is a classic optimization problem. Claude handles the trade-off reasoning naturally — "spend more on the sofa, save on the coffee table" — without needing a solver.

---

## Limitations & Future Work

- eBay API sorts by relevance, not price — budget-tier options may not always surface first
- No persistent user profile between sessions
- Vision Agent (room photo analysis) is planned but not yet connected to the main flow
- Fashion Mode (clothing + accessories) is a natural extension of the same architecture

---

## Author

Built by [gkazemikhanghah-maker](https://github.com/gkazemikhanghah-maker)
