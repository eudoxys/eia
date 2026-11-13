# Changelog

All notable changes to `eia` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions
follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

First public release. Changes since the initial import:

### Added

- CLI subcommands `generation_monthly` (Form 923) and `region_fuel_hourly`
  (Form 930 fuel mix) (#34).
- Plant-level Form 923 data and `Form930Fuel` (#1).
- `eia.__version__`, read from the installed package metadata (#22).
- Documentation deployed with GitHub Pages (#26, #41), `DESIGN.md` (#24),
  and a Claude Code skill (#2).

### Changed

- Form 930 data start in January 2019 for both `Form930` and `Form930Fuel`,
  the first month the EIA API v2 serves (previously July 2015 and July
  2018, which returned empty frames); earlier years raise `ValueError` (#48).
- The test suite uses `pytest` (#21). Tests are split by module under
  `tests/test_*.py`, run offline by default against small synthetic EIA
  workbooks and API responses, and the tests that download data from EIA
  are marked `network` (run them with `pytest -m network`).
- **Breaking:** consistent public API across all forms (#19). Every form
  takes `Form(year, month=None, *, <filters>, raw=False, refresh=False)`;
  filters and options are keyword-only, and Form 930 takes
  `respondent=` instead of a leading `region`/`respondent` argument
  (`Form930(2020, 8, respondent="CAL")`). Every frame is indexed by a UTC
  `timestamp` (beginning of the month or hour) followed by its natural keys,
  and all column names are lower-case with a unit suffix (e.g., Form 860m
  `NAMEPLATE_MW` → `nameplate_mw`, Form 930 `load_MW` → `load_mw`,
  `NG_MW` → `ng_mw`). The `date` column/index level is now `timestamp`.
- `HS861m` is renamed `Form861mSales` (module `eia.form861msales`) (#19).
- `raw=True` is supported by every form, including `Form923`, `Form930`,
  and `Form930Fuel` (#19); `Form861m` accepts `month=None` for a whole year.
- Pandas operations on a form return plain `pandas.DataFrame` objects (#19).
- CLI: `-r/--respondent` is the primary name of the Form 930 option
  (`--region` still works), and `.xlsx` output writes UTC timestamps without
  a time zone (#19).
- Downloaded data are cached in the user cache folder instead of inside the
  installed package (#36).
- Uniform network handling, published-month bounds, and refreshable Form 930
  reference data (#38).
- Invalid arguments raise exceptions instead of failing `assert` checks (#37).
- `pyproject.toml` metadata uses PEP 621 author fields and a PEP 639 license
  expression (#22).
- Usage demos moved from the modules' `__main__` blocks to `examples/`;
  Form 861m and Form 923 share one download helper, and `eia.cli` no longer
  imports the `eia` package (#23).

### Deprecated

- `HS861m` (and `eia.hs861m`) remain as a compatibility class with the
  former interface (`date` index level, `state`-only index for a single
  month, positional `refresh` and `raw`) and issue a `DeprecationWarning`;
  use `Form861mSales` instead (#19).

### Fixed

- CLI `bulk_generation` uses Form 860m (#28), `region_hourly` works (#29),
  and output formats and error reporting are handled correctly (#35).
- `customer_demand` (HS861m) year and month handling (#30).
- `raw=True` on the Form 861m sales table applies the `year` and `month`
  selection (#27).
- Corrupt Form 860m cache files are reported instead of raising
  `UnboundLocalError` (#31).
- `Form860m(..., raw=True)` returns integer columns such as `Plant ID` as
  EIA's original text (`"10"`, not `"10.0"`). The Form 860m cache version
  is now 2, so existing Form 860m caches are ignored and the workbooks are
  downloaded again (#47).
- Form 861m keeps its cache when a month is missing and tries both URLs (#32).
- Form 930 API key lookup works on Windows and never leaks the key (#39).
- Form 930 UTC timestamps (#1).
- README and docstrings match the package behaviour (#40, #25).

### Removed

- Unused `pytz` dependency (#33).
- `Form923.FORM923_URL` (use `Form923.FORM923_URLS`) (#23).

[Unreleased]: https://github.com/eudoxys/eia/commits/main
