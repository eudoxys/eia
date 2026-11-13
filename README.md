[![validate](https://github.com/eudoxys/eia/actions/workflows/validate.yaml/badge.svg)](https://github.com/eudoxys/eia/actions/workflows/validate.yaml)

Access the following EIA Form data

  - Form 860m: Monthly inventory of generators of 1 MW or more

  - Form 861m: Monthly small-scale (under 1 MW) solar capacity and generation
    by state and sector

  - Form 861m sales: Monthly retail sales, revenue, customers, and price by
    state and sector
    (`Form861mSales`; the former name `HS861m` is deprecated)

  - Form 923: Monthly net generation by state, balancing authority, and fuel,
    or by plant, prime mover, and fuel

  - Form 930: Hourly load, net generation, and interchange by balancing
    authority or region, and hourly net generation by energy source

## Documentation

See https://www.eudoxys.com/eia

## Installation

    pip install git+https://github.com/eudoxys/eia

## Examples

### Command line

    eia distributed_generation --year 2020 --month 8

Hourly load, net generation, and interchange for California in August 2020
(Form 930)

    eia region_hourly --respondent CAL --year 2020 --month 8

Monthly net generation from natural gas and hydro in the CAISO balancing
authority for August 2020 (Form 923; add `--by plant` for plant-level data)

    eia generation_monthly --year 2020 --month 8 --ba CISO --fuel NG,WAT

Hourly net generation by energy source for the Bonneville Power
Administration in August 2020 (Form 930)

    eia region_fuel_hourly --respondent BPAT --year 2020 --month 8

### Python code

    from eia import Form861m
    Form861m(2020,8)

Monthly net generation from natural gas and hydro in the CAISO balancing
authority for August 2020 (Form 923)

    from eia import Form923
    Form923(2020,8,fuels=["NG","WAT"],bas="CISO")

Plant-level monthly net generation from hydro plants in California for August
2020 (Form 923)

    from eia import Form923
    Form923(2020,8,states="CA",fuels="WAT",by="plant")

Hourly load, net generation, and interchange for California in August 2020
(Form 930)

    from eia import Form930
    Form930(2020,8,respondent="CAL")

Hourly net generation by energy source for the Bonneville Power Administration
in August 2020 (Form 930)

    from eia import Form930Fuel
    Form930Fuel(2020,8,respondent="BPAT")

More complete scripts are in [`examples/`](examples/).

## Conventions

Every form follows the same API, so code written for one form carries over
to the others:

- **Signature:** `Form(year, month=None, *, <filters>, raw=False,
  refresh=False)`. Only `year` and `month` are positional; everything else is
  keyword-only. Form 930 requires `respondent=`, e.g.,
  `Form930(2020,8,respondent="CAL")`. `Form860m` requires `month`.
- **Period:** `year` and `month` accept an `int` or a numeric `str` (`month`
  also accepts a name such as `"Aug"`). `month=None` selects the whole year.
- **Filters** (`states`, `bas`, `fuels`, `plants`) accept one value or a
  list; `None` selects all.
- **Index:** `timestamp` (tz-aware UTC, beginning of the month or hour)
  followed by the natural keys of a row, e.g., `(timestamp, state, ba, fuel)`
  for Form 923 and `(timestamp, plant, generator)` for Form 860m. Form 930
  frames are indexed by `timestamp` only.
- **Columns:** lower case with a unit suffix on measured values: `_mw`,
  `_mwh`, `_kusd` (thousand US dollars), `_cpkwh` (US cents per kWh), `_qty`
  (count). Energy source columns use lower-cased EIA codes, e.g., `ng_mw`.
- **Raw data:** `raw=True` returns the EIA data for the requested period
  with a default integer index and no renaming, coercion, or filtering.
- **Return type:** the form classes are loaders. Pandas operations on a form
  (e.g., `.loc[]`, `.groupby()`) return plain `pandas.DataFrame` objects.

## Notes

- **Form 923** covers 2008 onward. Recent years are preliminary until EIA
  finalizes them. Net generation can be negative (e.g., pumped storage and
  batteries). Rows for plant `99999` are EIA's state-fuel level increment
  estimates; exclude them with `increments=False`.

- **Form 930** requires an EIA Open Data API key. Register at
  https://www.eia.gov/opendata/register.php, then store the key in the
  environment variable `EIA_API_KEY` or in the file `~/.eia/api_key`.
  Valid respondent codes are listed by `Form930.respondents()`.

- **Form 930 time convention:** timestamps are UTC and mark the *beginning*
  of the hour, so the value at `2020-08-01 00:00:00+00:00` covers 00:00 to
  01:00 UTC. Form 930 data (load, generation, interchange, and generation by
  energy source) start in January 2019, the first month the EIA API serves,
  except that `Form930Fuel` reads July to December 2018 from the EIA-930
  six-month files on the Hourly Electric Grid Monitor (no API key needed for
  those months; regions are the sum of their balancing authorities).

- Downloaded data are cached locally; pass `refresh=True` (or `--refresh` on
  the command line) to download again. See [Caching](#caching).

## Caching

Cache files are stored under `{cache_dir}/eia/{version}/`, never inside the
installed package, so read-only installs work and upgrades keep the cache.
The cache folder is chosen in this order:

1. the folder given to `eia.set_cache_dir(path)` (`None` restores the default),
2. the environment variable `EIA_CACHE_DIR`,
3. the platform user cache folder: `~/.cache/eudoxys` on Linux (or
   `$XDG_CACHE_HOME/eudoxys`), `~/Library/Caches/eudoxys` on macOS, and
   `%LOCALAPPDATA%\eudoxys\Cache` on Windows.

```python
import eia
eia.cache_dir()                    # where the cache is
eia.set_cache_dir("/data/eia")     # relocate it for this process
eia.clear_cache()                  # delete all cached eia data
```

To relocate the cache for the command line tool or all programs, set
`EIA_CACHE_DIR`, e.g., `export EIA_CACHE_DIR=/data/eia`. To clear it
without Python, delete the `eia` folder inside the cache folder.

## Claude Code skill

The file `.claude/skills/eia/SKILL.md` documents form selection, returned
data frame structure, caching, and current command-line limitations for use
with Claude Code. Claude Code loads it automatically when run from a clone of
this repository. To make it available in other projects, copy the folder:

    mkdir -p ~/.claude/skills
    cp -r .claude/skills/eia ~/.claude/skills/

## Issues

See https://github.com/eudoxys/eia/issues

## Acknowledgments

- This material is based on work supported by the U.S. Department of Energy’s Office of Electricity through a grant from the Grid Controls and Communications Division
