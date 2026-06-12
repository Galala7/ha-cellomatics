"""Lightweight async client for the (unofficial, reverse-engineered) Cellomatics API."""

from __future__ import annotations

import json
import logging
import re

import aiohttp

from .const import BASE_URL

_LOGGER = logging.getLogger(__name__)

_VIEWSTATE_RE = re.compile(r'__VIEWSTATE" id="__VIEWSTATE" value="([^"]*)"')
_VIEWSTATEGEN_RE = re.compile(
    r'__VIEWSTATEGENERATOR" id="__VIEWSTATEGENERATOR" value="([^"]*)"'
)
_EVENTVALIDATION_RE = re.compile(
    r'__EVENTVALIDATION" id="__EVENTVALIDATION" value="([^"]*)"'
)


class CellomaticsAuthError(Exception):
    """Raised when login fails or the session cannot be authenticated."""


class CellomaticsApi:
    """Handles login/session management and raw API calls."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        site_id: str,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self.site_id = site_id

    async def async_login(self) -> None:
        """Run the multi-step ASP.NET login flow and store auth cookies in the session."""
        # 1. Hit the platform URL to obtain a session cookie.
        async with self._session.get(
            f"{BASE_URL}/online_platformn_ns124", ssl=False
        ) as resp:
            await resp.read()

        # 2. Load the mobile login form to scrape the ASP.NET WebForms tokens.
        async with self._session.get(f"{BASE_URL}/loginmob", ssl=False) as resp:
            text = await resp.text()

        vs = _VIEWSTATE_RE.search(text)
        vsg = _VIEWSTATEGEN_RE.search(text)
        ev = _EVENTVALIDATION_RE.search(text)
        if not (vs and vsg and ev):
            raise CellomaticsAuthError("Could not parse login form (page layout changed?)")

        # 3. Submit credentials.
        data = {
            "__VIEWSTATE": vs.group(1),
            "__VIEWSTATEGENERATOR": vsg.group(1),
            "__EVENTVALIDATION": ev.group(1),
            "UserName": self._username,
            "Password": self._password,
            "Button2": "Login",
        }
        async with self._session.post(
            f"{BASE_URL}/loginmob", data=data, ssl=False
        ) as resp:
            await resp.read()

    async def async_test_credentials(self) -> bool:
        """Attempt a login and verify it succeeded (used by the config flow)."""
        await self.async_login()
        data = await self.async_get(f"/api/readValvesCount/{self.site_id}")
        return isinstance(data, list) and len(data) > 0

    async def async_get_valve_count(self) -> int | None:
        """Read the number of valves configured on this controller (4-6)."""
        try:
            data = await self.async_get(f"/api/readValvesCount/{self.site_id}")
            count = int(data[0]["stringParam"])
        except (KeyError, IndexError, TypeError, ValueError, CellomaticsAuthError):
            return None

        if 1 <= count <= 6:
            return count
        return None

    async def async_get(self, path: str):
        """GET a JSON API endpoint, re-logging in once if the session has expired."""
        for attempt in range(2):
            async with self._session.get(f"{BASE_URL}{path}", ssl=False) as resp:
                content_type = resp.headers.get("content-type", "")
                text = await resp.text()

            if (
                content_type.startswith("application/json")
                and "Authorization has been denied" not in text
            ):
                return json.loads(text)

            if attempt == 0:
                _LOGGER.debug("Cellomatics session expired, re-authenticating")
                await self.async_login()

        raise CellomaticsAuthError(f"Failed to fetch {path}")

    async def async_call(self, command: str):
        """POST a live command to /api/call and return the parsed JSON string result."""
        body = {"devId": self.site_id, "intParam": 14, "stringParam": command}

        for attempt in range(2):
            async with self._session.post(
                f"{BASE_URL}/api/call",
                json=body,
                headers={
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                },
                ssl=False,
            ) as resp:
                status = resp.status
                text = await resp.text()

            if status == 200 and text.startswith('"'):
                return json.loads(text)

            if attempt == 0:
                _LOGGER.debug("Cellomatics session expired, re-authenticating")
                await self.async_login()

        raise CellomaticsAuthError("Failed to call /api/call")
