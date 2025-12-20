"""EIA Form Data Accessor

The `eia` package downloads and structure EIA form data for bulk power systems.

# Usage
    
    eia [-y YEAR] [-m MONTH] [--subset SUBSET] 
        [-o|--output OUTPUT] [--raw] [--refresh] 
        [-h|--help] [--warning] [--debug] 
        [--format {csv,gzip,zip,xlsx}]
        {861m,860m,help}

# Positional arguments

- `860m`: EIA Form 860m

- `861m`: EIA Form 861m

- `help`: get online help

# Options

-  `-h`, `--help`: show this help message and exit

-  `-o OUTPUT`, `--output OUTPUT`: set output file name

- `--raw`: access raw EIA form data

- `--refresh`: refresh local cache data

- `-y YEAR`, `--year YEAR`: select year

- `-m MONTH`, `--month MONTH`: select month

- `--subset SUBSET`: data subset requested

- `--warning`: enable warning message from python

- `--debug`: enable debug traceback on exceptions

- `--format {csv,gzip,zip,xlsx}`: specify output format

# Supported forms

Currently supported forms are

- `eia.form860m.Form860m`: Bulk power system generation fleet (1MW capacity cut-off)

- `eia.form861m.Form861m`: Distributed generation capacity and energy data (1MW capacity cut-off)

# Installation

    python3 -m venv .venv
    . .venv/bin/activate
    pip install git+https://github.com/eudoxys/eia

# Example

Get the Form 860m generator data

    eia 860m -y 2020 -m 8

# Package information

- Source code: https://github.com/eudoxys/eia

- Documentation: https://www.eudoxys.com/eia

- Issues: https://github.com/eudoxys/eia/issues

- License: https://github.com/eudoxys/eia/blob/main/LICENSE

- Requirements: https://github.com/eudoxys/eia/blob/main/requirements.txt

----
"""
from eia.cli import main
from eia.form860m import Form860m
from eia.form861m import Form861m
