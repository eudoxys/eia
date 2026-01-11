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

    eia distribute_generation --year 2020 --month 8

Outputs

                        res_mw    com_mw    ind_mw     tot_mw      res_mwh     com_mwh     ind_mwh      tot_mwh
    date       state                                                                                           
    2020-08-01 AK        5.405     1.473     0.043      6.921      701.497     193.737       6.117      901.351
               AL        0.000     0.000     0.611      0.000        0.000       0.000      99.501        0.000
               AR       24.698    13.600    15.846     54.144     4164.484    2334.792    2719.254     9218.530
               AZ     1138.607   426.052     6.630   1571.289   186103.677   74192.920    1197.221   261493.818
               CA     6415.725  2253.064  1341.708  10010.497  1096187.879  411763.930  257364.943  1765316.752
    ...
               VT       81.463    48.205     1.387    131.055    11607.382    7360.232     208.949    19176.563
               WA      163.265    27.214     0.410    190.889    26775.955    4551.384      72.101    31399.440
               WI       41.373    39.805    13.853     95.031     6365.008    6313.855    2171.008    14849.871
               WV        6.987     3.127     0.058     10.172     1071.614     486.645       9.013     1567.273
               WY        6.272     1.393     0.276      7.941     1080.503     248.006      49.268     1377.776

Python
------

Get the state-level distributed generation data for August 2020

    from eia.form861m import Form861m
    print(Form861m(years=2020,month=8))

Outputs

                        res_mw    com_mw    ind_mw     tot_mw      res_mwh     com_mwh     ind_mwh      tot_mwh
    date       state                                                                                           
    2020-08-01 AK        5.405     1.473     0.043      6.921      701.497     193.737       6.117      901.351
               AL        0.000     0.000     0.611      0.000        0.000       0.000      99.501        0.000
               AR       24.698    13.600    15.846     54.144     4164.484    2334.792    2719.254     9218.530
               AZ     1138.607   426.052     6.630   1571.289   186103.677   74192.920    1197.221   261493.818
               CA     6415.725  2253.064  1341.708  10010.497  1096187.879  411763.930  257364.943  1765316.752
    ...
               VT       81.463    48.205     1.387    131.055    11607.382    7360.232     208.949    19176.563
               WA      163.265    27.214     0.410    190.889    26775.955    4551.384      72.101    31399.440
               WI       41.373    39.805    13.853     95.031     6365.008    6313.855    2171.008    14849.871
               WV        6.987     3.127     0.058     10.172     1071.614     486.645       9.013     1567.273
               WY        6.272     1.393     0.276      7.941     1080.503     248.006      49.268     1377.776

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


----
"""
from eia.cli import main
from eia.form860m import Form860m
from eia.form861m import Form861m
