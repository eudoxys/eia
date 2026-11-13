---
name: eia
description: Retrieve US EIA electricity data (Forms 860m, 861m, 923, 930 and the 861m sales/revenue table) as pandas data frames with the eudoxys `eia` package. Use when a task calls for generator inventories, small-scale solar, retail sales, monthly net generation by BA/plant/fuel, or hourly BA load, generation, interchange or fuel mix.
---

# eia: EIA form data accessor

The `eia` package (https://github.com/eudoxys/eia) downloads EIA form data,
caches it locally, and returns each form as a `pandas.DataFrame`.
This file records which class serves which data request, the exact shape of
each returned frame, and the known limitations of the current release.

## Installation

```bash
pip install git+https://github.com/eudoxys/eia
```

Python 3.11 or later. Dependencies: `pandas`, `openpyxl`, `requests`,
`platformdirs`, and `cache` (https://github.com/eudoxys/cache).

## Selecting a form

| Data needed | Class | Resolution | Coverage |
|---|---|---|---|
| Generator inventory (operating, planned, retired units ≥1 MW) | `Form860m` | one month snapshot, per generator | 2015 → present |
| Small-scale (<1 MW) solar capacity and energy by state and sector | `Form861m` | monthly, per state | 2017 → present |
| Retail sales, revenue, customers, price by state and sector | `Form861mSales` | monthly, per state | full EIA table |
| Net generation by state, BA and fuel, or by plant | `Form923` | monthly | 2008 → present |
| Hourly load, net generation, interchange per BA or region | `Form930` | hourly (UTC) | January 2019 → present |
| Hourly net generation by energy source per BA or region | `Form930Fuel` | hourly (UTC) | July 2018 → present |

All classes import from the package root:

```python
from eia import Form860m, Form861m, Form861mSales, Form923, Form930, Form930Fuel
```

Every class is also available from the `eia` command line (see *Command
line* below); use the Python API when you need the data frame itself.

## Conventions shared by every form

- Signature `Form(year, month=None, *, <filters>, raw=False, refresh=False)`.
  Only `year` and `month` are positional; pass everything else by keyword.
  `Form930`/`Form930Fuel` require `respondent=`. `Form860m` requires `month`.
- `year`/`month` accept `int` or numeric `str`; `month` also accepts names
  such as `"Jul"`. `month=None` returns the whole year.
- Filters accept one value or a list; `None` means all.
- The index starts with `timestamp` (tz-aware UTC, beginning of the month
  or hour), followed by the row's natural keys. Use `df.xs("CA",
  level="state")` or `df.loc[(ts, "CA")]` to select; `df.reset_index()`
  gives a flat frame.
- Columns are lower case with unit suffixes `_mw`, `_mwh`, `_kusd`
  (thousand USD), `_cpkwh` (US cents per kWh), `_qty` (count).
- `raw=True` returns EIA's data for the period with a `RangeIndex` and no
  renaming, coercion, or filtering (other filters are ignored).
- Results of pandas operations are plain `pandas.DataFrame` objects.

## Class reference

### `Form860m(year, month, *, subset=None, raw=False, refresh=False)`

- `subset`: one of `Operating` (default), `Planned`, `Retired`,
  `Canceled or Postponed`, `Operating_PR`, `Planned_PR`, `Retired_PR`
  (these are the sheet names of the EIA workbook).
- Index (`timestamp`, `plant`, `generator`); `timestamp` is the report
  month. Columns: `owner`, `owner_name`, `plant_name`, `state`, `county`,
  `ba`, `sector`, `unit`, `nameplate_mw`, `summer_mw`, `winter_mw`,
  `dc_net_mw`, `nameplate_mwh`, `technology`, `fuel` (energy source code),
  `pm` (prime mover code), `operating_month`, `operating_year`,
  `planned_retirement_month`, `planned_retirement_year`, `status`,
  `planned_derate_*`/`planned_uprate_*`, `latitude`, `longitude`.
- Columns absent from a given month's sheet are filled with a default
  (`0` for integers, `NaN` for floats, `""` for strings).
- `raw=True` returns the EIA sheet as strings with the original headers.

```python
gen = Form860m(2024, 6)                       # operating fleet, June 2024
gen.groupby(["state", "fuel"])["nameplate_mw"].sum()
planned = Form860m(2024, 6, subset="Planned")
```

### `Form861m(year, month=None, *, raw=False, refresh=False)`

- Small-scale solar only (the EIA `small_scale_solar_{year}.xlsx` workbook).
- Index (`timestamp`, `state`); columns `res_mw`, `com_mw`, `ind_mw`,
  `tot_mw`, `res_mwh`, `com_mwh`, `ind_mwh`, `tot_mwh`. Missing and
  non-numeric values are set to `0.0`.
- One workbook is downloaded per year and held in an in-process cache.

```python
dg = Form861m(2020, 8)
dg.xs("WA", level="state")[["tot_mw", "tot_mwh"]]
```

### `Form861mSales(year=None, month=None, *, raw=False, refresh=False)`

- Loads the full EIA `sales_revenue.xlsx` table once per process.
- Index (`timestamp`, `state`) for any selection. `year=None` returns every
  year in the table; `month=None` every month of the selected year(s).
- Columns follow `{sector}_{quantity}_{unit}`, with sectors `res`, `com`,
  `ind`, `tra`, `tot` and quantities `revenue_kusd` (thousand USD),
  `energy_mwh`, `customers_qty`, `price_cpkwh` (US cents per kWh).
- Missing values are set to `0.0` unless `raw=True`.
- `raw=True` returns the selected rows with `year`, `month`, `state`,
  `status` columns.
- `HS861m` is the deprecated former name: it still works (former index
  `date`/`state`, `state` only for a single month) but warns with
  `DeprecationWarning`. Use `Form861mSales` in new code.

```python
sales = Form861mSales(2022, 7)
sales.xs("CA", level="state")[["res_energy_mwh", "res_price_cpkwh"]]
```

### `Form923(year, month=None, *, states=None, bas=None, fuels=None, plants=None, by="ba", increments=True, nonzero=True, precision=3, raw=False, refresh=False)`

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
- `raw=True` returns the EIA "Generation and Fuel Data" worksheet as
  strings with original headers; with `month`, other months' columns are
  dropped.

```python
Form923(2020, 8, fuels=["NG", "WAT"], bas="CISO")
Form923(2020, 8, states="CA", fuels="WAT", by="plant")
Form923(2022).groupby(level="fuel")["gen_mwh"].sum()   # annual totals
```

### `Form930(year, month=None, *, respondent, raw=False, refresh=False)`

- Requires an EIA Open Data API key (register at
  https://www.eia.gov/opendata/register.php), stored in the environment
  variable `EIA_API_KEY` or in the file `~/.eia/api_key`.
- `respondent`: a BA or region code from `Form930.respondents()` (e.g.
  `CISO`, `BPAT`, `ERCO`, `CAL`, `NW`). Calling `respondents()` downloads the
  EIA 930 reference workbook once and caches it; `refresh=True` downloads it
  again, and an unknown code triggers one automatic re-download.
- Indexed by `timestamp`; columns `load_mw`, `generation_mw`,
  `interchange_mw` (positive interchange is export).
- Data start in January 2019; `month=None` returns the whole year.
- `raw=True` returns the API records (`period` is UTC hour-ending).

### `Form930Fuel(year, month=None, *, respondent, fuels=None, raw=False, refresh=False)`

- Same API key and respondent codes as `Form930`; data starts July 2018 and
  a request with no months in range raises `ValueError`. July-December 2018
  comes from the EIA-930 six-month file (no API key; reported values only,
  codes `COL NG NUC OIL WAT SUN WND OTH UNK`; a region is the sum of its BAs;
  `raw=True` gives only `period`, `respondent`, `fueltype`, `value`).
- Indexed by `timestamp`; one `{code}_mw` column per energy source the
  respondent reports (e.g. `ng_mw`, `nuc_mw`, `sun_mw`, `wat_mw`,
  `wnd_mw`). Codes never reported in the period are omitted; missing hours
  are `NaN`. `fuels` codes are not case sensitive.

### Time convention for Form 930

The EIA API reports UTC hour-ending values. Both Form 930 classes shift them
to UTC **hour-beginning**: the row at `2020-08-01 00:00:00+00:00` covers
00:00–01:00 UTC, and each month has exactly `24 × days` rows. Convert to
local time with `df.index.tz_convert("America/Los_Angeles")`.

## Caching

- All forms cache under `{cache_dir}/eia/{version}/...`, where `cache_dir`
  is the folder set by `eia.set_cache_dir(path)`, else `$EIA_CACHE_DIR`,
  else the platform user cache folder (`~/.cache/eudoxys` on Linux,
  `~/Library/Caches/eudoxys` on macOS). Nothing is written inside the
  installed package. `eia.cache_dir()` returns the folder and
  `eia.clear_cache()` deletes all cached `eia` data.
- Pass `refresh=True` to re-download a period, for example after EIA
  revises the most recent months.

## Command line

The `eia` command takes a subcommand and shared options; each form uses only
the options it accepts and ignores the rest.

| Subcommand | Class | Form-specific options |
|---|---|---|
| `bulk_generation` | `Form860m` | `--subset` |
| `distributed_generation` | `Form861m` | |
| `customer_demand` | `Form861mSales` | |
| `generation_monthly` | `Form923` | `--state`, `--ba`, `--fuel`, `--plant`, `--by {ba,plant}`, `--no-increments` |
| `region_hourly` | `Form930` | `-r/--respondent` (required) |
| `region_fuel_hourly` | `Form930Fuel` | `-r/--respondent` (required), `--fuel` |

Common options: `-y YEAR`, `-m MONTH` (number, name, or abbreviation),
`--raw`, `--refresh`, `-o OUTPUT`, `-f {csv,gzip,zip,xlsx}`. List options
take comma-separated values, e.g. `--fuel NG,WAT` or `--plant 6099,286`.

```bash
eia distributed_generation -y 2020 -m 8 -o dg_2020_08.csv
eia generation_monthly -y 2020 -m 8 --ba CISO --fuel NG,WAT
eia region_fuel_hourly --respondent BPAT -y 2020 -m 8
```

`.xlsx` output names the sheet after the form class and writes UTC
timestamps without a time zone (Excel does not store time zones).

## Troubleshooting

- `ValueError: year=... is not valid`: the year is outside the
  coverage table above, or later than the current calendar year.
- `ValueError: ... is not published yet`: the month has not ended (monthly
  forms) or is in the future (Form 930).
- `HTTP error 404` on recent months: EIA has not yet posted that month;
  the monthly forms are published with a lag of one month or more.
- Slow or flaky connections: `eia.set_download_options(timeout=...,
  retries=...)` or the `EIA_TIMEOUT`/`EIA_RETRIES` environment variables
  (defaults 300 s and 3 retries).
- `BadZipFile` or `unable to read ... deleting invalid cache file`: EIA
  returned an HTML error page instead of a workbook; the bad cache file is
  removed automatically, so retry later or with `refresh=True`.
- `FileNotFoundError` for `~/.eia/api_key`: no API key is configured for
  Form 930.
- Network sandboxes that block `www.eia.gov` or `api.eia.gov` make every
  class fail at download time; previously cached periods still load.
