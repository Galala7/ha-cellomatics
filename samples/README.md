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

See `indo.md` in the repo root for the full field-by-field breakdown of these
formats.
