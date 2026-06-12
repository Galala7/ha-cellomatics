## Cellomatics Irrigation API — Technical Summary

### Authentication flow
The portal uses ASP.NET cookie auth via a mobile login form. Steps required:

1. **GET** `https://www.cellomatics.com/online_platformn_ns124`
   → 302 redirect to `/loginmob`, sets `ASP.NET_SessionId` cookie. Save cookie jar.

2. **GET** `https://www.cellomatics.com/loginmob` (with session cookie)
   → returns HTML form containing hidden fields: `__VIEWSTATE`, `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION` (must be re-extracted each time, they're per-session/per-request).

3. **POST** `https://www.cellomatics.com/loginmob` (with same session cookie), form-urlencoded body:
   - `__VIEWSTATE`, `__VIEWSTATEGENERATOR`, `__EVENTVALIDATION` (from step 2)
   - `UserName=<username>`
   - `Password=<password>`
   - `Button2=Login`
   → 302 to `/online_platformn_ns124`, sets new cookie **`.AspNet.ApplicationCookie`** (this is the auth token, validity ~14 days based on observed `expires`).

4. All subsequent `/api/...` calls just need the **`.AspNet.ApplicationCookie`** cookie sent. `ASP.NET_SessionId` doesn't seem strictly required afterward but keep it too for safety.

→ For HA, this means a periodic re-login job (e.g. daily) to refresh the cookie before it expires, then use the cookie for polling.

### API endpoints (passive DB reads)
Base path: `/api/<endpoint>/<siteId>` where siteId = `&lt;site_id&gt;`.

All return JSON arrays of records shaped like:
```json
{"devId":..., "stringParam":..., "stringParam_2":..., "stringParam_3":..., "stringParam_4":..., "intParam":..., "dateTime":..., "devIds":..., "flowRate":...}
```
Most fields are null/unused — `stringParam`, `intParam`, and `dateTime` carry the actual content.

#### `/api/readValvesCount/{siteId}`
Single record, `stringParam` = number of valves (e.g. `"6"`).

#### `/api/readValvesNames/{siteId}`
One record per valve (`intParam` = valve index 1-6):
- `stringParam` = valve display name (numeric default, or custom Hebrew name like "דשן", "שכן", "ראשי")
- `stringParam_2` = appears related to flow-meter quantity setting (e.g. `"15000"` for valve 1, `"0"` for others)

Site's valve map:
| # | Name | Role |
|---|---|---|
| 1 | (default "1") | Main zone, flow-metered, runs plan "1.2" |
| 2 | (default "2") | Bound to valve 1 (mirrors its state, `Bound:1->2`) |
| 3 | דשן | Fertilizer/dosing valve |
| 4 | (default "4") | spare |
| 5 | שכן | Neighbor zone, plan "5.1", no flow meter |
| 6 | ראשי | Main supply valve (opens whenever any other zone runs) |

Notes on configuration (controller-side, not currently read/exposed by the
HA integration - see README TODO section):
- Controllers support **4-6 valves** (`readValvesCount` returns the
  configured count for this site). The `STAT`/`VALVES` bitmasks always
  appear to be 6 digits regardless of configured count.
- **Valve binding** (`Bound:N->M`): valve M is configured to mirror valve
  N's open/closed state. On this site, valve 2 is bound to valve 1.
- **"Main" valve**: exactly one valve (valve 6 here, ראשי) is configured as
  the main supply valve and opens automatically alongside any other valve
  that runs. Which valve plays this role is a per-site setting and could in
  principle be any valve 1-6.

#### `/api/readParams/{siteId}`
Single record, `stringParam` = device status code string, e.g. `"ENA:1..OK$ENA:1..$"` (enabled flag + ack), `dateTime` = timestamp of last param update.

#### `/api/readRaw/{siteId}` and `/api/dashboardReadRaw/{siteId}`
Same underlying hourly/event telemetry stream, but **`dashboardReadRaw` is a filtered subset**: it only includes the task (`NO_TASK`/`Output_...`), `VEN`, and `STAT` lines. `BAT` (battery) and `BAL` lines are **only present in `readRaw`**, so the integration polls `readRaw` for its passive updates. Records are key-value strings with `intParam` indicating message type (2 = status line, 3 = task/event line). Key tokens seen:

- `STAT:bbbbbb,CTR:nnnnnn,L/H:n,ENA:n;` — `STAT` = 6-digit valve on/off bitmask (one digit per valve, 1=open/active); `CTR` = cumulative main flow-meter pulse counter; `L/H` = current flow rate (liters/hour); `ENA` = system enabled flag (see below).
- `,VEN:111111,D2:0;` — per-valve "vent"/configured-enabled mask (all 1s = all valves configured), `D2` = secondary digital input/output state.
- `,BAT:nnnn;` — battery voltage in mV.
- `..NO_TASK..$` — no irrigation task currently scheduled/running.
- `..Output_N_(min,count): m,c,f..` — countdown for output/valve N: `m` = minutes remaining, `c` = pulse count target/limit, `f` = flow counter snapshot.
- `Bound:1->2` — sequence transition between outputs (e.g., main valve 1 followed by valve 2 step in a multi-step plan).
- `IO:nn,SPA:nn,STAT:bbbbbb;` — extra digital I/O register and a spare/analog reading, plus the status bitmask.
- `BOUNDS:..N:M,a,b....OK..$` — reports a configured valve binding (valve `N` bound to valve `M`, with flag values `a,b`). Seen as `BOUNDS:..1:2,1,1....OK..$` on this site (valve 1 -> valve 2 binding).
- `ENA:n` — system enabled flag. `ENA:1` = normal/enabled. Other values (`0`, `11`, ...) indicate irrigation is currently suspended/disabled — see "Suspend mode" below. When toggling, multiple `ENA:` tokens can appear concatenated in one entry, e.g. `ENA:0..OK$ENA:11..OK$ENA:11..$`.

#### Suspend mode ("vacation"/pause for N days)
The portal has a feature to suspend all irrigation for a configurable number
of days. Observed effect on the API (captured 2026-06-12, suspending for 12
days):
- `ENA` flips from `1` to `11` (via a transient `0`), in `readRaw`,
  `readParams`, and the live `/api/call` response (`ENA:11..$`).
- **No field anywhere exposes the remaining suspend duration or an end
  date** — `readPlans` is unchanged, and no other endpoint/token carries a
  day-count. The 12-day duration appears to be tracked server-side only.
- The integration therefore only exposes a binary "suspended" state
  (`ENA != 1`), not a countdown.

#### `/api/readPlans/{siteId}`
Single record, `stringParam` = one or more plan definitions concatenated with `..`, each comma-separated:
```
<body>,<action>,<startTime HHMM>,<duration min>,<daysBitmask>,<fertLiters>,<waterQtyLiters>,<waterBeforeLiters>,<fertBody>
```
- `daysBitmask`: 7-bit mask over (א,ב,ג,ד,ה,ו,ש) = (Sun,Mon,Tue,Wed,Thu,Fri,Sat),
  bit0 (LSB) = Sunday ... bit6 = Saturday. `127` = 0b1111111 = all days.
  **Confirmed 2026-06-12**: restricting plan 5.1 to Monday+Tuesday produced
  `daysBitmask = 6` (`0b0000110` = bits 1,2 = Mon,Tue), matching this
  mapping. See `samples/readPlans_dayrestricted.json`.
- `fertBody`/`fertLiters` only present when fertilization is configured (plan "1.2" doses 8L via valve 3, with 100L water-before).
- `dateTime` on this record = timestamp of last plan edit (not a schedule occurrence).

Current plans on this site:
- **Plan 1.2** (body 1): 04:40 start, 147 min, all days, 60000L limit, 100L water-before, 8L fert via valve 3.
- **Plan 5.1** (body 5/שכן): 04:40 start, 147 min, **Monday+Tuesday only**
  (`daysBitmask = 6`), 0L (no flow meter / unmetered).

#### `/api/readReport/{siteId}/{startDate M-D-YY}/{endDate M-D-YY}`
Daily history records, `stringParam` format:
```
TE,<body>,<action>,<duration min>,<value>,0.0,0.0;
```
- One entry per plan per day it ran.
- `duration` reflects the plan's duration setting *at the time* (changed from 200→147 min on 5/26, matching the `readPlans` edit timestamp).
- `value` for `TE,1,2,...` (metered zone) = liters delivered that day (ranges ~100-44000L depending on whether the run completed/looped).
- `value` for `TE,5,1,...` (unmetered zone) = a smaller secondary counter, not volume.

### `/api/call` — live device query (active poll)
**POST** `https://www.cellomatics.com/api/call` (no siteId in path — goes in body).
Requires the `.AspNet.ApplicationCookie` cookie. Recommended headers: `Content-Type: application/json; charset=UTF-8`, `X-Requested-With: XMLHttpRequest`.

Request body:
```json
{"devId":"&lt;site_id&gt;","intParam":14,"stringParam":"valves;!flow;!flow2;!fert flow;!get ena;!ptime;!status;!"}
```
- `stringParam` is a `!`-terminated list of command tokens sent live to the cellular controller — possibly customizable to request a subset of data.
- This call **actively wakes/queries the physical device over its cellular link** (took ~4s round trip) — unlike the `read*` endpoints which just read from the DB. Should be polled sparingly (e.g. every 15-30 min, not every few seconds) to avoid battery/cellular cost.

Response: a single JSON string (not array-of-objects like other endpoints):
```
"VALVES:000000_,_111111..OK..$CTR:181191,FLOW:0$CTR2:158,FLOW2:0$FCTR1:3,FLOW:0..$ENA:1..$Day:5_Time:19:00:22_DYC:1434..$..NO_TASK..$"
```
- `VALVES:aaaaaa_,_bbbbbb` — `aaaaaa` = current valve open/closed state (6 digits, one per valve, 1=open); `bbbbbb` = configured/enabled mask.
- `CTR:nnnnnn,FLOW:n` — main flow meter counter + current flow rate.
- `CTR2:nnnnnn,FLOW2:n` — second flow meter counter + rate (likely valve 5/שכן line).
- `FCTR1:n,FLOW:n` — fertilizer flow meter counter + rate.
- `ENA:1` — system enabled.
- `Day:D_Time:HH:MM:SS_DYC:n` — device's internal clock (Day=weekday number) and a day/cycle counter (`DYC`).
- `..NO_TASK..` — no irrigation currently running (or shows active task info if one is running).

### Open items / assumptions to validate later
- ~~`STAT`/`VALVES` bitmask digit-to-valve ordering (left-to-right vs reversed) not yet 100% confirmed against UI.~~
  **Confirmed 2026-06-12**: during a manual run on valve 1 (which auto-opened
  valves 2 and 6), `readRaw`/`apiCall` showed `VALVES:110001_,_111111` -
  digit position 1-6 left-to-right = valve 1-6, `1` = open. See
  `samples/readRaw_running.json` / `samples/apiCall_running.json`.
- `TE,5,1` value's exact meaning (likely a pulse/time counter, not liters) — could confirm by watching it during/after a שכן-only run.
- Cookie expiry/refresh cadence for unattended polling needs real-world testing (observed `expires` ~14 days from login).
- Whether `stringParam` command list in `/api/call` can be trimmed to reduce device load, and what other command tokens exist.

This should be enough to design the HA polling integration — let me know when you want to move to that.
