"""EIA command line processor

Usage:

    eia [-h] [-o OUTPUT] FORM

Exapmle:

    eia 861
"""
from eia.cli import main
from eia.form860m import Form860m
from eia.form861m import Form861m
