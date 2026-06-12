"""Standalone smoke test: exercise the coordinator's parsing logic against
the sample API responses in samples/, without needing Home Assistant (or
aiohttp) installed.

Usage:
    python tests/test_parsing.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COORD_SRC = (ROOT / "custom_components/cellomatics/coordinator.py").read_text(
    encoding="utf-8"
)

# Extract the regex constants directly from coordinator.py so this test
# always matches the real parsing logic, without importing the module
# (which would require Home Assistant to be installed).
_ns: dict = {"re": re}
for _line in COORD_SRC.splitlines():
    if re.match(r"^_[A-Z0-9_]+_RE = re\.compile\(", _line):
        exec(_line, _ns)  # noqa: S102
    elif re.match(r'^_ENA_ENABLED_VALUE = "', _line):
        exec(_line, _ns)  # noqa: S102

_STAT_RE = _ns["_STAT_RE"]
_BAT_RE = _ns["_BAT_RE"]
_VALVES_RE = _ns["_VALVES_RE"]
_CTR_RE = _ns["_CTR_RE"]
_CTR2_RE = _ns["_CTR2_RE"]
_FERT_RE = _ns["_FERT_RE"]
_REPORT_RE = _ns["_REPORT_RE"]
_ENA_RE = _ns["_ENA_RE"]
_ENA_ENABLED_VALUE = _ns["_ENA_ENABLED_VALUE"]


def load(name: str):
    return json.loads((ROOT / "samples" / f"{name}.json").read_text(encoding="utf-8"))


def test_passive_update() -> None:
    """Mirrors CellomaticsCoordinator._async_passive_update parsing."""
    entries = load("readRaw")
    data: dict = {}
    window = entries[:20]

    for entry in window:
        match = _STAT_RE.search(entry.get("stringParam") or "")
        if match:
            stat, ctr, flow_lh, _ena = match.groups()
            data["valves"] = [c == "1" for c in stat]
            data["ctr_main"] = int(ctr)
            data["flow_main"] = int(flow_lh)
            break

    for entry in window:
        match = _BAT_RE.search(entry.get("stringParam") or "")
        if match:
            data["battery"] = int(match.group(1))
            break

    for entry in window:
        match = _ENA_RE.search(entry.get("stringParam") or "")
        if match:
            data["enabled"] = match.group(1) == _ENA_ENABLED_VALUE
            break

    for entry in window:
        string_param = entry.get("stringParam") or ""
        if "NO_TASK" in string_param:
            data["status"] = "idle"
            break
        if "Output_" in string_param:
            data["status"] = "running"
            break

    print("passive update ->", data)
    assert data.get("valves") == [False, False, False, False, False, False]
    assert data.get("ctr_main") == 181206
    assert data.get("flow_main") == 0
    assert data.get("battery") == 4030
    assert data.get("enabled") is True
    assert data.get("status") == "idle"


def test_passive_update_running() -> None:
    """Mirrors CellomaticsCoordinator._async_passive_update parsing during a
    manual/unplanned irrigation run (samples/readRaw_running.json).

    Captured while a manual 60-minute run was active on valve 1, which
    auto-opened valves 2 and 6 (VALVES:110001).
    """
    entries = load("readRaw_running")
    data: dict = {}
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

        valves_match = _VALVES_RE.search(string_param)
        if valves_match:
            data["valves"] = [c == "1" for c in valves_match.group(1)]
            ctr_match = _CTR_RE.search(string_param)
            if ctr_match:
                data["ctr_main"] = int(ctr_match.group(1))
                data["flow_main"] = int(ctr_match.group(2))
            break

    for entry in window:
        string_param = entry.get("stringParam") or ""
        if "NO_TASK" in string_param:
            data["status"] = "idle"
            break
        if "Output_" in string_param or "MAN#" in string_param:
            data["status"] = "running"
            break

    print("passive update (running) ->", data)
    assert data.get("valves") == [True, True, False, False, False, True]
    assert data.get("ctr_main") == 181210
    assert data.get("flow_main") == 15420
    assert data.get("status") == "running"


def test_passive_update_suspended() -> None:
    """Mirrors CellomaticsCoordinator._async_passive_update parsing while the
    controller is suspended/disabled via the portal (samples/readRaw_suspended.json).

    The portal's "suspend irrigation for N days" feature sets ENA to a
    non-"1" value (observed: ENA:0 momentarily, then ENA:11). The API does
    not expose the remaining suspend duration, only that it's not "1".
    """
    entries = load("readRaw_suspended")
    data: dict = {}
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

        valves_match = _VALVES_RE.search(string_param)
        if valves_match:
            data["valves"] = [c == "1" for c in valves_match.group(1)]
            ctr_match = _CTR_RE.search(string_param)
            if ctr_match:
                data["ctr_main"] = int(ctr_match.group(1))
                data["flow_main"] = int(ctr_match.group(2))
            break

    for entry in window:
        match = _ENA_RE.search(entry.get("stringParam") or "")
        if match:
            data["enabled"] = match.group(1) == _ENA_ENABLED_VALUE
            break

    for entry in window:
        string_param = entry.get("stringParam") or ""
        if "NO_TASK" in string_param:
            data["status"] = "idle"
            break
        if "Output_" in string_param or "MAN#" in string_param:
            data["status"] = "running"
            break

    if data.get("enabled") is False:
        data["status"] = "suspended"

    print("passive update (suspended) ->", data)
    assert data.get("valves") == [False, False, False, False, False, False]
    assert data.get("ctr_main") == 181410
    assert data.get("flow_main") == 0
    assert data.get("enabled") is False
    assert data.get("status") == "suspended"


def test_active_update() -> None:
    """Mirrors CellomaticsCoordinator._async_active_update parsing."""
    resp = load("apiCall")
    data: dict = {}

    match = _VALVES_RE.search(resp)
    assert match
    data["valves"] = [c == "1" for c in match.group(1)]

    match = _CTR_RE.search(resp)
    assert match
    data["ctr_main"], data["flow_main"] = int(match.group(1)), int(match.group(2))

    match = _CTR2_RE.search(resp)
    assert match
    data["ctr2"], data["flow2"] = int(match.group(1)), int(match.group(2))

    match = _FERT_RE.search(resp)
    assert match
    data["fert_ctr"], data["fert_flow"] = int(match.group(1)), int(match.group(2))

    match = _ENA_RE.search(resp)
    assert match
    data["enabled"] = match.group(1) == _ENA_ENABLED_VALUE

    data["status"] = "idle" if "NO_TASK" in resp else "running"

    print("active update ->", data)
    assert data["valves"] == [False, False, False, False, False, False]
    assert data["ctr_main"] == 181206
    assert data["ctr2"] == 158
    assert data["fert_ctr"] == 3
    assert data["enabled"] is True
    assert data["status"] == "idle"


def test_active_update_suspended() -> None:
    """Mirrors CellomaticsCoordinator._async_active_update parsing while the
    controller is suspended/disabled via the portal (samples/apiCall_suspended.json).
    """
    resp = load("apiCall_suspended")

    match = _ENA_RE.search(resp)
    assert match
    enabled = match.group(1) == _ENA_ENABLED_VALUE

    status = "idle" if "NO_TASK" in resp else "running"
    if enabled is False:
        status = "suspended"

    print("active update (suspended) -> enabled =", enabled, "status =", status)
    assert enabled is False
    assert status == "suspended"


def test_daily_summary() -> None:
    """Mirrors CellomaticsCoordinator._async_daily_summary parsing.

    Note: samples/readReport.json covers 12 days (6-1-26..6-12-26) to show
    the TE,1,2 vs TE,5,1 zone format across several days. The real
    coordinator queries a single day (start == end == today), so in
    production this would sum just 1-2 entries, not the whole sample.
    """
    entries = load("readReport")
    total = 0.0
    for entry in entries:
        match = _REPORT_RE.match(entry.get("stringParam") or "")
        if match:
            total += float(match.group(1))

    print("water_today (sum over sample's 12 days) ->", round(total, 1))


if __name__ == "__main__":
    test_passive_update()
    test_passive_update_running()
    test_passive_update_suspended()
    test_active_update()
    test_active_update_suspended()
    test_daily_summary()
    print("OK")
