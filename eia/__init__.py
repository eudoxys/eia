# pylint: disable=line-too-long # docstring example output is wider than 100 columns
"""EIA Form Data Accessor

The `eia` package downloads and structures EIA form data for bulk power systems.

Syntax
------

    eia [-y YEAR] [-m MONTH] [-r|--respondent RESPONDENT] [--subset SUBSET]
        [--state STATES] [--ba BAS] [--fuel FUELS] [--plant PLANTS]
        [--by {ba,plant}] [--no-increments]
        [-o|--output OUTPUT] [--raw] [--refresh]
        [-h|--help] [--warning] [--debug]
        [-f|--format {csv,gzip,zip,xlsx}]
        {bulk_generation,customer_demand,distributed_generation,
         generation_monthly,region_hourly,region_fuel_hourly,help}

Positional arguments
--------------------

- `bulk_generation`: EIA Form 860m generator inventory

- `customer_demand`: EIA Form 861m retail sales, revenue, customers, and price

- `distributed_generation`: EIA Form 861m small-scale solar data

- `generation_monthly`: EIA Form 923 monthly net generation by balancing
  authority or by plant, prime mover, and fuel

- `region_hourly`: EIA Form 930 hourly load, net generation, and interchange
  by balancing authority or region (requires `--respondent`)

- `region_fuel_hourly`: EIA Form 930 hourly net generation by energy source
  by balancing authority or region (requires `--respondent`)

- `help`: get online help

Optional arguments
------------------

-  `-h|--help`: show this help message and exit

-  `-o|--output OUTPUT`: set output file name

- `--raw`: access raw EIA form data

- `--refresh`: refresh local cache data

- `-y YEAR`, `--year YEAR`: select year

- `-m MONTH`, `--month MONTH`: select month (number, name, or abbreviation,
  e.g., `8`, `August`, or `aug`)

- `-r RESPONDENT`, `--respondent RESPONDENT`, `--region RESPONDENT`: select
  region or balancing authority (`region_hourly` and `region_fuel_hourly`;
  see `eia.Form930.respondents()`)

- `--state STATES`, `--states STATES`: select states, comma separated
  (`generation_monthly`)

- `--ba BAS`, `--bas BAS`: select balancing authorities, comma separated
  (`generation_monthly`)

- `--fuel FUELS`, `--fuels FUELS`: select fuel or energy source codes, comma
  separated (`generation_monthly` and `region_fuel_hourly`)

- `--plant PLANTS`, `--plants PLANTS`: select EIA plant ids, comma separated
  (`generation_monthly`)

- `--by {ba,plant}`: aggregate by balancing authority (default) or by plant,
  prime mover, and fuel (`generation_monthly`)

- `--no-increments`: exclude EIA's state-fuel level increment estimates
  (plant `99999`) (`generation_monthly`)

- `--subset SUBSET`: fleet subset (`bulk_generation`; default `Operating`)

- `--warning`: enable warning message from python

- `--debug`: enable debug traceback on exceptions

- `-f|--format {csv,gzip,zip,xlsx}`: specify output format; takes precedence
  over the `--output` file name extension, which otherwise sets the format
  (`.csv`, `.csv.gz`, `.csv.zip`, or `.xlsx`); without `--output`, only `csv`
  is allowed and is written to standard output

Supported forms
---------------

Currently supported forms are

- `eia.form860m.Form860m`: Monthly inventory of generators of 1 MW or more

- `eia.form861m.Form861m`: Small-scale (under 1 MW) solar capacity and energy by state and sector

- `eia.form861msales.Form861mSales`: Monthly retail sales, revenue, customers, and price by state and sector
  (formerly `HS861m`, which is still available but deprecated)

- `eia.form923.Form923`: Monthly net generation by balancing authority or by
  plant, prime mover, and fuel

- `eia.form930.Form930`: Hourly load, net generation, and interchange by
  balancing authority or region (UTC, hour-beginning)

- `eia.form930.Form930Fuel`: Hourly net generation by energy source by
  balancing authority or region (UTC, hour-beginning; July 2018 onward)

Conventions
-----------

All forms follow the same conventions:

- `Form(year, month=None, *, <filters>, raw=False, refresh=False)`: `year`
  and `month` are the only positional arguments; filters and options are
  keyword-only. Form 930 requires `respondent=` (e.g.,
  `Form930(2020,8,respondent="CAL")`). `Form860m` requires `month`.

- `year` and `month` accept an `int` or a numeric `str`; `month` also accepts
  a name or abbreviation. `month=None` selects the whole year.

- Filters (`states`, `bas`, `fuels`, `plants`) accept one value or a list;
  `None` selects all.

- The index starts with `timestamp`, the tz-aware UTC beginning of the month
  or hour, followed by the natural keys of a row (e.g., `state`, `ba`,
  `fuel`). Measured values are columns.

- Column names are lower case with a unit suffix on measured values: `_mw`,
  `_mwh`, `_kusd` (thousand US dollars), `_cpkwh` (US cents per kWh), `_qty`
  (count).

- `raw=True` returns the EIA data for the requested period with a default
  integer index and no renaming, coercion, or filtering.

- Pandas operations on a form return plain `pandas.DataFrame` objects.

Form 930 data are obtained from the EIA Open Data API, which requires an API
key. Register at https://www.eia.gov/opendata/register.php, then store the key
in the environment variable `EIA_API_KEY` or in the file `~/.eia/api_key`.

Installation
------------

    python3 -m venv .venv
    . .venv/bin/activate
    pip install git+https://github.com/eudoxys/eia

Examples
--------

Shell
-----

Get the state-level distributed generation data for August 2020

    eia distributed_generation --year 2020 --month 8

Outputs

                                 res_mw  com_mw  ind_mw  tot_mw   res_mwh   com_mwh  ind_mwh   tot_mwh
    timestamp                 state
    2020-08-01 00:00:00+00:00 AK      5.405   1.473   0.043   6.921   701.497   193.737    6.117   901.351
                              AL      0.000   0.000   0.611   0.000     0.000     0.000   99.501     0.000
                              AR     24.698  13.600  15.846  54.144  4164.484  2334.792 2719.254  9218.530
    ...

Get the hourly load, net generation, and interchange for California in August
2020 (Form 930)

    eia region_hourly --respondent CAL --year 2020 --month 8

Get the August 2020 net generation from natural gas and hydro in the CAISO
balancing authority (Form 923)

    eia generation_monthly --year 2020 --month 8 --ba CISO --fuel NG,WAT

Get the hourly net generation by energy source for the Bonneville Power
Administration in August 2020 (Form 930)

    eia region_fuel_hourly --respondent BPAT --year 2020 --month 8

Python
------

Get the state-level distributed generation data for August 2020

    from eia import Form861m
    Form861m(2020,8)

Outputs

                                 res_mw  com_mw  ind_mw  tot_mw   res_mwh   com_mwh  ind_mwh   tot_mwh
    timestamp                 state
    2020-08-01 00:00:00+00:00 AK      5.405   1.473   0.043   6.921   701.497   193.737    6.117   901.351
                              AL      0.000   0.000   0.611   0.000     0.000     0.000   99.501     0.000
                              AR     24.698  13.600  15.846  54.144  4164.484  2334.792 2719.254  9218.530
    ...

Get the August 2020 net generation from natural gas and hydro in the CAISO
balancing authority (Form 923)

    from eia import Form923
    Form923(2020,8,fuels=["NG","WAT"],bas="CISO")

Outputs

                                                   gen_mwh
    timestamp                 state ba   fuel
    2020-08-01 00:00:00+00:00 CA    CISO NG    9013312.798
                                         WAT   1773947.542
                              NV    CISO NG     153002.000

Get the same data by plant and prime mover for hydro plants in California
(Form 923)

    from eia import Form923
    Form923(2020,8,states="CA",fuels="WAT",by="plant")

Get the hourly load, net generation, and interchange for California in August
2020 (Form 930; indexed by `timestamp`, columns `load_mw`, `generation_mw`,
`interchange_mw`)

    from eia import Form930
    Form930(2020,8,respondent="CAL")

Get the hourly net generation by energy source for the Bonneville Power
Administration in August 2020 (Form 930; one `{code}_mw` column per energy
source, e.g., `ng_mw`, `nuc_mw`, `wat_mw`, `wnd_mw`)

    from eia import Form930Fuel
    Form930Fuel(2020,8,respondent="BPAT")

Caching
-------

Downloaded data are cached so that repeated requests do not access EIA
again. Pass `refresh=True` (or `--refresh` on the command line) to download
again, e.g., after EIA revises recent months.

Cache files are stored under `{cache_dir}/eia/{version}/`, never inside the
installed package. The cache folder is, in order of precedence, the folder
given to `eia.set_cache_dir()`, the environment variable `EIA_CACHE_DIR`, or
the platform user cache folder (`~/.cache/eudoxys` on Linux,
`~/Library/Caches/eudoxys` on macOS, `%LOCALAPPDATA%\\eudoxys\\Cache` on
Windows). Use `eia.cache_dir()` to find it and `eia.clear_cache()` to delete
all cached `eia` data, e.g.,

    import eia
    print(eia.cache_dir())
    eia.set_cache_dir("/data/eia-cache")
    eia.clear_cache()

or on the command line

    EIA_CACHE_DIR=/data/eia-cache eia generation_monthly -y 2020 -m 8

Network access
--------------

Downloads time out after 300 seconds and transient failures (connection
errors, timeouts, HTTP 429 and 5xx) are retried 3 times with exponential
backoff. Use `eia.set_download_options()` or the environment variables
`EIA_TIMEOUT` and `EIA_RETRIES` to change this, e.g.,

    import eia
    eia.set_download_options(timeout=60,retries=5)

Months that cannot have been published yet (e.g., the current month for the
monthly forms, or a future month for Form 930) are rejected with a
`ValueError` before any download is attempted.

Package information
-------------------

- Source code: https://github.com/eudoxys/eia

- Documentation: https://www.eudoxys.com/eia

- Issues: https://github.com/eudoxys/eia/issues

- License: https://github.com/eudoxys/eia/blob/main/LICENSE

- Dependencies:

    - [pandas](https://pypi.org/project/pandas/)
    - [openpyxl](https://pypi.org/project/openpyxl/)
    - [requests](https://pypi.org/project/requests/)
    - [platformdirs](https://pypi.org/project/platformdirs/)
    - [cache](https://github.com/eudoxys/cache)
"""
from importlib.metadata import version as _version, PackageNotFoundError as _PackageNotFoundError

try:
    __version__ = _version("eia")
    """Installed package version (from the package metadata)"""
except _PackageNotFoundError: # running from a source tree that is not installed
    __version__ = "0.0.0"

from eia.cli import main
from eia.form860m import Form860m
from eia.form861m import Form861m
from eia.form930 import Form930, Form930Fuel
from eia.form923 import Form923
from eia.form861msales import Form861mSales, HS861m
from eia.base import cache_dir, set_cache_dir, clear_cache, download_options, set_download_options
