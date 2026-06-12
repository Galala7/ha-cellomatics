"""Data update coordinator for Cellomatics Irrigation.

Polling strategy (push-based, not on a fixed interval):

- Every day at 00:06, /api/readPlans is read and today's run window(s) are
  computed (plan start time -> start + duration).
- On every quarter hour (xx:00, xx:15, xx:30, xx:45) that falls inside a run
  window:
    - xx:00            -> passive read (readRaw) - the controller pushes its
                          own hourly update around this time.
    - xx:15/30/45      -> active poll (/api/call) - live valve states + flow
                          rates.
- Every hour at xx:05 (always, regardless of run windows) a passive read
  (readRaw) keeps battery level, valve/flow state and idle/running status
  fresh without waking the device.
- Every day at 23:55, /api/readReport is read for today and the day's total
  water usage (zone 1.2) is published.

All wall-clock comparisons use Home Assistant's configured local time
(`homeassistant.util.dt.now()`) rather than the host OS clock, so this
behaves correctly even if the underlying system clock is UTC (e.g. some
Docker hosts) while Home Assistant itself is configured for a different
time zone.
"""

from __future__ import annotations

import datetime
import logging
import re

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import CellomaticsApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_STAT_RE = re.compile(r"STAT:(\d{6}),CTR:(\d+),L/H:(\d+),ENA:(\d)")
_BAT_RE = re.compile(r"BAT:(\d+)")
_VALVES_RE = re.compile(r"VALVES:(\d{6})_,_(\d{6})")
_CTR_RE = re.compile(r"CTR:(\d+),FLOW:(\d+)")
_CTR2_RE = re.compile(r"CTR2:(\d+),FLOW2:(\d+)")
_FERT_RE = re.compile(r"FCTR1:(\d+),FLOW:(\d+)")
_REPORT_RE = re.compile(r"TE,1,2,\d+,([\d.]+),")

_ACTIVE_COMMAND = "valves;!flow;!flow2;!fert flow;!get ena;!ptime;!status;!"


class CellomaticsCoordinator(DataUpdateCoordinator):
    """Coordinates polling of the Cellomatics API on a custom schedule."""

    def __init__(self, hass: HomeAssistant, api: CellomaticsApi) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.api = api
        self.data: dict = {}
        self._windows: list[tuple[datetime.datetime, datetime.datetime]] = []
        self._unsub_tick = None
        self._unsub_midnight = None
        self._unsub_report = None

    async def async_setup(self) -> None:
        """Prime the data and start the schedule listeners."""
        await self._async_refresh_windows()
        await self._async_passive_update()
        await self._async_daily_summary()

        self._unsub_tick = async_track_time_change(
            self.hass, self._async_tick, minute=[0, 5, 15, 30, 45], second=10
        )
        self._unsub_midnight = async_track_time_change(
            self.hass, self._async_midnight, hour=0, minute=6, second=0
        )
        self._unsub_report = async_track_time_change(
            self.hass, self._async_report_tick, hour=23, minute=55, second=0
        )

    def unload(self) -> None:
        """Cancel all scheduled listeners."""
        for unsub in (self._unsub_tick, self._unsub_midnight, self._unsub_report):
            if unsub:
                unsub()

    # ------------------------------------------------------------------
    # Scheduled callbacks
    # ------------------------------------------------------------------
    async def _async_midnight(self, now: datetime.datetime) -> None:
        await self._async_refresh_windows()

    async def _async_report_tick(self, now: datetime.datetime) -> None:
        await self._async_daily_summary()

    async def _async_tick(self, now: datetime.datetime) -> None:
        # Derive our own HA-local wall-clock time rather than relying on the
        # representation of `now` as delivered by the event helper, so the
        # minute/window math below is always correct regardless of the host
        # system's timezone.
        local_now = dt_util.now().replace(second=0, microsecond=0, tzinfo=None)
        minute = local_now.minute
        in_window = self._in_window(local_now)

        if minute == 5:
            # Hourly heartbeat - always, regardless of run windows.
            await self._async_passive_update()
        elif minute == 0:
            if in_window:
                await self._async_passive_update()
        elif minute in (15, 30, 45):
            if in_window:
                await self._async_active_update()

    # ------------------------------------------------------------------
    # Run window handling
    # ------------------------------------------------------------------
    async def _async_refresh_windows(self) -> None:
        try:
            data = await self.api.async_get(f"/api/readPlans/{self.api.site_id}")
            string_param = (data[0].get("stringParam") or "") if data else ""
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Cellomatics: failed to read plans: %s", err)
            string_param = ""

        today = dt_util.now().date()

        # Hebrew week order in the UI is א(Sun) ב(Mon) ג(Tue) ד(Wed) ה(Thu) ו(Fri) ש(Sat).
        # Assumption (unverified against a non-"every day" plan): bit0 (LSB) = Sunday
        # ... bit6 = Saturday. 127 = 0b1111111 = all days, which covers the
        # currently configured plans.
        weekday = today.weekday()  # Monday=0 .. Sunday=6
        sun_index = (weekday + 1) % 7

        windows: list[tuple[datetime.datetime, datetime.datetime]] = []
        for plan in string_param.split(".."):
            fields = plan.split(",")
            if len(fields) < 5:
                continue
            try:
                start_str = fields[2]
                duration = int(fields[3])
                days_mask = int(fields[4])
            except ValueError:
                continue

            if days_mask != 127 and not (days_mask & (1 << sun_index)):
                continue

            try:
                hour, minute = int(start_str[:2]), int(start_str[2:])
                start_dt = datetime.datetime.combine(today, datetime.time(hour, minute))
            except ValueError:
                _LOGGER.debug(
                    "Cellomatics: could not parse plan start time %r", start_str
                )
                continue

            end_dt = start_dt + datetime.timedelta(minutes=duration)
            windows.append((start_dt, end_dt))

        self._windows = windows
        _LOGGER.debug("Cellomatics: today's run windows = %s", windows)

    def _in_window(self, slot: datetime.datetime) -> bool:
        return any(start <= slot <= end for start, end in self._windows)

    # ------------------------------------------------------------------
    # Data fetchers
    # ------------------------------------------------------------------
    async def _async_active_update(self) -> None:
        try:
            resp = await self.api.async_call(_ACTIVE_COMMAND)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Cellomatics: active poll failed: %s", err)
            return

        if not isinstance(resp, str):
            _LOGGER.warning("Cellomatics: unexpected /api/call response: %r", resp)
            return

        data = dict(self.data)

        match = _VALVES_RE.search(resp)
        if match:
            data["valves"] = [c == "1" for c in match.group(1)]

        match = _CTR_RE.search(resp)
        if match:
            data["ctr_main"] = int(match.group(1))
            data["flow_main"] = int(match.group(2))

        match = _CTR2_RE.search(resp)
        if match:
            data["ctr2"] = int(match.group(1))
            data["flow2"] = int(match.group(2))

        match = _FERT_RE.search(resp)
        if match:
            data["fert_ctr"] = int(match.group(1))
            data["fert_flow"] = int(match.group(2))

        data["status"] = "idle" if "NO_TASK" in resp else "running"
        data["raw"] = resp

        self.async_set_updated_data(data)

    async def _async_passive_update(self) -> None:
        try:
            entries = await self.api.async_get(f"/api/readRaw/{self.api.site_id}")
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Cellomatics: passive poll failed: %s", err)
            return

        if not isinstance(entries, list):
            _LOGGER.warning(
                "Cellomatics: unexpected readRaw response: %r", entries
            )
            return

        data = dict(self.data)

        # The most recent entries are a batch of related lines from the same
        # heartbeat (task status, BAT, BAL, VEN, STAT, ...). Look at a small
        # window covering a few recent batches.
        window = entries[:20]

        for entry in window:
            string_param = entry.get("stringParam") or ""
            match = _STAT_RE.search(string_param)
            if match:
                stat, ctr, flow_lh, _ena = match.groups()
                data["valves"] = [c == "1" for c in stat]
                data["ctr_main"] = int(ctr)
                data["flow_main"] = int(flow_lh)
                break

        for entry in window:
            string_param = entry.get("stringParam") or ""
            match = _BAT_RE.search(string_param)
            if match:
                data["battery"] = int(match.group(1))
                break

        for entry in window:
            string_param = entry.get("stringParam") or ""
            if "NO_TASK" in string_param:
                data["status"] = "idle"
                break
            if "Output_" in string_param:
                data["status"] = "running"
                break

        self.async_set_updated_data(data)

    async def _async_daily_summary(self) -> None:
        now = dt_util.now()
        date_str = f"{now.month}-{now.day}-{now.strftime('%y')}"

        try:
            entries = await self.api.async_get(
                f"/api/readReport/{self.api.site_id}/{date_str}/{date_str}"
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Cellomatics: daily summary failed: %s", err)
            return

        if not isinstance(entries, list):
            _LOGGER.warning(
                "Cellomatics: unexpected readReport response: %r", entries
            )
            return

        total = 0.0
        for entry in entries:
            string_param = entry.get("stringParam") or ""
            match = _REPORT_RE.match(string_param)
            if match:
                total += float(match.group(1))

        data = dict(self.data)
        data["water_today"] = round(total, 1)
        self.async_set_updated_data(data)
