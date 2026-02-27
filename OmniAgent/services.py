"""
OmniAgent Mock Services
=======================
A FastAPI-based suite of REST endpoints simulating real-world data
for Weather, Finance, Identity, Travel, and Cinema domains.
"""

import random
import string
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="OmniAgent Mock Services", version="1.0.0")

# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------

class WeatherResponse(BaseModel):
    location: str
    temperature_c: float
    condition: str
    humidity: int
    wind_kph: float

class CurrencyResponse(BaseModel):
    from_currency: str
    to_currency: str
    amount: float
    converted: float
    rate: float

class MemberResponse(BaseModel):
    email: str
    name: str
    member_id: str
    tier: str
    points: int

class Flight(BaseModel):
    flight_id: str
    airline: str
    origin: str
    destination: str
    date: str
    departure: str
    arrival: str
    price_usd: float

class FlightSearchResponse(BaseModel):
    origin: str
    destination: str
    date: str
    flights: list[Flight]

class BookingConfirmation(BaseModel):
    confirmation_code: str
    flight_id: str
    member_id: str
    status: str

class Movie(BaseModel):
    movie_id: str
    title: str
    genre: str
    rating: float
    showtime: str

class MovieSearchResponse(BaseModel):
    genre: str
    movies: list[Movie]

class MovieTicket(BaseModel):
    ticket_id: str
    movie_id: str
    seats: int
    total_price_usd: float
    status: str

# ---------------------------------------------------------------------------
# Hardcoded Data
# ---------------------------------------------------------------------------

EXCHANGE_RATES = {
    ("USD", "EUR"): 0.92, ("EUR", "USD"): 1.09,
    ("USD", "GBP"): 0.79, ("GBP", "USD"): 1.27,
    ("USD", "INR"): 83.50, ("INR", "USD"): 0.012,
    ("EUR", "GBP"): 0.86, ("GBP", "EUR"): 1.16,
    ("USD", "JPY"): 154.50, ("JPY", "USD"): 0.0065,
    ("EUR", "INR"): 90.80, ("INR", "EUR"): 0.011,
}

MEMBERS = {
    "test@email.com":  {"name": "Alice Johnson",  "member_id": "MEM-1001", "tier": "Gold",     "points": 52400},
    "john@demo.com":   {"name": "John Smith",     "member_id": "MEM-1002", "tier": "Silver",   "points": 18700},
    "sara@demo.com":   {"name": "Sara Williams",  "member_id": "MEM-1003", "tier": "Platinum", "points": 105000},
}

AIRLINES = ["SkyWay Airlines", "AeroConnect", "GlobalJet"]

CONDITIONS = ["Sunny", "Partly Cloudy", "Cloudy", "Rainy", "Thunderstorm", "Snowy", "Windy", "Clear"]

MOVIES = {
    "sci-fi": [
        {"movie_id": "MOV-301", "title": "Quantum Horizon",      "rating": 8.4, "showtime": "7:00 PM"},
        {"movie_id": "MOV-302", "title": "Neural Frontier",      "rating": 7.9, "showtime": "9:30 PM"},
        {"movie_id": "MOV-303", "title": "The Singularity Code",  "rating": 8.1, "showtime": "6:15 PM"},
    ],
    "action": [
        {"movie_id": "MOV-401", "title": "Steel Thunder",        "rating": 7.5, "showtime": "8:00 PM"},
        {"movie_id": "MOV-402", "title": "Rogue Protocol",       "rating": 8.0, "showtime": "9:00 PM"},
    ],
    "comedy": [
        {"movie_id": "MOV-501", "title": "Office Chaos",         "rating": 7.2, "showtime": "6:30 PM"},
        {"movie_id": "MOV-502", "title": "The Unlikely Pair",    "rating": 7.8, "showtime": "8:45 PM"},
    ],
    "drama": [
        {"movie_id": "MOV-601", "title": "The Last Letter",      "rating": 8.6, "showtime": "7:30 PM"},
        {"movie_id": "MOV-602", "title": "Echoes of Tomorrow",   "rating": 8.2, "showtime": "9:15 PM"},
    ],
}

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/weather", response_model=WeatherResponse)
def get_weather(location: str):
    """Return randomized weather data for a given location."""
    return WeatherResponse(
        location=location,
        temperature_c=round(random.uniform(-5, 42), 1),
        condition=random.choice(CONDITIONS),
        humidity=random.randint(20, 95),
        wind_kph=round(random.uniform(0, 60), 1),
    )


@app.get("/convert", response_model=CurrencyResponse)
def convert_currency(from_currency: str, to_currency: str, amount: float):
    """Convert currency using hardcoded exchange rates."""
    key = (from_currency.upper(), to_currency.upper())
    rate = EXCHANGE_RATES.get(key)
    if rate is None:
        return CurrencyResponse(
            from_currency=from_currency.upper(),
            to_currency=to_currency.upper(),
            amount=amount,
            converted=0.0,
            rate=0.0,
        )
    return CurrencyResponse(
        from_currency=from_currency.upper(),
        to_currency=to_currency.upper(),
        amount=amount,
        converted=round(amount * rate, 2),
        rate=rate,
    )


@app.get("/member", response_model=MemberResponse)
def lookup_member(email: str):
    """Look up a member by email address."""
    member = MEMBERS.get(email.lower())
    if member is None:
        return MemberResponse(email=email, name="Unknown", member_id="N/A", tier="None", points=0)
    return MemberResponse(email=email, **member)


@app.get("/flights", response_model=FlightSearchResponse)
def search_flights(origin: str, destination: str, date: str):
    """Search for available flights between two cities on a given date (YYYY-MM-DD)."""
    flights = []
    for i in range(random.randint(2, 3)):
        dep_hour = random.randint(6, 20)
        flights.append(Flight(
            flight_id=f"FL-{random.randint(1000, 9999)}",
            airline=random.choice(AIRLINES),
            origin=origin.upper(),
            destination=destination.upper(),
            date=date,
            departure=f"{dep_hour:02d}:{random.choice(['00','15','30','45'])}",
            arrival=f"{(dep_hour + random.randint(2, 8)) % 24:02d}:{random.choice(['00','15','30','45'])}",
            price_usd=round(random.uniform(150, 1200), 2),
        ))
    return FlightSearchResponse(origin=origin.upper(), destination=destination.upper(), date=date, flights=flights)


@app.post("/book_flight", response_model=BookingConfirmation)
def book_flight(flight_id: str, member_id: str):
    """Book a flight for a member. Returns a confirmation code."""
    code = "CONF-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return BookingConfirmation(
        confirmation_code=code,
        flight_id=flight_id,
        member_id=member_id,
        status="confirmed",
    )


@app.get("/movies", response_model=MovieSearchResponse)
def search_movies(genre: str):
    """Search for currently playing movies by genre."""
    genre_lower = genre.lower()
    movie_list = MOVIES.get(genre_lower, [])
    movies = [Movie(genre=genre_lower, **m) for m in movie_list]
    return MovieSearchResponse(genre=genre_lower, movies=movies)


@app.post("/book_movie", response_model=MovieTicket)
def book_movie(movie_id: str, seats: int):
    """Book movie tickets. Returns a digital ticket stub."""
    ticket_id = "TKT-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return MovieTicket(
        ticket_id=ticket_id,
        movie_id=movie_id,
        seats=seats,
        total_price_usd=round(seats * random.uniform(10, 18), 2),
        status="confirmed",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
