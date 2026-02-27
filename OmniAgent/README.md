# OmniAgent: Multi-Domain MCP-Powered AI Assistant

A demo project showcasing **Agentic AI** with the **Model Context Protocol (MCP)**. The agent uses Azure OpenAI to reason across multiple domains — weather, currency, travel, and cinema — via MCP tools.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   User Input     │────▶│  Azure OpenAI   │────▶│   MCP Server    │
│                  │◀────│  (ReAct Agent)  │◀────│   (Tool Layer)  │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │ HTTP
                                                ┌────────▼────────┐
                                                │  FastAPI Mock    │
                                                │  Services        │
                                                └─────────────────┘
```

**Three layers:**
1. **services.py** — FastAPI mock APIs (Weather, Currency, Member, Flights, Movies)
2. **mcp_server.py** — MCP tool definitions wrapping the APIs
3. **agent.py** — Azure OpenAI ReAct agent connected via MCP client

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Azure OpenAI

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

### 3. Start the mock services

In a terminal:
```bash
python services.py
```

This starts the FastAPI server on `http://localhost:8000`. You can test endpoints at `http://localhost:8000/docs`.

### 4. Run the agent

In a second terminal:
```bash
python agent.py
```

## Demo Scenarios

### Scenario 1: Multi-Step Travel + Entertainment
```
You: I'm a Gold member (test@email.com). Find me a flight to London tomorrow
     and a sci-fi movie to watch tonight.
```

**Expected agent reasoning:**
1. Call `member_lookup` → gets Member ID (MEM-1001)
2. Call `flight_search` → finds flights to London
3. Call `movie_search` → finds sci-fi movies
4. Synthesize into a natural-language itinerary

### Scenario 2: Currency + Weather
```
You: What's the weather in Tokyo? Also convert 500 USD to JPY.
```

### Scenario 3: Full Booking Flow
```
You: Book the cheapest flight to London for member test@email.com for tomorrow,
     and 2 tickets for the highest-rated sci-fi movie.
```

## API Endpoints Reference

| Endpoint | Method | Parameters |
|-----------|--------|------------|
| `/weather` | GET | `location` |
| `/convert` | GET | `from_currency`, `to_currency`, `amount` |
| `/member` | GET | `email` |
| `/flights` | GET | `origin`, `destination`, `date` (YYYY-MM-DD) |
| `/book_flight` | POST | `flight_id`, `member_id` |
| `/movies` | GET | `genre` |
| `/book_movie` | POST | `movie_id`, `seats` |

## MCP Tools

| Tool Name | Description |
|-----------|-------------|
| `get_weather` | Get weather for a location |
| `convert_currency` | Convert between currencies |
| `member_lookup` | Look up loyalty member by email |
| `flight_search` | Search flights between cities |
| `book_flight` | Book a flight for a member |
| `movie_search` | Search movies by genre |
| `book_movie` | Book movie tickets |
| `get_session_context` | Retrieve session state |
