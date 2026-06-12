# Sample API responses

These are real (sanitized) responses captured from the Cellomatics API on
2026-06-12, used to understand the data format and to sanity-check the
parsing logic in `custom_components/cellomatics/coordinator.py` without
needing to call the live device.

The real `devId`/site ID has been replaced everywhere with the placeholder
`0501234567`.

| File | Endpoint | Notes |
| --- | --- | --- |
| `readValvesCount.json` | `GET /api/readValvesCount/{siteId}` | `stringParam` = number of valves (6). |
| `readValvesNames.json` | `GET /api/readValvesNames/{siteId}` | One record per valve (1-6); `stringParam` = name/number, `stringParam_2` = configured flow limit. |
| `readParams.json` | `GET /api/readParams/{siteId}` | Device enabled/ack status string. |
| `readPlans.json` | `GET /api/readPlans/{siteId}` | Both configured plans (`1.2` and `5.1`), `..`-separated. |
| `readRaw.json` | `GET /api/readRaw/{siteId}` | First 40 of 1000 telemetry entries. Includes `BAT`, `BAL`, `VEN`, `STAT`, and task (`NO_TASK`/`Output_...`) lines — this is what the coordinator's passive poll reads. |
| `dashboardReadRaw.json` | `GET /api/dashboardReadRaw/{siteId}` | First 40 entries. Filtered subset of `readRaw` — **no `BAT`/`BAL` lines** (this is why the passive poll uses `readRaw` instead). |
| `readReport.json` | `GET /api/readReport/{siteId}/{start}/{end}` | Daily usage report (`TE,...` lines) for 6-1-26 to 6-12-26. |
| `apiCall.json` | `POST /api/call` (live query) | One live-query response, used by the active poll during a run window. |
| `readRaw_running.json` | `GET /api/readRaw/{siteId}` | First 40 entries, captured during a **manual 60-minute run on valve 1** (which auto-opened valves 2 and 6). Most recent entry: `VALVES:110001_,_111111..OK..$..MAN#1:60,40;..Bound:1->2..$CTR:181210,FLOW:15420$`. Confirms the `STAT`/`VALVES` bitmask ordering (digit 1-6 left-to-right = valve 1-6) and that manual runs show up as `MAN#...` task lines instead of `NO_TASK`/`Output_...`. |
| `dashboardReadRaw_running.json` | `GET /api/dashboardReadRaw/{siteId}` | Same time window as `readRaw_running.json`. |
| `apiCall_running.json` | `POST /api/call` (live query) | Live-query response during the same manual run: `VALVES:110001_,_111111..OK..$CTR:181246,FLOW:9000$CTR2:158,FLOW2:0$FCTR1:3,FLOW:0..$ENA:1..$Day:6_Time:10:23:47_DYC:1435..$..MAN#1:57,400;..Bound:1->2..$`. |
| `readRaw_suspended.json` | `GET /api/readRaw/{siteId}` | First 40 entries, captured right after **suspending irrigation for 12 days via the portal**. Most recent entries show `ENA:0..OK$ENA:11..OK$ENA:11..$` (toggle confirmation) followed by `STAT:000000,CTR:181410,L/H:0,ENA:11;` - i.e. `ENA` flips from `1` (normal) to `11` (suspended). No field anywhere encodes the remaining suspend duration. Also includes `BOUNDS:..1:2,1,1....OK..$`, confirming the valve 1->2 binding configuration. |
| `apiCall_suspended.json` | `POST /api/call` (live query) | Live-query response while suspended: `...ENA:11..$..NO_TASK..$` (vs `ENA:1..$` when not suspended). |
| `readPlans_dayrestricted.json` | `GET /api/readPlans/{siteId}` | Captured after restricting plan 5.1 to **Monday+Tuesday only**: `...3..5,1,0440,147,6,0,0,0`, i.e. `daysBitmask = 6` (`0b0000110` = bits 1,2 = Mon,Tue). Confirms the bit0=Sunday mapping used in `_async_refresh_windows`. |

See `info.md` in the repo root for the full field-by-field breakdown of these
formats.
