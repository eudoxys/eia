"""EIA command line processor

Usage:

    eia [-h] [-o OUTPUT] FORM

Exapmle:

    eia 861
"""
from eia.cli import main
from eia.form861 import Form861
