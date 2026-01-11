"""EIA Form Data Accessor

The `eia` package downloads and structures EIA form data for bulk power systems.

Syntax
------
    
    eia [-y YEAR] [-m MONTH] [--subset SUBSET] 
        [-o|--output OUTPUT] [--raw] [--refresh] 
        [-h|--help] [--warning] [--debug] 
        [-f|--format {csv,gzip,zip,xlsx}]
        {bulk_generation,customer_demand,distributed_generation,help}

Positional arguments
--------------------

- `bulk_generation`: EIA Form 860m bulk generation data

- `customer_demand`: EIA Form 861m customer consumption data

- `distributed_generation`: EIA Form 861m non-bulk generation data

- `help`: get online help

Optional arguments
------------------

-  `-h|--help`: show this help message and exit

-  `-o|--output OUTPUT`: set output file name

- `--raw`: access raw EIA form data

- `--refresh`: refresh local cache data

- `-y YEAR`, `--year YEAR`: select year

- `-m MONTH`, `--month MONTH`: select month

- `--subset SUBSET`: data subset requested

- `--warning`: enable warning message from python

- `--debug`: enable debug traceback on exceptions

- `-f|--format {csv,gzip,zip,xlsx}`: specify output format

Supported forms
---------------

Currently supported forms are

- `eia.form860m.Form860m`: Bulk power system generation fleet (1MW capacity cut-off)

- `eia.form861m.Form861m`: Distributed generation capacity and energy data (1MW capacity cut-off)

- `eia.hs861m.HS861m`: Customer energy consumption data (1MW capacity cut-off)

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

                            date state    res_mw    com_mw    ind_mw     tot_mw      res_mwh     com_mwh     ind_mwh      tot_mwh
    0  2020-08-01 00:00:00+00:00    AK     5.405     1.473     0.043      6.921      701.497     193.737       6.117      901.351
    1  2020-08-01 00:00:00+00:00    AL     0.000     0.000     0.611      0.000        0.000       0.000      99.501        0.000
    2  2020-08-01 00:00:00+00:00    AR    24.698    13.600    15.846     54.144     4164.484    2334.792    2719.254     9218.530
    .
    .
    .
    48 2020-08-01 00:00:00+00:00    WI    41.373    39.805    13.853     95.031     6365.008    6313.855    2171.008    14849.871
    49 2020-08-01 00:00:00+00:00    WV     6.987     3.127     0.058     10.172     1071.614     486.645       9.013     1567.273
    50 2020-08-01 00:00:00+00:00    WY     6.272     1.393     0.276      7.941     1080.503     248.006      49.268     1377.776

Python
------

Get the state-level distributed generation data for August 2020

    from eia import Form861m
    Form861m(year=2020,month=8)

Outputs

                            date state    res_mw    com_mw    ind_mw     tot_mw      res_mwh     com_mwh     ind_mwh      tot_mwh
    0  2020-08-01 00:00:00+00:00    AK     5.405     1.473     0.043      6.921      701.497     193.737       6.117      901.351
    1  2020-08-01 00:00:00+00:00    AL     0.000     0.000     0.611      0.000        0.000       0.000      99.501        0.000
    2  2020-08-01 00:00:00+00:00    AR    24.698    13.600    15.846     54.144     4164.484    2334.792    2719.254     9218.530
    .
    .
    .
    48 2020-08-01 00:00:00+00:00    WI    41.373    39.805    13.853     95.031     6365.008    6313.855    2171.008    14849.871
    49 2020-08-01 00:00:00+00:00    WV     6.987     3.127     0.058     10.172     1071.614     486.645       9.013     1567.273
    50 2020-08-01 00:00:00+00:00    WY     6.272     1.393     0.276      7.941     1080.503     248.006      49.268     1377.776

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
"""
from eia.cli import main
from eia.form860m import Form860m
from eia.form861m import Form861m
from eia.hs861m import HS861m
