"""Daily forecast from Open-Meteo (free, no API key)."""
import datetime as dt
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

API = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes -> short English description
CODES = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Cloudy",
    45: "Fog", 48: "Fog",
    51: "Drizzle", 53: "Drizzle", 55: "Drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow",
    80: "Showers", 81: "Showers", 82: "Heavy showers", 85: "Snow showers", 86: "Snow showers",
    95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm",
}


@dataclass
class Forecast:
    high: float
    low: float
    code: int
    rain_chance: int  # percent

    @property
    def description(self) -> str:
        return CODES.get(self.code, "Unknown")


def fetch(cfg: dict, day: dt.date, timezone: str) -> Forecast | None:
    """Forecast for `day`, or None if the API is unreachable (the frame is built without it)."""
    query = urllib.parse.urlencode({
        "latitude": cfg["latitude"],
        "longitude": cfg["longitude"],
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": timezone,
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
    })
    try:
        with urllib.request.urlopen(f"{API}?{query}", timeout=15) as resp:
            daily = json.load(resp)["daily"]
        return Forecast(
            high=daily["temperature_2m_max"][0],
            low=daily["temperature_2m_min"][0],
            code=daily["weather_code"][0],
            rain_chance=daily["precipitation_probability_max"][0] or 0,
        )
    except Exception as e:  # network down, date out of range, API change...
        print(f"Weather unavailable: {e}")
        return None
