"""EIA Form Data Accessor

The `eia` package downloads and structures EIA form data for bulk power systems.

Syntax
------
    
    eia [-y YEAR] [-m MONTH] [-r|--region REGION] [--subset SUBSET]
        [--state STATES] [--ba BAS] [--fuel FUELS] [--plant PLANTS]
        [--by {ba,plant}] [--no-increments]
        [-o|--output OUTPUT] [--raw] [--refresh]
        [-h|--help] [--warning] [--debug]
        [-f|--format {csv,gzip,zip,xlsx}]
        {bulk_generation,customer_demand,distributed_generation,
         generation_monthly,region_hourly,region_fuel_hourly,help}

Positional arguments
--------------------

- `bulk_generation`: EIA Form 860m bulk generation data

- `customer_demand`: EIA Form 861m customer consumption data

- `distributed_generation`: EIA Form 861m non-bulk generation data

- `generation_monthly`: EIA Form 923 monthly net generation by balancing
  authority or by plant, prime mover, and fuel

- `region_hourly`: EIA Form 930 hourly load, net generation, and interchange
  by balancing authority or region (requires `--region`)

- `region_fuel_hourly`: EIA Form 930 hourly net generation by energy source
  by balancing authority or region (requires `--region`)

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

- `-r REGION`, `--region REGION`, `--respondent REGION`: select region or
  balancing authority (`region_hourly` and `region_fuel_hourly`; see
  `eia.Form930.respondents()`)

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

- `eia.form923.Form923`: Monthly net generation by balancing authority or by
  plant, prime mover, and fuel

- `eia.form930.Form930`: Hourly load, net generation, and interchange by
  balancing authority or region (UTC, hour-beginning)

- `eia.form930.Form930Fuel`: Hourly net generation by energy source by
  balancing authority or region (UTC, hour-beginning; July 2018 onward)

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

Get the hourly load, net generation, and interchange for California in August
2020 (Form 930)

    eia region_hourly --region CAL --year 2020 --month 8

Get the August 2020 net generation from natural gas and hydro in the CAISO
balancing authority (Form 923)

    eia generation_monthly --year 2020 --month 8 --ba CISO --fuel NG,WAT

Get the hourly net generation by energy source for the Bonneville Power
Administration in August 2020 (Form 930)

    eia region_fuel_hourly --region BPAT --year 2020 --month 8

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
2020 (Form 930; columns `timestamp`, `load_MW`, `generation_MW`,
`interchange_MW`)

    from eia import Form930
    Form930("CAL",2020,8)

Get the hourly net generation by energy source for the Bonneville Power
Administration in August 2020 (Form 930; one `{code}_MW` column per energy
source, e.g., `NG_MW`, `NUC_MW`, `WAT_MW`, `WND_MW`)

    from eia import Form930Fuel
    Form930Fuel("BPAT",2020,8)

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
    - [cache](https://github.com/eudoxys/cache)
"""
from eia.cli import main
from eia.form860m import Form860m
from eia.form861m import Form861m
from eia.form930 import Form930, Form930Fuel
from eia.form923 import Form923
from eia.hs861m import HS861m
