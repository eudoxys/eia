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
- Plotting (the `__main__` demo blocks are examples only, see §11).
- Non-electricity EIA datasets.

## 2. Supported data sources

| Class | EIA source | Transport | Granularity | First period | Key |
|---|---|---|---|---|---|
| `Form860m` | Form 860M generator inventory | Excel workbook, one per month | generator | 2015-01 | none |
| `Form861m` | Form 861M small-scale solar | Excel workbook, one per year | state × month | 2017-01 | none |
| `HS861m` | Form 861M sales and revenue | Excel workbook, all years in one file | state × month | 2017-01 per docstring (code does not check) | none |
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

- No class defines `_constructor` or `_metadata`, so almost every pandas
  operation (`.loc`, `.groupby`, arithmetic) returns a plain `DataFrame`. The
  subclass type carries no guarantees after the first operation (#17).
- The constructor has side effects (network, disk), which makes the classes
  harder to test and means a frame cannot be built from existing data without
  going through the loader.

**Open decision (#17).** Either (a) keep subclassing and define
`_constructor = pd.DataFrame` explicitly, documenting that the subclass is a
loader, not a type; or (b) switch to loader functions/classmethods that return
plain `DataFrame`s (e.g. `eia.form861m.load(2020, 8)`), keeping the class
names as thin aliases for compatibility. Option (a) is the smaller change
before release; option (b) is easier to test. Whichever is chosen applies to
every form.

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
- `_download(url | list[url], *, timeout, retries)` — one HTTP helper with a
  configurable timeout, status check, fallback across URL candidates, and
  redaction of `api_key` from error text (#13, #14).
- `_cache(form, *parts, version)` — one constructor for cache paths (§4).

## 4. Caching

### 4.1 Current state

Two mechanisms coexist (#11):

| Form | Mechanism | Location | Granularity | Invalidation |
|---|---|---|---|---|
| `Form860m` | hand-rolled files | `{site-packages}/eia/.cache/` | raw workbook per month + `.csv.gz` per subset | `refresh=True`; deletes workbook on `BadZipFile` |
| `Form861m` | hand-rolled files + module dict | `{site-packages}/eia/.cache/` | raw workbook per year; in-process dict per month | `refresh=True`; deletes workbook on *any* read error, including an unpublished month (#8) |
| `HS861m` | `cache.Cache(version=0)` + module global | `cache` package dir | one CSV for all years; in-process copy | `refresh=True` (but the in-process copy ignores it) |
| `Form923` | `cache.Cache(version=1)` | `cache` package dir | normalised `.csv.gz` per year | `refresh=True`; regenerated on read error |
| `Form930*` | `cache.Cache(version=1)` | `cache` package dir | raw API rows `.csv.gz` per respondent × month | `refresh=True`; regenerated on read error |
| Form 930 reference tables | `cache.Cache(version=0)` + class dict | `cache` package dir | one CSV per sheet | never (ignores `refresh`) |

Note that `cache.Cache.CACHEDIR` itself defaults to
`os.path.dirname(cache.__file__)/.cache`, i.e. inside the `cache` package's
install directory. Moving `Form860m`/`Form861m` onto `cache` therefore does
not by itself fix the read-only `site-packages` problem; the default has to
change in `cache` or be overridden by `eia`.

### 4.2 Target

- **One mechanism.** All forms use `cache.Cache(package="eia", version=N, ...)`.
- **Location.** Default to the platform user-cache directory
  (`platformdirs.user_cache_dir("eia")` or equivalent), overridable with the
  `EIA_CACHE_DIR` environment variable and a single `eia.set_cache_dir()`
  call. No per-class `CACHEDIR` attributes.
- **What is cached.** Cache the smallest *normalised* artefact that still
  serves every request option (as `Form923` already does), plus the raw file
  only when `raw=True` must reproduce EIA's original columns. Cached files are
  `.csv.gz`.
- **Schema version.** Bump the `version` argument whenever the cached layout
  or normalisation changes, so stale files are ignored rather than misread.
- **Failure handling.** Distinguish *unreadable file* (delete and re-download,
  with a warning naming the path) from *requested period absent* (raise
  `ValueError` without touching the cache).
- **Reference data** honours `refresh` and has a maximum age.
- **In-process memoisation** is optional, keyed by the full argument tuple,
  and always bypassed by `refresh=True`.
- **User control.** Document `cache clear --package eia` and `cache size`
  in the README.

## 5. Public API conventions

### 5.1 Current inconsistencies (#17)

| Aspect | 860m | 861m | HS861m | 923 | 930 / 930Fuel |
|---|---|---|---|---|---|
| First positional | `year` | `year` | `year` | `year` | `region` / `respondent` |
| `month=None` allowed | no | no | yes (undocumented) | yes | yes |
| `str` year/month | coerced | coerced | not coerced | not coerced | not coerced |
| Time label | none | `date` column | `date` index level | `timestamp` index level | `timestamp` column |
| Index | integer | integer | `date, state` | `timestamp, state, ba, fuel[, plant, pm]` | integer |
| Column style | `UPPER_SNAKE`, unit in some names | `res_mw` | `res_energy_mwh` | `gen_mwh` | `load_MW`, `NG_MW` |
| `raw` / `refresh` | both, positional | both, positional | both, positional | `refresh` keyword-only | `refresh` keyword-only |

### 5.2 Target convention

These must be settled before the first release, because changing them later
breaks callers.

1. **Signature.** `Form(year, month=None, *, <subject filters>, raw=False, refresh=False)`.
   `year` and `month` are the only positional arguments. Subject filters
   (`states`, `bas`, `fuels`, `plants`, `subset`, `respondent`) are
   keyword-only. Required subject arguments are keyword-only with no default,
   e.g. `Form930(2020, 8, respondent="CAL")`.
2. **Period handling.** `year` and `month` accept `int` or numeric `str`.
   `month=None` returns the whole year for every form that supports it.
   Out-of-range periods raise `ValueError`.
3. **Filters.** A filter accepts a single value or a list; `None` means "all".
4. **Time.** A tz-aware UTC `timestamp` marking the **beginning** of the
   period (month or hour). EIA's hour-ending API timestamps are shifted by −1 h
   (already done in `Form930`).
5. **Shape.** `timestamp` plus the natural keys form a `MultiIndex`; measured
   values are columns. (Alternative: always return a flat frame with
   `timestamp` as a column. Pick one and apply it everywhere.)
6. **Column names.** `lower_snake_case` with a unit suffix:
   `_mw`, `_mwh`, `_kusd`, `_cpkwh`, `_qty`. Fuel/energy-source columns use
   EIA codes lower-cased, e.g. `ng_mw`, `wat_mw`.
7. **`raw=True`** returns EIA's original columns and values with only the
   period filter applied — no renaming, coercion, or dropped rows — and is
   supported by every form.
8. **Inventory forms.** `Form860m` is a point-in-time inventory, not a time
   series; its `timestamp` is the report month. Its columns follow rule 6
   (`nameplate_mw`, `operating_year`, …).
9. **Naming.** Class names follow EIA form numbers (`Form860m`, `Form923`).
   `HS861m` should become `Form861mSales` (or similar) to match, with the old
   name kept only if a release has already shipped it.

## 6. Command-line interface

**Current.** One flat `argparse` parser with a positional `form` choice that
maps to a class via `_FORMS`, and a shared option set filtered per class by
`makeargs`. Known defects: wrong class for `bulk_generation` (#3),
`region_hourly` unusable (#4), `customer_demand` type errors (#5), and the
output-path issues listed in #10. `Form923` and `Form930Fuel` have no
subcommand (#9).

**Target.**

- `argparse` sub-parsers, one per subcommand, so each exposes only the options
  its form accepts. Subcommand names describe the data, not the form number:

  | Subcommand | Class |
  |---|---|
  | `bulk_generation` | `Form860m` |
  | `distributed_generation` | `Form861m` |
  | `customer_demand` | `HS861m` |
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

**Current.** Validation uses `assert` (stripped by `python -O`); network
failures surface as `AssertionError`, `RuntimeError`, `KeyError` or
`UnboundLocalError` depending on the module (#6, #7, #12).

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
  status check.
- API pagination uses `PAGE_LENGTH = 5000` and stops when `offset >= total`.
- The API key is read from `EIA_API_KEY`, then
  `os.path.expanduser("~/.eia/api_key")` (works on Windows; #14). It is
  never logged or included in exception text.
- Constructing a form must not require network access when the requested data
  is already cached (currently violated by `Form930.respondents()`; #13).

## 9. Dependencies

Runtime: `pandas`, `openpyxl`, `requests`, `cache`. `pytz` is unused and
should be dropped (#21). `platformdirs` is added only if §4.2 is adopted and
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
- `__main__` demo blocks move to `examples/` (they import matplotlib, which
  is not a dependency).

## 12. Documentation

- Module and class docstrings are the API reference, rendered with `pdoc`.
  Each form's class docstring lists every output column with units, the index,
  the first available period, and EIA caveats.
- `README.md` lists all supported forms and CLI subcommands with one example
  each; it must match `eia --help`.
- Generated HTML is built and published by CI (GitHub Pages) rather than
  committed under `docs/` (#16).

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
| D2 | Frame type | DataFrame subclass with `_constructor` · loader functions | #17 |
| D3 | Output shape | `MultiIndex` on `timestamp` + keys · flat frame with `timestamp` column | #17 |
| D4 | `cache` dependency | publish to PyPI · vendor into `eia` | #2, release |
| D5 | Default cache location | `platformdirs` user cache · change `cache` package default | #11 |
| D6 | `HS861m` name | rename to match `FormNNN` pattern · keep | #17 |
