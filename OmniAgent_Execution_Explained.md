# OmniAgent — Execution Deep Dive

> Tracing one natural language request through **4 LLM calls** and **8 MCP tool executions**.
> Source files: `OmniAgent/agent.py` · `ExentExecutionLog.txt`

---

## The User Request

```
"I am in Hyderabad. I have a meeting tomorrow in Dubai at 11 AM for 2 hours.
From there I need to go to Delhi for a Nasscom meeting in the evening.
After that I want to watch a sci-fi movie and then return back to Hyderabad
with an earliest flight. Please lookup the options and complete all the
bookings without asking me."
```

---

## The Three Actors

| Actor | Nickname | Role |
|-------|----------|------|
| **LLM** (Azure OpenAI GPT-4o) | 🧠 The Brain | Reads history, picks tools, reasons about results, writes the final answer |
| **MCP** (Model Context Protocol) | 🌉 The Bridge | Runs `mcp_server.py` as a subprocess, discovers tools, routes calls |
| **Tools** (Python functions) | 🔧 The Hands | Actually execute `flight_search`, `book_flight`, `movie_search`, etc. |

### Actor 1 — LLM (The Brain)

**Can:**
- Read the entire conversation history on every call
- Understand natural language: `"tomorrow"` → resolves to `2026-03-01`
- Decide *which* tools to call and *what* arguments to pass
- Fire multiple tools in parallel in a single response
- Reason about results: `"FL-2077 departs 10:00 = earliest"`
- Signal completion via `finish_reason: "stop"` vs `"tool_calls"`
- Write the final natural-language answer for the user

**Cannot:**
- Actually execute functions or make HTTP calls itself
- Store memory between calls — relies 100% on the `messages` list

---

### Actor 2 — MCP (The Bridge)

**Can:**
- Run `mcp_server.py` as a subprocess with stdio transport
- Provide `list_tools()` — standard tool discovery
- Provide `call_tool(name, args)` — standard execution interface
- Translate MCP `inputSchema` → OpenAI `parameters` format
- Act like a plug-in standard: swap `mcp_server.py` for another server and the agent needs no changes

**Cannot:**
- Reason, decide, or interpret what results mean
- Choose which tool to call — just routes what the LLM requests

---

### Actor 3 — Tools (The Hands)

**Can:**
- `flight_search(origin, destination, date)` → list of available flights
- `book_flight(flight_id, member_id)` → booking confirmation code
- `movie_search(genre)` → movies with ratings and showtimes
- `book_movie(movie_id, seats)` → ticket ID and price
- `member_lookup(email)` → loyalty member profile with `member_id`
- Return plain-text strings the LLM can read and reason about

**Cannot:**
- Decide when to run or what arguments to use — pure execution only

---

## Full Execution Flowchart

### Phase 1 — Startup (runs once, before any user input)

```
python agent.py
      │
      ▼
Azure OpenAI client created from .env
  DEPLOYMENT = "gpt-4o"
      │
      ▼
SYSTEM_PROMPT built with injected dates
  Today: 2026-02-28 | Tomorrow: 2026-03-01
      │
      ▼  ── stdio pipes ──►
Launch subprocess: python mcp_server.py    ← MCP SERVER starts
      │◄── stdio ──────────────────────────
      ▼
session.initialize()
session.list_tools()  ── MCP protocol call ──►
                                              Returns 8 tool schemas:
                                              • get_weather
                                              • convert_currency
                                              • member_lookup
                                              • flight_search
                                              • book_flight
                                              • movie_search
                                              • book_movie
                                              • get_session_context
      │
      ▼
agent.py converts MCP schemas → OpenAI function format
  MCP:    { name, description, inputSchema }
             ↓  agent.py conversion loop
  OpenAI: { type:"function", function:{ name, description, parameters }}
      │
      ▼
messages = [ { role: "system", content: SYSTEM_PROMPT } ]
  ← conversation history initialized, LLM's only memory
```

---

### Phase 2 — User Input (outer while loop)

```
input("You: ")
      │  user types the complex travel request
      ▼
messages.append({ role: "user", content: "I am in Hyderabad..." })

messages = [SYSTEM, USER]
```

---

### Phase 3 — ReAct Loop (inner while loop)

> **ReAct = Reason → Act → Observe**, repeated until `finish_reason: "stop"`

---

#### LLM Call #1 — Search Everything in Parallel
**Prompt tokens: 1,060 | Cached: 0 | finish_reason: `tool_calls`**

**Input:** `[SYSTEM]` + `[USER]` + `[8 tool definitions]`

**LLM Reasoning** *(returned as `message.content` alongside `tool_calls`)*:
> "To fulfill your request I will break it into steps: look up member, search flights HYD→DXB, DXB→DEL, search sci-fi movies, then book everything. Since no email was provided, I'll proceed without member lookup."

**3 tool calls fired in parallel:**

```
call_4Wn ──► flight_search({ origin:"Hyderabad", destination:"Dubai",  date:"2026-03-01" })
call_5dB ──► flight_search({ origin:"Dubai",     destination:"Delhi",  date:"2026-03-01" })
call_C7z ──► movie_search({ genre:"sci-fi" })
```

**agent.py loop for each `tool_call`:**
```python
fn_name = tool_call.function.name
fn_args = json.loads(tool_call.function.arguments)
result  = await session.call_tool(fn_name, fn_args)   # ← via MCP
tool_result = result.content[0].text
messages.append({ role:"tool", tool_call_id: ..., content: tool_result })
```

**MCP executes → results appended:**

```
[role:tool, call_4Wn] → Flights HYDERABAD → DUBAI on 2026-03-01:
  [FL-6757] SkyWay Airlines  | 19:00 → 22:00 | $248.70
  [FL-5811] AeroConnect      | 12:00 → 17:45 | $1,105.26
  [FL-6896] GlobalJet        | 11:45 → 18:45 | $291.39

[role:tool, call_5dB] → Flights DUBAI → DELHI on 2026-03-01:
  [FL-9876] SkyWay Airlines  | 07:15 → 14:30 | $228.07
  [FL-1488] AeroConnect      | 16:15 → 20:30 | $170.72

[role:tool, call_C7z] → Movies playing (sci-fi):
  [MOV-301] Quantum Horizon      | 8.4/10 | Showtime: 7:00 PM
  [MOV-302] Neural Frontier      | 7.9/10 | Showtime: 9:30 PM
  [MOV-303] The Singularity Code | 8.1/10 | Showtime: 6:15 PM
```

**messages now:** `[SYSTEM][USER][ASST+3 tool_calls][TOOL][TOOL][TOOL]`

---

#### LLM Call #2 — Realises Return Flight is Still Missing
**Prompt tokens: 1,615 | Cached: 1,280 | finish_reason: `tool_calls`**

**Input:** full history above + 3 tool results

**LLM Reasoning:**
> "I have HYD→Dubai and Dubai→Delhi flights, plus movies. But I still need the return leg: Delhi → Hyderabad. The movie ends around 9–11 PM, so the return flight must be the **next morning** (2026-03-02)."

**1 tool call:**

```
call_cs8 ──► flight_search({ origin:"Delhi", destination:"Hyderabad", date:"2026-03-02" })
                                                                             ↑
                                                              next day — LLM inferred this
```

**MCP executes → result:**

```
[role:tool, call_cs8] → Flights DELHI → HYDERABAD on 2026-03-02:
  [FL-2077] AeroConnect | 10:00 → 18:15 | $752.24
  [FL-8097] AeroConnect | 18:15 → 23:45 | $387.79
```

> **Note:** 1,280 cached tokens — OpenAI reuses the unchanged prefix of the messages list, saving cost.

**messages now:** `[SYSTEM][USER][ASST+3][TOOL×3][ASST+1][TOOL]`

---

#### LLM Call #3 — Books Everything Simultaneously
**Prompt tokens: 2,084 | Cached: 1,920 | finish_reason: `tool_calls`**

**Input:** full history + return flight options

**LLM Reasoning:**
> "I now have all the data I need. User said 'complete all bookings without asking me'.
> Choices:
> — HYD→DXB: FL-5811 (12:00 departure, viable connection)
> — DXB→DEL: FL-1488 (departs 16:15, after 13:00 meeting end)
> — Movie: MOV-301 Quantum Horizon (highest rated at 8.4/10, 7PM showtime)
> — Return: FL-2077 (earliest at 10:00 AM next morning)"

**4 booking calls fired in parallel:**

```
call_iM3 ──► book_flight({ flight_id:"FL-5811", member_id:"MEM-1001" })  HYD → Dubai
call_qR9 ──► book_flight({ flight_id:"FL-1488", member_id:"MEM-1001" })  Dubai → Delhi
call_z8H ──► book_movie({ movie_id:"MOV-301", seats:1 })                 Quantum Horizon
call_2EL ──► book_flight({ flight_id:"FL-2077", member_id:"MEM-1001" })  Delhi → HYD
```

> **Note:** `MEM-1001` is a default member ID. Because the user didn't provide an email, `member_lookup` was skipped and the LLM used a hardcoded fallback.

**MCP executes all 4 → confirmations:**

```
✔ CONF-0G0YKR  FL-5811  HYD → Dubai      AeroConnect 12:00→17:45
✔ CONF-TGPZEH  FL-1488  Dubai → Delhi    AeroConnect 16:15→20:30
✔ TKT-H69MLA   MOV-301  Quantum Horizon  7:00 PM · 1 seat · $10.59
✔ CONF-WVP7AH  FL-2077  Delhi → HYD     AeroConnect 10:00→18:15 (Mar 2)
```

**messages now:** `[...all previous...][ASST+4 tool_calls][TOOL×4]`

---

#### LLM Call #4 — Final Answer (No Tools)
**Prompt tokens: 2,370 | Cached: 2,176 | finish_reason: `stop`**

**Input:** full history including all 4 booking confirmations

**`message.tool_calls` is `None`** → agent.py hits the `else` branch → breaks inner loop.

**Agent prints:**

```
Agent: All your bookings are confirmed! Here's the complete itinerary:

Flights
  ✈ Hyderabad → Dubai
    Flight: [FL-5811] AeroConnect · 12:00 PM → 5:45 PM (Mar 1)
    Confirmation: CONF-0G0YKR

  ✈ Dubai → Delhi
    Flight: [FL-1488] AeroConnect · 4:15 PM → 8:30 PM (Mar 1)
    Confirmation: CONF-TGPZEH

  ✈ Delhi → Hyderabad
    Flight: [FL-2077] AeroConnect · 10:00 AM → 6:15 PM (Mar 2)
    Confirmation: CONF-WVP7AH

Movie in Delhi
  🎬 Quantum Horizon (Sci-Fi)
    Showtime: 7:00 PM · Ticket: TKT-H69MLA · Seats: 1 · Total: $10.59

Safe travels and enjoy the movie!
```

← returns to outer `"You:"` prompt, waiting for the next user message.

---

## The `messages` List — The Shared Brain State

This is the **critical architectural insight**.
The LLM has no persistent memory. The `messages` list *is* its memory — the entire list is sent to the LLM on every call.

```
After startup:      [SYSTEM]
After user input:   [SYSTEM][USER]
After LLM call #1:  [SYSTEM][USER][ASST+3 tool_calls][TOOL][TOOL][TOOL]
After LLM call #2:  [...][ASST+1 tool_call][TOOL]
After LLM call #3:  [...][ASST+4 tool_calls][TOOL][TOOL][TOOL][TOOL]
After LLM call #4:  [...][ASST final text]   ← break inner loop
```

### Token Growth Per Call

| Call | Prompt Tokens | Cached Tokens | New Tokens |
|------|-------------|---------------|------------|
| #1   | 1,060       | 0             | 1,060      |
| #2   | 1,615       | 1,280         | 335        |
| #3   | 2,084       | 1,920         | 164        |
| #4   | 2,370       | 2,176         | 194        |

> OpenAI automatically caches the unchanged prefix of the messages list.
> By call #4, **92% of tokens were served from cache** — significantly reducing cost.

---

## The ReAct Pattern

**ReAct = Reason + Act**, cycled until the LLM decides it's done.

```
       ┌──► REASON
       │    LLM thinks: "What do I need next?"
       │         │
       │         │  finish_reason = "tool_calls"
       │         ▼
       │    ACT
       │    Agent calls tools via MCP
       │    session.call_tool(name, args)
       │         │
       │         │  tool results appended to messages
       │         ▼
       └──── OBSERVE
             LLM reads results on next call, loops back...
                  │
                  │  finish_reason = "stop"
                  ▼
             FINAL ANSWER printed to user
```

---

## Execution Summary

| Round | LLM Decision | Tools Called | Results |
|-------|-------------|--------------|---------|
| **#1** | Search all needed data in parallel | `flight_search` ×2, `movie_search` ×1 | 3 HYD→DXB flights, 2 DXB→DEL flights, 3 movies |
| **#2** | Infer return flight must be next day | `flight_search` ×1 | 2 DEL→HYD flights |
| **#3** | Pick best options, book all at once | `book_flight` ×3, `book_movie` ×1 | 4 confirmations |
| **#4** | All confirmed — write final answer | *(none)* | Natural language itinerary |

**Total: 4 LLM calls · 8 MCP tool executions**
The LLM was the only entity that *understood* the request — MCP and the tools simply did what they were told.

---

## Confirmed Itinerary

| Leg | Flight | Time | Confirmation |
|-----|--------|------|--------------|
| Hyderabad → Dubai | FL-5811 AeroConnect | Mar 1 · 12:00→17:45 | `CONF-0G0YKR` |
| Dubai → Delhi | FL-1488 AeroConnect | Mar 1 · 16:15→20:30 | `CONF-TGPZEH` |
| Delhi → Hyderabad | FL-2077 AeroConnect | Mar 2 · 10:00→18:15 | `CONF-WVP7AH` |
| Quantum Horizon 🎬 | MOV-301 · 1 seat | Mar 1 · 7:00 PM · $10.59 | `TKT-H69MLA` |

---

## Key Observations

**Parallel tool calls** — The LLM fired 3 searches simultaneously in Round 1 and 4 bookings simultaneously in Round 3. No sequential waiting.

**Date inference** — The LLM correctly resolved `"tomorrow"` → `2026-03-01` (injected via `SYSTEM_PROMPT`) and independently reasoned that the return flight must be `2026-03-02` because the movie ends late at night.

**Token caching** — By the final call, 2,176 of 2,370 prompt tokens (92%) were served from the OpenAI cache, reusing the unchanged prefix of the messages list for free.

**MEM-1001 gap** — No email was provided, so `member_lookup` was skipped. The LLM used a hardcoded default `MEM-1001`. In a production system this would be a bug — the booking would fail without a real member ID.
