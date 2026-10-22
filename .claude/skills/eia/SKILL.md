---
name: eia
description: Retrieve US EIA electricity data (Forms 860m, 861m, 923, 930 and the 861m sales/revenue table) as pandas data frames with the eudoxys `eia` package. Use when a task calls for generator inventories, small-scale solar, retail sales, monthly net generation by BA/plant/fuel, or hourly BA load, generation, interchange or fuel mix.
---

# eia: EIA form data accessor

The `eia` package (https://github.com/eudoxys/eia) downloads EIA form data,
caches it locally, and returns each form as a `pandas.DataFrame` subclass.
This file records which class serves which data request, the exact shape of
each returned frame, and the known limitations of the current release.

## Installation

```bash
pip install git+https://github.com/eudoxys/eia
```

Python 3.11 or later. Dependencies: `pandas`, `openpyxl`, `requests`,
`pytz`, and `cache` (https://github.com/eudoxys/cache).

## Selecting a form

| Data needed | Class | Resolution | Coverage |
|---|---|---|---|
| Generator inventory (operating, planned, retired units ≥1 MW) | `Form860m` | one month snapshot, per generator | 2015 → present |
| Small-scale (<1 MW) solar capacity and energy by state and sector | `Form861m` | monthly, per state | 2017 → present |
| Retail sales, revenue, customers, price by state and sector | `HS861m` | monthly, per state | full EIA table |
| Net generation by state, BA and fuel, or by plant | `Form923` | monthly | 2008 → present |
| Hourly load, net generation, interchange per BA or region | `Form930` | hourly (UTC) | July 2015 → present |
| Hourly net generation by energy source per BA or region | `Form930Fuel` | hourly (UTC) | July 2018 → present |

All classes import from the package root:

```python
from eia import Form860m, Form861m, HS861m, Form923, Form930, Form930Fuel
```

Use the Python API rather than the `eia` command line for anything other
than Form 861m and HS 861m (see *Command-line limitations* below).

## Class reference

### `Form860m(year, month, subset=None, refresh=None, raw=None)`

- `subset`: one of `Operating` (default), `Planned`, `Retired`,
  `Canceled or Postponed`, `Operating_PR`, `Planned_PR`, `Retired_PR`
  (these are the sheet names of the EIA workbook).
- Returns a frame with a default `RangeIndex`, one row per generator, and
  upper-case columns: `OWNER_ID`, `OWNER_NAME`, `ID` (plant id), `NAME`,
  `STATE`, `COUNTY`, `BA_CODE`, `SECTOR`, `GENERATOR_ID`, `UNIT_CODE`,
  `NAMEPLATE_MW`, `SUMMER_MW`, `WINTER_MW`, `TECHNOLOGY`,
  `ENERGY_SOURCE_CODE`, `PRIME_MOVER_CODE`, `OPERATING_MONTH`,
  `OPERATING_YEAR`, `PLANNED_RETIREMENT_MONTH`, `PLANNED_RETIREMENT_YEAR`,
  `STATUS`, `NAMEPLATE_MWH`, `DC_NET_MW`, planned derate/uprate columns,
  `LAT`, `LON`.
- Columns absent from a given month's sheet are filled with a default
  (`0` for integers, `NaN` for floats, `""` for strings).
- `raw=True` returns the EIA sheet as strings with the original headers.
- The class docstring mentions `date` and `state` columns; those are not
  present. Use `STATE` and the requested `year`/`month`.

```python
gen = Form860m(2024, 6)                       # operating fleet, June 2024
gen.groupby(["STATE", "ENERGY_SOURCE_CODE"])["NAMEPLATE_MW"].sum()
planned = Form860m(2024, 6, subset="Planned")
```

### `Form861m(year, month, refresh=False, raw=False)`

- Small-scale solar only (the EIA `small_scale_solar_{year}.xlsx` workbook).
- Returns a `RangeIndex` frame with columns `date` (UTC, first of month),
  `state`, `res_mw`, `com_mw`, `ind_mw`, `tot_mw`, `res_mwh`, `com_mwh`,
  `ind_mwh`, `tot_mwh`. Missing and non-numeric values are set to `0.0`.
- One workbook is downloaded per year; individual months are held in an
  in-process cache.

```python
dg = Form861m(2020, 8)
dg.set_index("state").loc["WA", ["tot_mw", "tot_mwh"]]
```

### `HS861m(year, month, refresh=False, raw=False)`

- Loads the full EIA `sales_revenue.xlsx` table once per process.
- With `year` and `month`: frame indexed by `state`.
  With `month=None`: frame indexed by (`date`, `state`) for that year.
  With `year=None`: every month in the table.
- Columns follow `{sector}_{quantity}_{unit}`, with sectors `res`, `com`,
  `ind`, `tra`, `tot` and quantities `revenue_kusd` (thousand USD),
  `energy_mwh`, `customers_qty`, `price_cpkwh` (US cents per kWh).
- Missing values are set to `0.0` unless `raw=True`.

```python
sales = HS861m(2022, 7)
sales.loc["CA", ["res_energy_mwh", "res_price_cpkwh"]]
```

### `Form923(year, month=None, states=None, bas=None, fuels=None, *, by="ba", plants=None, increments=True, precision=3, refresh=False, nonzero=True)`

- `by="ba"` → MultiIndex (`timestamp`, `state`, `ba`, `fuel`).
  `by="plant"` → MultiIndex (`timestamp`, `state`, `ba`, `plant`, `pm`,
  `fuel`). Single column `gen_mwh` (net generation, MWh).
- `month=None` returns all twelve months of the year.
- `states`, `bas`, `fuels`, `plants` accept a single value or a list.
  Fuel codes are EIA reported fuel type codes (e.g. `NG`, `WAT`, `NUC`,
  `SUN`, `WND`, `BIT`, `SUB`).
- Net generation can be negative (pumped storage, batteries, station use).
  `nonzero=True` removes zero and missing rows only.
- Plant id `99999` rows are EIA state-fuel increment estimates for plants
  not surveyed monthly; exclude them with `increments=False`.
- The two most recent years raise a warning because EIA has not finalized
  them.

```python
Form923(2020, 8, fuels=["NG", "WAT"], bas="CISO")
Form923(2020, 8, states="CA", fuels="WAT", by="plant")
Form923(2022).groupby(level="fuel")["gen_mwh"].sum()   # annual totals
```

### `Form930(region, year, month=None, *, refresh=False)`

- Requires an EIA Open Data API key (register at
  https://www.eia.gov/opendata/register.php), stored in the environment
  variable `EIA_API_KEY` or in the file `~/.eia/api_key`.
- `region`: a BA or region code from `Form930.respondents()` (e.g. `CISO`,
  `BPAT`, `ERCO`, `CAL`, `NW`). Calling `respondents()` downloads the EIA
  930 reference workbook once.
- Returns a `RangeIndex` frame with `timestamp`, `load_MW`,
  `generation_MW`, `interchange_MW` (positive interchange is export).
- `month=None` returns the whole year; months before July 2015 are skipped.

### `Form930Fuel(respondent, year, month=None, *, fuels=None, refresh=False)`

- Same API key and respondent codes as `Form930`; data starts July 2018 and
  a request with no months in range raises `ValueError`.
- Returns `timestamp` plus one `{code}_MW` column per energy source the
  respondent reports (e.g. `NG_MW`, `NUC_MW`, `SUN_MW`, `WAT_MW`,
  `WND_MW`). Codes never reported in the period are omitted; missing hours
  are `NaN`.

### Time convention for Form 930

The EIA API reports UTC hour-ending values. Both Form 930 classes shift them
to UTC **hour-beginning**: the row at `2020-08-01 00:00:00+00:00` covers
00:00–01:00 UTC, and each month has exactly `24 × days` rows. Convert to
local time with `df.timestamp.dt.tz_convert("America/Los_Angeles")`.

## Caching

- `Form860m` and `Form861m` cache downloaded workbooks in `eia/.cache`
  inside the installed package (override with the class attribute
  `CACHEDIR` before constructing).
- `Form923`, `Form930`, `Form930Fuel` and `HS861m` use the `cache`
  package, stored under `{cache package}/.cache/eia/{version}/...`. The
  `cache` command (`cache size --package eia`, `cache clear --package eia`)
  inspects or clears it.
- Pass `refresh=True` to re-download a period, for example after EIA
  revises the most recent months.

## Command-line limitations (current release)

The `eia` command accepts `bulk_generation`, `customer_demand`,
`distributed_generation`, `region_hourly` and `help`, with `-y`, `-m`,
`--subset`, `--raw`, `--refresh`, `-o OUTPUT` and
`-f {csv,gzip,zip,xlsx}`. Known defects:

- `bulk_generation` maps to `Form861m`, not `Form860m`; it returns
  small-scale solar data.
- `region_hourly` fails with `'Form930' has no attribute 'makeargs'`.
- Form 923 and `Form930Fuel` have no command-line entry.
- `.xlsx` output always uses the sheet name `Form861`.

`distributed_generation` and `customer_demand` operate correctly:

```bash
eia distributed_generation -y 2020 -m 8 -o dg_2020_08.csv
eia customer_demand -y 2022 -m 7 -o sales_2022_07.xlsx
```

## Troubleshooting

- `AssertionError: year=... is not valid`: the year is outside the
  coverage table above, or later than the current calendar year.
- `HTTP error 404` on recent months: EIA has not yet posted that month;
  the monthly forms are published with a lag of one month or more.
- `BadZipFile` or `unable to read ... deleting invalid cache file`: EIA
  returned an HTML error page instead of a workbook; the bad cache file is
  removed automatically, so retry later or with `refresh=True`.
- `FileNotFoundError` for `~/.eia/api_key`: no API key is configured for
  Form 930.
- Network sandboxes that block `www.eia.gov` or `api.eia.gov` make every
  class fail at download time; previously cached periods still load.
