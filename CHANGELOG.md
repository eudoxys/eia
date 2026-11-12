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

- Downloaded data are cached in the user cache folder instead of inside the
  installed package (#36).
- Uniform network handling, published-month bounds, and refreshable Form 930
  reference data (#38).
- Invalid arguments raise exceptions instead of failing `assert` checks (#37).
- `pyproject.toml` metadata uses PEP 621 author fields and a PEP 639 license
  expression (#22).

### Fixed

- CLI `bulk_generation` uses Form 860m (#28), `region_hourly` works (#29),
  and output formats and error reporting are handled correctly (#35).
- `customer_demand` (HS861m) year and month handling (#30).
- Corrupt Form 860m cache files are reported instead of raising
  `UnboundLocalError` (#31).
- Form 861m keeps its cache when a month is missing and tries both URLs (#32).
- Form 930 API key lookup works on Windows and never leaks the key (#39).
- Form 930 UTC timestamps (#1).
- README and docstrings match the package behaviour (#40, #25).

### Removed

- Unused `pytz` dependency (#33).

[Unreleased]: https://github.com/eudoxys/eia/commits/main
