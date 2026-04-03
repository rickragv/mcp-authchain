"""Typed MCP client utility for weather tool. Auto-refresh on 401."""

from .base import BaseToolClient


class WeatherMCPClient(BaseToolClient):

    async def get_weather(self, city: str) -> dict:
        return await self.call_tool("get_weather", {"city": city})
