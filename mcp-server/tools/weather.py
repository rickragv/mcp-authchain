"""Weather API tool -- config loaded from configs/tools/weather.yaml."""

import logging

import httpx

from .base import BaseMCPTool

log = logging.getLogger(__name__)


class GetWeatherTool(BaseMCPTool):

    async def execute(self, city: str, **kwargs) -> dict:
        geocode_url = self.config.get("api", {}).get(
            "geocode_url", "https://geocoding-api.open-meteo.com/v1/search"
        )
        weather_url = self.config.get("api", {}).get(
            "weather_url", "https://api.open-meteo.com/v1/forecast"
        )

        async with httpx.AsyncClient(timeout=15) as client:
            geo_resp = await client.get(geocode_url, params={"name": city, "count": 1})
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()

            results = geo_data.get("results")
            if not results:
                return {"error": f"City not found: {city}"}

            location = results[0]
            lat, lon = location["latitude"], location["longitude"]
            resolved_name = location.get("name", city)
            country = location.get("country", "")

            weather_resp = await client.get(
                weather_url,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,wind_speed_10m,weather_code",
                    "temperature_unit": "celsius",
                },
            )
            weather_resp.raise_for_status()
            weather_data = weather_resp.json()

        current = weather_data.get("current", {})
        return {
            "city": resolved_name,
            "country": country,
            "latitude": lat,
            "longitude": lon,
            "temperature_celsius": current.get("temperature_2m"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "weather_code": current.get("weather_code"),
        }

    def register(self, mcp, mcp_auth) -> None:
        tool = self

        @mcp.tool(name=self.name, description=self.description)
        async def get_weather(city: str) -> dict:
            log.info("tool_call tool=%s city=%s", tool.name, city)
            return await tool.execute(city=city)
