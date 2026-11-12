# eia — design

This document records how the `eia` package is built and the conventions new
code should follow. It covers the state of `main` at `bf6c690` (2026-10-21) and
the decisions still open before the first release. Issue numbers (`#n`) refer
to the draft issues in `release-issues.md`.

Sections marked **Current** describe the code as it is. Sections marked
**Target** describe the convention proposed for the first release; they are
not yet implemented and need the maintainer's sign-off.

---

## 1. Purpose and scope

`eia` downloads public U.S. Energy Information Administration (EIA) electricity
data and returns it as tidy `pandas` data frames, with a local cache so that
repeated requests do not hit EIA servers.

In scope:

- Monthly and hourly electricity data published by EIA as Excel workbooks or
  through the EIA Open Data API v2.
- Light normalisation: consistent column names and units, UTC timestamps,
  dropping EIA status/footnote rows, numeric coercion.
- A command-line tool (`eia`) that writes the same frames to the terminal or
  to CSV/XLSX files.

Out of scope:

- Analysis, aggregation beyond what a form natively offers, or modelling.
- Plotting (the scripts in `examples/` may plot with matplotlib, which is
  not a dependency; see §11).
- Non-electricity EIA datasets.

## 2. Supported data sources

| Class | EIA source | Transport | Granularity | First period | Key |
|---|---|---|---|---|---|
| `Form860m` | Form 860M generator inventory | Excel workbook, one per month | generator | 2015-01 | none |
| `Form861m` | Form 861M small-scale solar | Excel workbook, one per year | state × month | 2017-01 | none |
| `Form861mSales` | Form 861M sales and revenue | Excel workbook, all years in one file | state × month | 2017-01 per docstring (code does not check) | none |
| `Form923` | Form 923 Schedules 2–5 net generation | ZIP of Excel workbooks, one per year | plant/prime mover/fuel × month, or state/BA/fuel × month | 2008-01 | none |
| `Form930` | Form 930 hourly demand, generation, interchange | API v2 `electricity/rto/region-data` | respondent × hour | 2015-07 | `EIA_API_KEY` |
| `Form930Fuel` | Form 930 hourly generation by energy source | API v2 `electricity/rto/fuel-type-data` | respondent × fuel × hour | 2018-07 | `EIA_API_KEY` |

Each EIA source has its own publication lag, file layout history, and URL
scheme (e.g. current-year vs `archive/` paths). Those quirks are contained in
the class for that source; nothing outside the class should depend on them.

## 3. Architecture

```
            ┌──────────────┐
  shell ──▶ │  eia.cli     │  argparse → kwargs → Form(**kwargs) → print / to_csv / to_excel
            └──────┬───────┘
                   │
  Python ──▶ ┌─────▼─────────────────────────────────────────────┐
             │ Form classes (pd.DataFrame subclasses)            │
             │  validate args → load (cache or download)         │
             │  → normalise → super().__init__(frame)            │
             └─────┬─────────────────────────────┬───────────────┘
                   │                             │
            ┌──────▼───────┐              ┌──────▼───────┐
            │ local cache  │              │ eia.gov      │
            │ (files)      │◀─── write ───│ xls/zip/API  │
            └──────────────┘              └──────────────┘
```

### 3.1 One class per source, subclassing `pandas.DataFrame`

**Current.** Each source is a `pd.DataFrame` subclass whose constructor does
all the work: argument checks, cache lookup, download, parsing, and
normalisation, then `super().__init__(data)`. Users write
`Form861m(2020, 8)` and get a frame.

Consequences to keep in mind:

- `FormBase` defines `_constructor` to return `pd.DataFrame` (and an empty
  `_metadata`), so every pandas operation (`.loc`, `.groupby`, arithmetic)
  returns a plain `DataFrame`. The subclass is a loader, not a type.
- The constructor has side effects (network, disk), which makes the classes
  harder to test and means a frame cannot be built from existing data without
  going through the loader.

**Decided (D2, GitHub #19): option (a).** Keep subclassing and define
`_constructor` explicitly, documenting that the subclass is a loader, not a
type. (Option (b), loader functions returning plain `DataFrame`s, was easier
to test but a larger change before release.)

### 3.2 Shared base class

**Current.** Only `Form930`/`Form930Fuel` share a base (`_Form930Base`).
`makeargs` is copy-pasted into `Form860m`, `Form861m` and `HS861m` and is
missing from the rest, which is why the `region_hourly` CLI subcommand fails
(#4). Download code is duplicated between `form860m.py` and `form861m.py` (#21).

**Target.** A private `eia._base` module with:

- `_FormBase(pd.DataFrame)` providing `makeargs`, `_constructor`, and the
  common `refresh`/`raw` handling.
- `_period(year, month, first=(YYYY, M))` — coerces `str → int`, validates
  range against the form's first published month, raises `ValueError` (#12).
  *Partly done (#14):* `eia.base.check_year()`/`check_month()` coerce and
  validate the year range and month; checking `(year, month)` against the
  first published month is still per form.
- `_download(url | list[url], *, timeout, retries)` — one HTTP helper with a
  configurable timeout, status check, fallback across URL candidates, and
  redaction of `api_key` from error text (#13, #14).
  *Done (#15):* `eia.base.download(url, params, *, missing_ok, timeout,
  retries)` is used by every form; URL fallback stays in the forms (they
  pass `missing_ok=True` and try the next candidate on `None`). Defaults
  come from `eia.set_download_options()` or `EIA_TIMEOUT`/`EIA_RETRIES`.
- `_cache(form, *parts, version)` — one constructor for cache paths (§4).

## 4. Caching

### 4.1 Current state

All forms use `cache.Cache` through `eia.base.cache_entry()`, rooted at
`eia.cache_dir()` (#13):

| Form | Mechanism | Location | Granularity | Invalidation |
|---|---|---|---|---|
| `Form860m` | `cache_entry(version=1)` | `{cache_dir}/eia/1/form860m/` | raw workbook per month + `.csv.gz` per subset | `refresh=True`; deletes workbook on `BadZipFile` |
| `Form861m` | `cache_entry(version=1)` + module dict | `{cache_dir}/eia/1/form861m/` | raw workbook per year; in-process dict per year | `refresh=True`; deletes workbook on *any* read error, including an unpublished month (#8) |
| `Form861mSales` | `cache_entry(version=0)` + module global | `{cache_dir}/eia/0/hs861m.csv` | one CSV for all years; in-process copy | `refresh=True` (but the in-process copy ignores it) |
| `Form923` | `cache_entry(version=1)` | `{cache_dir}/eia/1/form923/` | normalised `{year}.csv.gz` and raw worksheet `{year}-raw.csv.gz` per year | `refresh=True`; regenerated on read error |
| `Form930*` | `cache_entry(version=1)` | `{cache_dir}/eia/1/form930/` | raw API rows `.csv.gz` per respondent × month | `refresh=True`; regenerated on read error |
| Form 930 reference tables | `cache_entry(version=1)` + class dict | `{cache_dir}/eia/1/reference/` | raw reference workbook | `refresh=True` on any Form 930 class or `respondents()`/`reference_data()`; re-downloaded once per process when a respondent code is not found (#15) |

`cache_dir` is the folder set by `eia.set_cache_dir()`, else
`$EIA_CACHE_DIR`, else `platformdirs.user_cache_dir("eudoxys")`. `eia` uses a
`cache.Cache` subclass rooted there, so the `cache` package's own default
(inside its install directory) is neither used nor changed. There are no
per-class `CACHEDIR` attributes. `eia.clear_cache()` deletes
`{cache_dir}/eia`.

### 4.2 Target

- **One mechanism.** All forms use `cache.Cache(package="eia", version=N, ...)`.
- **Location.** Done (#13): platform user-cache directory, overridable with
  `EIA_CACHE_DIR` and `eia.set_cache_dir()`.
- **What is cached.** Cache the smallest *normalised* artefact that still
  serves every request option (as `Form923` already does), plus the raw file
  only when `raw=True` must reproduce EIA's original columns. Cached files are
  `.csv.gz`.
- **Schema version.** Bump the `version` argument whenever the cached layout
  or normalisation changes, so stale files are ignored rather than misread.
- **Failure handling.** Distinguish *unreadable file* (delete and re-download,
  with a warning naming the path) from *requested period absent* (raise
  `ValueError` without touching the cache).
- **Reference data** honours `refresh` and has a maximum age. *Partly done
  (#15):* honours `refresh` and refreshes itself when an unknown respondent
  code is requested; no maximum age.
- **In-process memoisation** is optional, keyed by the full argument tuple,
  and always bypassed by `refresh=True`.
- **User control.** Done (#13): `eia.cache_dir()` and `eia.clear_cache()`
  are documented in the README. (`cache clear --package eia` is not
  recommended: the `cache` CLI defaults to its own folder and passes the
  package name where `Cache.clear()` expects a list.)

## 5. Public API conventions

### 5.1 Inconsistencies before the first release (#17, GitHub #19, fixed)

| Aspect | 860m | 861m | HS861m | 923 | 930 / 930Fuel |
|---|---|---|---|---|---|
| First positional | `year` | `year` | `year` | `year` | `region` / `respondent` |
| `month=None` allowed | no | no | yes (undocumented) | yes | yes |
| `str` year/month | coerced | coerced | not coerced | not coerced | not coerced |
| Time label | none | `date` column | `date` index level | `timestamp` index level | `timestamp` column |
| Index | integer | integer | `date, state` | `timestamp, state, ba, fuel[, plant, pm]` | integer |
| Column style | `UPPER_SNAKE`, unit in some names | `res_mw` | `res_energy_mwh` | `gen_mwh` | `load_MW`, `NG_MW` |
| `raw` / `refresh` | both, positional | both, positional | both, positional | `refresh` keyword-only | `refresh` keyword-only |

### 5.2 Convention

**Current** (GitHub #19). Every form follows these rules; changing them now
breaks callers. `FormBase`'s docstring summarises them for the API reference.

1. **Signature.** `Form(year, month=None, *, <subject filters>, raw=False, refresh=False)`.
   `year` and `month` are the only positional arguments. Subject filters
   (`states`, `bas`, `fuels`, `plants`, `subset`, `respondent`) are
   keyword-only. Required subject arguments are keyword-only with no default,
   e.g. `Form930(2020, 8, respondent="CAL")`. `Form860m` requires `month`
   (an inventory is a monthly snapshot).
2. **Period handling.** `year` and `month` accept `int` or numeric `str`.
   `month=None` returns the whole year for every form that supports it.
   Out-of-range periods raise `ValueError`.
3. **Filters.** A filter accepts a single value or a list; `None` means "all".
4. **Time.** A tz-aware UTC `timestamp` marking the **beginning** of the
   period (month or hour). EIA's hour-ending API timestamps are shifted by −1 h
   (already done in `Form930`).
5. **Shape.** `timestamp` plus the natural keys form a `MultiIndex`; measured
   values are columns (decided D3). Keys: `Form860m` (`plant`, `generator`);
   `Form861m` and `Form861mSales` (`state`); `Form923` (`state`, `ba`, `fuel`)
   or (`state`, `ba`, `plant`, `pm`, `fuel`). Form 930 frames hold one
   respondent and are indexed by `timestamp` alone. Key names are shared
   across forms (`state`, `ba`, `plant`, `pm`, `fuel`) so frames can be
   joined.
6. **Column names.** `lower_snake_case` with a unit suffix:
   `_mw`, `_mwh`, `_kusd`, `_cpkwh`, `_qty`. Fuel/energy-source columns use
   EIA codes lower-cased, e.g. `ng_mw`, `wat_mw`.
7. **`raw=True`** returns EIA's original columns and values with only the
   period filter applied — no renaming, coercion, or dropped rows — and is
   supported by every form. Exceptions: `Form861m` and `Form861mSales` name
   the columns, because EIA's headers span several rows; `Form923` drops the
   monthly columns of other months when `month` is given.
8. **Inventory forms.** `Form860m` is a point-in-time inventory, not a time
   series; its `timestamp` is the report month. Its columns follow rule 6
   (`nameplate_mw`, `operating_year`, …).
9. **Naming.** Class names follow EIA form numbers (`Form860m`, `Form923`).
   `HS861m` was renamed `Form861mSales` (module `eia.form861msales`) before
   the first release (decided D6). `HS861m` (also importable from
   `eia.hs861m`) remains as a deprecated subclass that warns with
   `DeprecationWarning` and keeps the former interface (positional
   `refresh`, `raw`; `date` index level; `state`-only index for a single
   month). Remove it in a later release.

## 6. Command-line interface

**Current.** One flat `argparse` parser with a positional `form` choice that
maps to a class via `_FORMS`, and a shared option set filtered per class by
`makeargs`. Known defects: wrong class for `bulk_generation` (#3),
`region_hourly` unusable (#4), `customer_demand` type errors (#5), and the
output-path issues listed in #10. `Form923` and `Form930Fuel` are exposed as
`generation_monthly` and `region_fuel_hourly`, with their filters as shared
comma-separated options (#9).

**Target.**

- `argparse` sub-parsers, one per subcommand, so each exposes only the options
  its form accepts. Subcommand names describe the data, not the form number:

  | Subcommand | Class |
  |---|---|
  | `bulk_generation` | `Form860m` |
  | `distributed_generation` | `Form861m` |
  | `customer_demand` | `Form861mSales` |
  | `generation_monthly` | `Form923` |
  | `region_hourly` | `Form930` |
  | `region_fuel_hourly` | `Form930Fuel` |
  | `help` | prints package docstring |

- The CLI passes strings; coercion lives in the shared validation helper, not
  in the CLI.
- **Output.** No `--output` → print to stdout. `--format` wins over the file
  extension; otherwise infer from `.csv`, `.csv.gz`, `.csv.zip`, `.xlsx`; else
  error. XLSX sheet name is the form name.
- **Streams and exit codes.** Data on stdout; warnings and errors on stderr.
  Exit `0` success, `1` runtime failure, `2` usage error (`argparse` default).
- `main(argv: list[str] | None = None)` passes `argv` to `parse_args` and
  never mutates `sys.argv`.
- `--debug` re-raises; `--warning` restores Python's default warning display.

## 7. Errors and warnings

**Current.** Argument validation no longer uses `assert` (#14). All forms
coerce and validate arguments with the shared helpers in `eia.base`
(`check_year`, `check_month`, `check_bool`, `check_choice`), which raise
`TypeError` for a bad argument type and `ValueError` for a bad value or a
year before the form's first published year; `str` years and month numbers,
names or abbreviations are accepted by every form. Network failures surface
as `RuntimeError` from `eia.base.download()` (#15). Months that cannot have
been published yet (not yet ended for the monthly forms, in the future for
Form 930) raise `ValueError` "not published yet" before any download (#15);
months that have ended but EIA has not posted still fail at download time.

**Target.**

| Situation | Exception |
|---|---|
| Bad argument type | `TypeError` |
| Bad argument value, period before first published month | `ValueError` |
| Period not yet published by EIA | `ValueError` with "not yet published" in the message |
| Network/HTTP failure after retries | `RuntimeError` (chained from the `requests` error), URL with `api_key` redacted |
| Downloaded file unreadable | `RuntimeError` naming the cache path |
| Missing API key | `RuntimeError` naming `EIA_API_KEY`, `~/.eia/api_key`, and the registration URL |

Warnings (`warnings.warn`) are reserved for conditions where data is still
returned: preliminary data for recent years, deleting and replacing a corrupt
cache file.

## 8. Network access and credentials

- All HTTP goes through the shared download helper (§3.2): default timeout
  300 s for workbooks and API pages, limited retries with back-off, explicit
  status check. *Done (#15):* 3 retries on connection errors, timeouts,
  HTTP 429 and 5xx, with backoff starting at 1 s and doubling.
- API pagination uses `PAGE_LENGTH = 5000` and stops when `offset >= total`.
- The API key is read from `EIA_API_KEY`, then
  `os.path.expanduser("~/.eia/api_key")` (works on Windows; #14). It is
  never logged or included in exception text. *Done (#16):* a missing or
  empty key raises `RuntimeError` naming `EIA_API_KEY`, the key file path,
  and the registration URL; `download()` redacts `api_key` from every
  `requests` error, not only connection errors and timeouts.
- Constructing a form must not require network access when the requested data
  is already cached. *Done:* the Form 930 reference workbook is read from
  the disk cache; the network is used only when it is missing, `refresh`
  is set, or the respondent code is not in it (#15).

## 9. Dependencies

Runtime: `pandas`, `openpyxl`, `requests`, `cache`. *Done (#33):* the
unused `pytz` dependency is dropped. `platformdirs` is added only if §4.2 is adopted and
`cache` does not provide the user cache dir itself.

`cache` must be published to PyPI under a non-clashing name and pinned by
version before `eia` can be uploaded (#2).

## 10. Packaging and release

- **Distribution name.** `eia` is taken on PyPI (#1). Proposed:
  distribution `eudoxys-eia`. Open decision: keep import name `eia` (clashes
  with the existing `eia` package if both are installed) or move to a
  namespace (`eudoxys.eia`).
- **Metadata.** PEP 621 in `pyproject.toml`; PEP 639 `license = "MIT"`;
  dependencies listed statically rather than via `requirements.txt` (#20).
- **Version.** Single source in `pyproject.toml`; `eia.__version__` from
  `importlib.metadata`. Semantic versioning; `0.x` until §5.2 is stable.
- **Release.** Tag `vX.Y.Z` → CI builds sdist/wheel, runs `twine check`, and
  publishes with PyPI trusted publishing. `CHANGELOG.md` updated per release.

## 11. Testing and CI

**Target layout (#18, #19):**

- `pytest`, with tests under `tests/` named `test_*.py`.
- **Offline unit tests** (default): small fixture workbooks and recorded API
  JSON under `tests/data/`, served by mocking the download helper. Cover
  parsing, normalisation, column names/dtypes, period validation, cache
  behaviour, and every CLI subcommand and output format.
- **Live tests** marked `@pytest.mark.network`, run on a schedule (not on
  every push), with `EIA_API_KEY` from repository secrets. They detect EIA
  layout or URL changes.
- CI matrix: Python 3.11–3.13; `pylint --fail-under` set to the current
  score and raised over time.
- Usage examples live in `examples/`, not in `__main__` blocks of the
  package modules (some import matplotlib, which is not a dependency).
  *Done (#23).*

## 12. Documentation

- Module and class docstrings are the API reference, rendered with `pdoc`.
  Each form's class docstring lists every output column with units, the index,
  the first available period, and EIA caveats.
- `README.md` lists all supported forms and CLI subcommands with one example
  each; it must match `eia --help`.
- Generated HTML is built and published by CI (GitHub Pages) rather than
  committed under `docs/` (#18). `make docs` builds it locally into the
  git-ignored `docs/` folder; install `pdoc` first.

## 13. Adding a new form

1. Create `eia/formNNN.py` with a class that subclasses `_FormBase`.
2. Follow §5.2 for signature, timestamp, index, and column names; document
   every column with its unit.
3. Use the shared period, download, and cache helpers; choose a cache
   `version` and bump it on any layout change.
4. Support `raw=True` and `refresh=True`.
5. Add offline fixture tests and one `network`-marked live test.
6. Register a CLI subcommand and add it to the README and package docstring.
7. Export the class from `eia/__init__.py`.

## 14. Open decisions

| # | Decision | Options | Blocks |
|---|---|---|---|
| D1 | Distribution and import name | `eudoxys-eia` + `eia` · `eudoxys-eia` + `eudoxys.eia` | #1, release |
| D2 | Frame type | **decided:** DataFrame subclass with `_constructor` (GitHub #19) | — |
| D3 | Output shape | **decided:** `MultiIndex` on `timestamp` + keys (GitHub #19) | — |
| D4 | `cache` dependency | publish to PyPI · vendor into `eia` | #2, release |
| D5 | Default cache location | `platformdirs` user cache · change `cache` package default | #11 |
| D6 | `HS861m` name | **decided:** renamed `Form861mSales`, deprecated `HS861m` alias kept (GitHub #19) | — |
