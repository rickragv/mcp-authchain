"""Token refresh strategies.

Each function returns a RefreshFn (async () -> str) that produces a fresh id_token.

    refresh = firebase_refresh(api_key="...", refresh_token="...")
    refresh = websocket_refresh(send_fn=ws.send_json, receive_fn=ws.receive_json)
    refresh = my_custom_fn  # any async () -> str
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable

import httpx

log = logging.getLogger(__name__)

RefreshFn = Callable[[], Awaitable[str]]

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2


class TokenRefreshError(Exception):
    """Refresh failed permanently (user revoked, token invalid, retries exhausted)."""

    pass


def firebase_refresh(
    api_key: str,
    refresh_token: str,
    on_rotate: Callable[[str], Awaitable[None]] | None = None,
) -> RefreshFn:
    """Refresh via Firebase Auth REST API.

    Args:
        api_key: Firebase Web API key.
        refresh_token: Long-lived refresh token from user login.
        on_rotate: Optional callback when Firebase rotates the refresh token.
    """
    state = {"refresh_token": refresh_token}

    async def _refresh() -> str:
        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        f"https://securetoken.googleapis.com/v1/token?key={api_key}",
                        data={
                            "grant_type": "refresh_token",
                            "refresh_token": state["refresh_token"],
                        },
                    )

                    if resp.status_code == 400:
                        body = resp.json() if resp.content else {}
                        msg = body.get("error", {}).get("message", "Unknown error")
                        raise TokenRefreshError(
                            f"Firebase rejected refresh token: {msg}. "
                            f"User may be disabled or token revoked."
                        )

                    resp.raise_for_status()
                    data = resp.json()

                new_id_token = data["id_token"]
                new_refresh_token = data["refresh_token"]

                if new_refresh_token != state["refresh_token"]:
                    state["refresh_token"] = new_refresh_token
                    if on_rotate:
                        try:
                            await on_rotate(new_refresh_token)
                        except Exception:
                            log.exception("Failed to persist rotated refresh token")

                log.info("Firebase token refreshed for user %s", data.get("user_id"))
                return new_id_token

            except TokenRefreshError:
                raise

            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                delay = _RETRY_BASE_DELAY * (2**attempt)
                log.warning(
                    "Firebase refresh attempt %d/%d failed, retry in %ds: %s",
                    attempt + 1, _MAX_RETRIES, delay, e,
                )
                await asyncio.sleep(delay)

        raise TokenRefreshError(
            f"Firebase refresh failed after {_MAX_RETRIES} attempts: {last_error}"
        )

    return _refresh


def websocket_refresh(
    send_fn: Callable[[dict[str, Any]], Awaitable[None]],
    receive_fn: Callable[[], Awaitable[dict[str, Any]]],
    timeout: float = 30.0,
) -> RefreshFn:
    """Refresh by asking the browser for a fresh token via WebSocket."""

    async def _refresh() -> str:
        await send_fn({"type": "token_refresh_needed"})
        try:
            msg = await asyncio.wait_for(receive_fn(), timeout=timeout)
        except asyncio.TimeoutError:
            raise TokenRefreshError(
                f"Browser did not respond with a fresh token within {timeout}s."
            )

        token = msg.get("id_token")
        if not token:
            raise TokenRefreshError(f"Browser response missing 'id_token'. Got: {list(msg.keys())}")
        log.info("Token refreshed via browser WebSocket")
        return token

    return _refresh
