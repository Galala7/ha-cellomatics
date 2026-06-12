# Cellomatics Irrigation for Home Assistant

A custom Home Assistant integration for **Cellomatics** cellular irrigation
controllers (cellomatics.com), via their (unofficial, reverse-engineered) web
API.

> ⚠️ This integration uses an unofficial, reverse-engineered API. It is not
> affiliated with or endorsed by Cellomatics. The API may change without
> notice and break this integration.

## Features

- **Valve states** (open/closed) for all 6 valves, as binary sensors.
- **Live flow rates** (main, zone 2, fertilizer) in L/h.
- **Cumulative flow counters** (main, zone 2, fertilizer) in liters
  (`total_increasing`, compatible with Utility Meter helpers).
- **Battery voltage** (mV).
- **Irrigation status** (idle/running), with a `last_update` attribute
  showing when this sensor's data was last refreshed (from either a
  scheduled or a manually-triggered update).
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

## Known limitations / open items

- The mapping from the plan "days" bitmask to weekdays is based on an
  assumption (bit 0 = Sunday) that has only been validated for the
  "every day" case (`127`). If you have a plan that doesn't run every
  day and the run-window detection seems off, please open an issue.
- "Water Used Today" reflects zone 1.2 (`TE,1,2,...` report entries).
  If your setup uses different zone/action numbers, this will need to be
  made configurable.
- Login session cookies are held in memory only; the integration
  re-authenticates automatically when the session expires.

## License

TBD.
