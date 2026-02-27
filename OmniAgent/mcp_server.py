"""
OmniAgent MCP Server
=====================
Exposes the FastAPI mock services as MCP tools using the Python MCP SDK.
Each tool has a detailed description to guide LLM reasoning.

Run with:  python mcp_server.py
Requires services.py to be running on port 8000.
"""

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("OmniAgent", instructions="A multi-domain personal assistant with tools for weather, currency, member lookup, flights, and movies.")

API_BASE = "http://localhost:8000"

# Session state for cross-tool context
session_state: dict = {}


def _get(path: str, params: dict) -> dict:
    """Helper: call the mock service API."""
    with httpx.Client(timeout=10) as client:
        resp = client.get(f"{API_BASE}{path}", params=params)
        resp.raise_for_status()
        return resp.json()


def _post(path: str, params: dict) -> dict:
    """Helper: call mock service POST endpoint."""
    with httpx.Client(timeout=10) as client:
        resp = client.post(f"{API_BASE}{path}", params=params)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool Definitions
# ---------------------------------------------------------------------------

@mcp.tool()
def get_weather(location: str) -> str:
    """Get the current weather for a city or location.

    Args:
        location: The city or location name (e.g. "London", "New York", "Mumbai").

    Returns:
        A summary of current weather conditions including temperature,
        humidity, wind speed, and sky condition.
    """
    data = _get("/weather", {"location": location})
    return (
        f"Weather in {data['location']}:\n"
        f"  Temperature: {data['temperature_c']}°C\n"
        f"  Condition: {data['condition']}\n"
        f"  Humidity: {data['humidity']}%\n"
        f"  Wind: {data['wind_kph']} km/h"
    )


@mcp.tool()
def convert_currency(from_currency: str, to_currency: str, amount: float) -> str:
    """Convert an amount from one currency to another.

    Supported currencies: USD, EUR, GBP, INR, JPY.

    Args:
        from_currency: The source currency code (e.g. "USD").
        to_currency: The target currency code (e.g. "EUR").
        amount: The amount to convert.

    Returns:
        The converted amount with the exchange rate used.
    """
    data = _get("/convert", {
        "from_currency": from_currency,
        "to_currency": to_currency,
        "amount": amount,
    })
    if data["rate"] == 0:
        return f"Currency pair {from_currency}->{to_currency} is not supported."
    return (
        f"{data['amount']} {data['from_currency']} = "
        f"{data['converted']} {data['to_currency']} "
        f"(rate: {data['rate']})"
    )


@mcp.tool()
def member_lookup(email: str) -> str:
    """Look up a loyalty program member by their email address.

    This retrieves the member's name, ID, tier (Gold/Silver/Platinum),
    and reward points. The member_id is needed for booking operations.

    Args:
        email: The member's email address (e.g. "test@email.com").

    Returns:
        Member profile information. The member_id from this result
        should be used in subsequent booking calls.
    """
    data = _get("/member", {"email": email})
    # Store in session for cross-tool context
    if data["member_id"] != "N/A":
        session_state["member_id"] = data["member_id"]
        session_state["member_name"] = data["name"]
        session_state["member_tier"] = data["tier"]

    return (
        f"Member Profile:\n"
        f"  Name: {data['name']}\n"
        f"  Email: {data['email']}\n"
        f"  Member ID: {data['member_id']}\n"
        f"  Tier: {data['tier']}\n"
        f"  Points: {data['points']}"
    )


@mcp.tool()
def flight_search(origin: str, destination: str, date: str) -> str:
    """Search for available flights between two cities on a specific date.

    Args:
        origin: Departure city or airport code (e.g. "New York" or "JFK").
        destination: Arrival city or airport code (e.g. "London" or "LHR").
        date: Travel date in YYYY-MM-DD format (e.g. "2025-07-15").

    Returns:
        A list of available flights with flight IDs, airlines, times, and prices.
        Use the flight_id from these results to book via the book_flight tool.
    """
    data = _get("/flights", {"origin": origin, "destination": destination, "date": date})
    lines = [f"Flights from {data['origin']} to {data['destination']} on {data['date']}:\n"]
    for f in data["flights"]:
        lines.append(
            f"  [{f['flight_id']}] {f['airline']} | "
            f"Depart: {f['departure']} → Arrive: {f['arrival']} | "
            f"${f['price_usd']}"
        )
    return "\n".join(lines)


@mcp.tool()
def book_flight(flight_id: str, member_id: str) -> str:
    """Book a specific flight for a loyalty program member.

    Args:
        flight_id: The flight ID from a previous flight_search result (e.g. "FL-1234").
        member_id: The member's ID from a previous member_lookup result (e.g. "MEM-1001").

    Returns:
        A booking confirmation with a confirmation code and status.
    """
    data = _post("/book_flight", {"flight_id": flight_id, "member_id": member_id})
    return (
        f"Booking Confirmed!\n"
        f"  Confirmation Code: {data['confirmation_code']}\n"
        f"  Flight: {data['flight_id']}\n"
        f"  Member: {data['member_id']}\n"
        f"  Status: {data['status']}"
    )


@mcp.tool()
def movie_search(genre: str) -> str:
    """Search for currently playing movies by genre.

    Available genres: sci-fi, action, comedy, drama.

    Args:
        genre: The movie genre to search for (e.g. "sci-fi", "action", "comedy", "drama").

    Returns:
        A list of currently playing movies with IDs, titles, ratings, and showtimes.
        Use the movie_id from these results to book via the book_movie tool.
    """
    data = _get("/movies", {"genre": genre})
    if not data["movies"]:
        return f"No movies found for genre: {genre}. Try: sci-fi, action, comedy, drama."
    lines = [f"Movies playing ({data['genre']}):\n"]
    for m in data["movies"]:
        lines.append(
            f"  [{m['movie_id']}] {m['title']} | "
            f"Rating: {m['rating']}/10 | "
            f"Showtime: {m['showtime']}"
        )
    return "\n".join(lines)


@mcp.tool()
def book_movie(movie_id: str, seats: int) -> str:
    """Book movie tickets for a specific movie.

    Args:
        movie_id: The movie ID from a previous movie_search result (e.g. "MOV-301").
        seats: Number of seats/tickets to book (e.g. 2).

    Returns:
        A digital ticket stub with ticket ID, seat count, total price, and status.
    """
    data = _post("/book_movie", {"movie_id": movie_id, "seats": seats})
    return (
        f"Movie Tickets Booked!\n"
        f"  Ticket ID: {data['ticket_id']}\n"
        f"  Movie: {data['movie_id']}\n"
        f"  Seats: {data['seats']}\n"
        f"  Total: ${data['total_price_usd']}\n"
        f"  Status: {data['status']}"
    )


@mcp.tool()
def get_session_context() -> str:
    """Retrieve the current session context (previously looked-up member info, etc.).

    Returns:
        Any stored session state from previous tool calls in this session.
    """
    if not session_state:
        return "No session context available. Use member_lookup first."
    lines = ["Current Session Context:"]
    for k, v in session_state.items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
