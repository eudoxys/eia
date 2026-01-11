"""EIA Form data accessor"""

import sys
import argparse
import warnings
import pandas as pd
# pylint: disable=unused-import
from eia.form861m import Form861m
from eia.form860m import Form860m

E_OK = 0
"""Exit code on success"""

E_FAILED = 1
"""Exit code on failure"""

E_SYNTAX = 2
"""Exit code on syntax error"""

def main(*args:list[str]) -> int:
    """EIA form accessor main command line processor

    Arguments
    ---------

      - `*args`: command line arguments (`None` is `sys.argv`)

    Returns
    -------

      - `int`: return/exit code
    """
    # pylint: disable=too-many-return-statements
    try:

        # support direct call to main
        if args:
            sys.argv = [__file__] + list(args)

        # setup command line parser
        parser = argparse.ArgumentParser(
            prog="eia",
            description="EIA form data accessor",
            epilog="See https://www.eudoxys.com/eia for documentation. "\
                "Use `eia help` to get a description of available forms."
            )
        parser.add_argument("form",
            choices=[x[4:] for x in globals() if x.startswith("Form")]+["help"])
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
            help="select month")
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
            help="specify output format")

        # parse arguments
        args = parser.parse_args()

        # setup warning handling
        if not args.warning:
            warnings.showwarning = lambda *x:print(
                f"WARNING [{__package__}]:",
                x[0],
                flush=True,
                file=sys.stderr,
                )

        # handle help request
        if args.form == "help":
            print(__doc__)
            return E_OK

        # get data
        form = globals()[f"Form{args.form}"]
        kwargs = {x:getattr(args,x) for x in dir(args) if x[0] != "_" }
        data = form(**form.makeargs(**kwargs))

        # handle default output
        if args.output is None:
            pd.options.display.max_rows = None
            pd.options.display.width = None
            pd.options.display.max_columns = None
            print(data)
            return E_OK

        # handle CSV output
        if args.output.endswith(".csv") or args.format == "csv":
            data.to_csv(args.output)
            return E_OK

        # handle GZIP output
        if args.output.endswith(".csv.gz") or args.format == "gzip":
            data.to_csv(args.output,compression="gzip")
            return E_OK

        # handle ZIP output
        if args.output.endswith(".csv.zip") or args.format == "zip":
            data.to_csv(args.output,compression="zip")
            return E_OK

        # handle XLSX output
        if args.output.endswith(".xlsx") or args.format == "xlsx":
            data.to_excel(args.output,
                sheet_name="Form861",
                merge_cells=False)
            return E_OK

        raise ValueError(f"output format '{args.format}' for '{args.output}' is invalid")

    # pylint: disable=broad-exception-caught
    except Exception as err:

        if getattr(args,"debug"):
            raise

        print(f"ERROR [eia]: {err}")
        return E_FAILED
