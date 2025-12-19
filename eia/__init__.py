"""EIA command line processor

The `eia` package downloads and structure EIA form data for bulk power systems.

Currently supported form:

- `eia.form860m.Form860m`: Bulk power system generation fleet (1MW capacity cut-off)

- `eia.form861m.Form861m`: Distributed generation capacity and energy data (1MW capacity cut-off)

# Usage

    eia [-h] [-o OUTPUT] [-y YEAR] [-m MONTH] FORM

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
