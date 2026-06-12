# Cellomatics Irrigation for Home Assistant

A custom Home Assistant integration for **Cellomatics** cellular irrigation
controllers (cellomatics.com), via their (unofficial, reverse-engineered) web
API.

> ⚠️ This integration uses an unofficial, reverse-engineered API. It is not
> affiliated with or endorsed by Cellomatics. The API may change without
> notice and break this integration.

## Features

- **Valve states** (open/closed) for each configured valve (controllers
  support 4-6 valves; the actual count is auto-detected on setup), as binary
  sensors.
- **Live flow rates** (main, zone 2, fertilizer) in L/h.
- **Cumulative flow counters** (main, zone 2, fertilizer) in liters
  (`total_increasing`, compatible with Utility Meter helpers).
- **Battery voltage** (mV), shown as a diagnostic sensor.
- **Irrigation status**: `idle`, `running`, or `suspended` (when irrigation
  has been paused via the portal's "suspend for N days" feature, `ENA != 1`
  - takes priority over idle/running). Has `enabled` and `last_update`
  attributes; the latter shows when this sensor's data was last refreshed
  (from either a scheduled or a manually-triggered update). Note: the API
  does not expose the remaining suspend duration, only whether it's
  currently suspended.
- **Water used today** (liters), derived from the controller's daily report.

## Services

Two services are provided for use in Developer Tools → Actions, or in your
own automations/scripts:

- **`cellomatics.force_passive_update`** - immediately performs a passive
  read (`readRaw`) of battery level, valve states, main flow, and
  idle/running status, without waking the cellular controller. Cheap, safe
  to call often.
- **`cellomatics.force_active_update`** - immediately performs an active
  poll (`/api/call`) of live valve states and flow rates (main, zone 2,
  fertilizer). This wakes the cellular controller over its cellular link -
  use sparingly (e.g. right after manually starting/stopping irrigation, to
  refresh state without waiting for the next scheduled poll).

Both services target the Cellomatics device; if no target is given they
apply to all configured Cellomatics sites. Successful updates are logged at
debug level (enable debug logging on the integration to see them).

## Polling strategy

To avoid unnecessarily waking the cellular controller (battery + cellular
cost), this integration:

- Reads the configured irrigation plans once a day to determine today's
  run window(s) (start time -> start + duration).
- During a run window, polls live data (`/api/call`) every 15 minutes,
  except at the top of each hour — at that point it just reads the
  controller's own hourly auto-report instead of actively polling.
- Outside run windows, it passively reads the hourly auto-report once an
  hour (for battery level / idle status).
- Once a day, it reads the daily usage report to populate "Water Used
  Today".

Login session cookies are held in memory only; the integration
re-authenticates automatically whenever the session expires.

## Installation

### HACS (custom repository)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/Galala7/ha-cellomatics`.
3. Install "Cellomatics Irrigation" from HACS.
4. Restart Home Assistant.

### Manual

1. Copy `custom_components/cellomatics` into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

Configuration is done entirely via the UI:

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for "Cellomatics Irrigation".
3. Enter your portal username, password, and irrigation site ID
   (e.g. `0501234567`).

## Example dashboard

See [`examples/lovelace.yaml`](examples/lovelace.yaml) for a sample Lovelace
dashboard card showing status, valves, flow rates, battery, water used
today, and buttons to trigger the `force_passive_update` /
`force_active_update` services. Update the entity IDs in the example to
match your installation (check **Settings → Devices & Services →
Cellomatics Irrigation → Entities**).

## Known limitations / open items

- "Water Used Today" reflects zone 1.2 (`TE,1,2,...` report entries).
  If your setup uses different zone/action numbers, this will need to be
  made configurable.
- The `suspended` status reflects only the current on/off state of the
  controller's enabled flag - it cannot show how many days remain on a
  portal-initiated suspend, since the API doesn't expose that.

### TODO - not yet implemented

These are known configuration features of the Cellomatics controller that
are **not yet surfaced in Home Assistant**. They're noted here for future
work:

- **Valve binding** (`Bound:N->M` in the telemetry): a valve can be
  configured to mirror another valve - e.g. on this site, valve 2 is bound
  to valve 1, so valve 2 opens/closes whenever valve 1 does. The integration
  currently just reports the raw per-valve state (which already reflects
  bound valves following their "leader"); it does not expose or make use of
  the binding relationship itself (e.g. to label/group bound valves, or
  read the binding configuration from the API).
- **Configurable "main" valve**: one valve (valve 6 on this site) is
  designated as the main supply valve and opens automatically whenever any
  other valve runs. This is a per-site configuration setting on the
  controller (any valve could be designated as "main") and is not currently
  read or exposed by the integration.

## License

Apache License 2.0 - see [LICENSE](LICENSE).
