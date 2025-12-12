"""EIA Form data accessor

Supported forms:

    - `861`: Distributed/small scale solar PV generation
"""

import os
import sys
import argparse
import warnings
import pandas as pd
import numpy as np
from eia.form861 import Form861

E_OK = 0
E_FAILED = 1
E_SYNTAX = 2

def main(*args,**kwargs):
    """EIA form accessor main command line processor

    Argument:

        - `*args`: command line arguments (none is sys.argv)

        - `**kwargs`: CLI options
    """
    try:

        if args:
            sys.argv = [__file__] + list(args)

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
        parser.add_argument("--states",
            help="select states")
        parser.add_argument("--years",
            help="select years")
        parser.add_argument("--warning",action="store_true")
        parser.add_argument("--debug",action="store_true")

        args = parser.parse_args()

        if not args.warning:
            warnings.showwarning = lambda *x:print(
                f"WARNING [{__package__}/{os.path.basename(x[2])}:{x[3]}]:",
                x[0],
                flush=True,
                file=sys.stderr,
                )

        if args.form == "help":
            print(__doc__)
            return E_OK

        data = globals()[f"Form{args.form}"](
            years=[int(x) for x in args.years.split(",")] if args.years else None,
            raw=args.raw,
            refresh=args.refresh,
            )\
            .reset_index()\
            .set_index(["date","state"])\
            .loc[(
                np.s_[args.years.split(",")] if args.years else np.s_[:],
                np.s_[args.states.split(",")] if args.states else np.s_[:],
                ),:]

        if args.output is None:

            pd.options.display.max_rows = None
            pd.options.display.width = None
            pd.options.display.max_columns = None
            print(data)
            return E_OK

        if args.output.endswith(".csv"):

            data.to_csv(args.output)
            return E_OK

        if args.output.endswith(".csv.gz"):

            data.to_csv(args.output,compression="gzip")
            return E_OK

        if args.output.endswith(".csv.zip"):

            data.to_csv(args.output,compression="zip")
            return E_OK

        if args.output.endswith(".xlsx"):

            data.to_excel(args.output,
                sheet_name="Form861",
                merge_cells=False)
            return E_OK

        raise ValueError(f"output format for '{args.output}' is invalid")

    except Exception as err:

        if args.debug:
            raise

        print(f"ERROR [eia]: {err}")
        return E_FAILED
