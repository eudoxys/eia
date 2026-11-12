"""EIA Form data accessor"""

import sys
import argparse
import warnings
import pandas as pd
# pylint: disable=unused-import
from eia import __doc__ as docs
from eia.form861m import Form861m
from eia.form860m import Form860m
from eia.form923 import Form923
from eia.form930 import Form930, Form930Fuel
from eia.form861msales import Form861mSales

E_OK = 0
"""Exit code on success"""

E_FAILED = 1
"""Exit code on failure"""

E_SYNTAX = 2
"""Exit code on syntax error"""

_EXTENSIONS = {
    ".csv": "csv",
    ".csv.gz": "gzip",
    ".csv.zip": "zip",
    ".xlsx": "xlsx",
}
"""Output formats inferred from output file name extensions"""

_FORMS = {
    "bulk_generation": Form860m,
    "customer_demand": Form861mSales,
    "distributed_generation": Form861m,
    "generation_monthly": Form923,
    "region_hourly": Form930,
    "region_fuel_hourly": Form930Fuel,
}

def output_format(output:str|None,fmt:str|None=None) -> str|None:
    """Get the output format for an output file name

    Arguments
    ---------

      - `output`: output file name (`None` for standard output)

      - `fmt`: output format from `--format` (`None` to infer from the
        `output` file name extension)

    Returns
    -------

      - `str|None`: output format (`csv`, `gzip`, `zip`, or `xlsx`), or
        `None` for the default table display on standard output

    Raises
    ------

      - `ValueError`: the format cannot be written to standard output, or
        cannot be inferred from the file name extension
    """
    if output is None:
        if fmt not in (None,"csv"):
            raise ValueError(f"output format '{fmt}' requires an output file name (--output)")
        return fmt
    if fmt is not None:
        return fmt
    for extension,result in _EXTENSIONS.items():
        if output.endswith(extension):
            return result
    raise ValueError(f"cannot infer output format from '{output}' "\
        f"(use --format or one of {', '.join(_EXTENSIONS)})")

def _naive_utc(data:pd.DataFrame) -> pd.DataFrame:
    """@private Convert tz-aware timestamps in the index and columns to naive UTC"""
    data = pd.DataFrame(data)
    names = [x for x in data.index.names if x is not None]
    if names:
        data = data.reset_index()
    for column in data.columns:
        if isinstance(data[column].dtype,pd.DatetimeTZDtype):
            data[column] = data[column].dt.tz_convert("UTC").dt.tz_localize(None)
    return data.set_index(names) if names else data

def main(*args:str) -> int:
    """EIA form accessor main command line processor

    Arguments
    ---------

      - `*args`: command line arguments (none uses `sys.argv`)

    Returns
    -------

      - `int`: return/exit code
    """
    # pylint: disable=too-many-return-statements
    options = None
    try:

        # setup command line parser
        parser = argparse.ArgumentParser(
            prog="eia",
            description="EIA form data accessor",
            epilog="See https://www.eudoxys.com/eia for documentation. "\
                "Use `eia help` to get a description of available forms."
            )
        parser.add_argument("form",
            choices=list(_FORMS) + ["help"])
        parser.add_argument("-o","--output",
            help="set output file name")
        parser.add_argument("--raw",
            action='store_true',
            help="access raw EIA form data")
        parser.add_argument("--refresh",
            action='store_true',
            help="refresh local cache data")
        parser.add_argument("-y","--year",
            help="select year")
        parser.add_argument("-m","--month",
            help="select month (number, name, or abbreviation)")
        parser.add_argument("-r","--respondent","--region",
            dest="respondent",
            help="select region or balancing authority (region_hourly, region_fuel_hourly)")
        parser.add_argument("--state","--states",
            dest="states",
            help="select states, comma separated (generation_monthly)")
        parser.add_argument("--ba","--bas",
            dest="bas",
            help="select balancing authorities, comma separated (generation_monthly)")
        parser.add_argument("--fuel","--fuels",
            dest="fuels",
            help="select fuel or energy source codes, comma separated "\
                "(generation_monthly, region_fuel_hourly)")
        parser.add_argument("--plant","--plants",
            dest="plants",
            help="select plant ids, comma separated (generation_monthly)")
        parser.add_argument("--by",
            choices=["ba","plant"],
            help="aggregate by balancing authority (default) or plant (generation_monthly)")
        parser.add_argument("--no-increments",
            dest="increments",
            action="store_false",
            help="exclude state-fuel level increment estimates, plant 99999 (generation_monthly)")
        parser.add_argument("--subset",
            help="data subset requested")
        parser.add_argument("--warning",
            action="store_true",
            help="enable warning message from python")
        parser.add_argument("--debug",
            action="store_true",
            help="enable debug traceback on exceptions")
        parser.add_argument("-f","--format",
            choices=["csv","gzip","zip","xlsx"],
            help="specify output format (default from --output extension)")

        # parse arguments (support direct call to main)
        options = parser.parse_args(list(args) if args else None)

        # setup warning handling
        if not options.warning:
            warnings.showwarning = lambda *x:print(
                f"WARNING [{__package__}]:",
                x[0],
                flush=True,
                file=sys.stderr,
                )

        # handle help request
        if options.form == "help":
            print(docs)
            return E_OK

        # check output format before accessing data
        fmt = output_format(options.output,options.format)

        # get data
        form = _FORMS[options.form]
        kwargs = {x:getattr(options,x) for x in dir(options) if x[0] != "_" }
        data = form(**form.makeargs(**kwargs))

        # handle default output
        if fmt is None:
            pd.options.display.max_rows = None
            pd.options.display.width = None
            pd.options.display.max_columns = None
            print(data)
            return E_OK

        # handle CSV output
        if fmt == "csv":
            data.to_csv(sys.stdout if options.output is None else options.output)
            return E_OK

        # handle GZIP and ZIP output
        if fmt in ("gzip","zip"):
            data.to_csv(options.output,compression=fmt)
            return E_OK

        # handle XLSX output (Excel does not support time zones, so UTC
        # timestamps are written without one)
        data = _naive_utc(data)
        data.to_excel(options.output,
            sheet_name=form.__name__,
            merge_cells=False)
        return E_OK

    # pylint: disable=broad-exception-caught
    except Exception as err:

        if getattr(options,"debug",False):
            raise

        print(f"ERROR [eia]: {err}",file=sys.stderr,flush=True)
        return E_FAILED
