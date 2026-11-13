"""EIA Form 860m data accessor

The `Form860m` module accesses the EIA Form 860m data archive of monthly
electric generator inventory.

The `Form860m` class is a Pandas data frame.

References
----------

  - https://www.eia.gov/electricity/data/eia860m/
"""

import os
import datetime as dt
import warnings
import zipfile
import pandas as pd
from eia.base import FormBase, cache_entry, check_year, check_month, check_bool, check_choice, \
    check_published, download, month_start

def _int(s,default=0):
    try:
        return int(s)
    except ValueError:
        return default


def _float(s,default=float('nan')):
    try:
        return float(s)
    except ValueError:
        return default

class Form860m(FormBase):
    """The `Form860m` class is a Pandas data frame loaded with the EIA Form 860m
    monthly archive of electric generator inventory.

    Form 860m is a point-in-time inventory, not a time series. The data frame
    has one row per generator in the requested `subset` of the fleet as of
    the requested month, and is indexed by

      - `timestamp`: the report month (UTC, first day of the month)

      - `plant`: EIA plant id

      - `generator`: EIA generator id

    The columns are the values of `COLUMNS` (other than the index levels):

      - `owner`, `owner_name`: EIA entity (owner) id and name

      - `plant_name`: EIA plant name

      - `state`, `county`, `ba`: plant location and balancing authority code

      - `sector`, `unit`: sector and unit code

      - `nameplate_mw`, `summer_mw`, `winter_mw`, `dc_net_mw`: nameplate,
        net summer, net winter, and DC net capacity in MW

      - `nameplate_mwh`: nameplate energy capacity in MWh (storage)

      - `technology`, `fuel`, `pm`: technology, energy source code, and
        prime mover code

      - `operating_month`, `operating_year`: month and year the generator
        began operating

      - `planned_retirement_month`, `planned_retirement_year`: planned
        retirement month and year

      - `status`: generator status code

      - `planned_derate_year`, `planned_derate_month`, `planned_derate_summer_mw`,
        `planned_uprate_year`, `planned_uprate_month`, `planned_uprate_summer_mw`:
        planned changes to net summer capacity

      - `latitude`, `longitude`: plant latitude and longitude in degrees

    Columns absent from a month's workbook are filled with `0` (integers),
    `NaN` (floats), or `""` (strings); missing or non-numeric values in
    existing integer and float columns are set the same way.

    If the `raw` argument is `True`, the EIA worksheet is returned with a
    default integer index, its original column names, and all values as
    strings.
    """

    # pylint: disable=invalid-name
    CACHE_VERSION = 2
    """@private Cache schema version (see `eia.base.cache_entry()`)"""

    SUBSETS = {
        "Operating",
        "Planned",
        "Retired",
        "Canceled or Postponed",
        "Operating_PR",
        "Planned_PR",
        "Retired_PR",
        }
    """Available generation fleet subsets"""

    COLUMNS = {
        "Entity ID": ("owner",_int),
        "Entity Name": ("owner_name",str),
        "Plant ID": ("plant",_int),
        "Plant Name": ("plant_name",str),
        "Plant State": ("state",str),
        "County": ("county",str),
        "Balancing Authority Code": ("ba",str),
        "Sector": ("sector",str),
        "Generator ID": ("generator",str),
        "Unit Code": ("unit",str),
        "Nameplate Capacity (MW)": ("nameplate_mw",_float),
        "Net Summer Capacity (MW)": ("summer_mw",_float),
        "Net Winter Capacity (MW)": ("winter_mw",_float),
        "Technology": ("technology",str),
        "Energy Source Code": ("fuel",str),
        "Prime Mover Code": ("pm",str),
        "Operating Month": ("operating_month",_int),
        "Operating Year": ("operating_year",_int),
        "Planned Retirement Month": ("planned_retirement_month",_int),
        "Planned Retirement Year": ("planned_retirement_year",_int),
        "Status": ("status",str),
        "Nameplate Energy Capacity (MWh)": ("nameplate_mwh",_float),
        "DC Net Capacity (MW)": ("dc_net_mw",_float),
        "Planned Derate Year": ("planned_derate_year",_int),
        "Planned Derate Month": ("planned_derate_month",_int),
        "Planned Derate of Summer Capacity (MW)": ("planned_derate_summer_mw",_float),
        "Planned Uprate Year": ("planned_uprate_year",_int),
        "Planned Uprate Month": ("planned_uprate_month",_int),
        "Planned Uprate of Summer Capacity (MW)": ("planned_uprate_summer_mw",_float),
        "Latitude": ("latitude",_float),
        "Longitude": ("longitude",_float)
    }
    """Table mapping EIA data columns to `eia.form860m.Form860m` data frame columns"""

    INDEX = ["timestamp","plant","generator"]
    """Index levels of the data frame"""

    def __init__(self,
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        # pylint: disable=too-many-locals,too-many-branches
        year:int|str,
        month:int|str,
        *,
        subset:str|None=None,
        raw:bool=False,
        refresh:bool=False,
        ):
        """Construct EIA Form 860m data frame

        Arguments
        ---------

          - `year`: specifies the year (2015 to present)

          - `month`: specifies the month (1 to 12, or a name or abbreviation
            such as `"August"` or `"Aug"`)

          - `subset`: fleet subset, one of `SUBSETS` (default
            `"Operating"`)

          - `raw`: return the EIA worksheet unchanged (default `False`)

          - `refresh`: refresh data cache (default `False`)

        Raises
        ------

          - `TypeError`: an argument has the wrong type

          - `ValueError`: `year`, `month` or `subset` is not valid, or the
            month is not published yet

          - `RuntimeError`: the workbook cannot be downloaded or read
        """

        # check arguments
        year = check_year(year,2015)
        month = check_month(month)
        check_published(year,month)
        subset = check_choice("subset","Operating" if subset is None else subset,self.SUBSETS)
        refresh = check_bool("refresh",refresh)
        raw = check_bool("raw",raw)

        # load data
        cachefile = cache_entry("form860m",f"{year}-{month:02d}.xlsx",
            version=self.CACHE_VERSION).pathname
        subsetfile = cache_entry("form860m",f"{year}-{month:02d}-{subset.lower()}.csv.gz",
            version=self.CACHE_VERSION).pathname
        month_str = dt.date(year,month,1).strftime("%B").lower()
        url = "https://www.eia.gov/electricity/data/eia860m/"\
            f"archive/xls/{month_str}_generator{year}.xlsx"
        source = f"cached copy of {url}"
        try:
            if refresh or not os.path.exists(cachefile):

                # download data from EIA
                req = download(url)
                with open(cachefile,"wb") as fh:
                    fh.write(req.content)
                source = f"downloaded from {url}"

            # read from cache
            if refresh or not os.path.exists(subsetfile):
                # read all values as text so the subset cache keeps EIA's
                # original values (otherwise integer columns with blank
                # footnote rows are read as floats and cached as "10.0")
                data = pd.read_excel(cachefile,
                    skiprows=2 if year > 2020 or (year == 2020 and month > 10) else 1,
                    sheet_name=subset,
                    dtype=str,
                    keep_default_na=False,
                    na_values=[""],
                    engine="openpyxl").dropna(subset="Plant ID")

                # save subset cache data
                data.to_csv(subsetfile,
                    index=False,
                    header=True,
                    compression="gzip" if subsetfile.endswith(".gz") else None,
                    )
            # load subset cache data
            data = pd.read_csv(subsetfile,
                dtype=str if raw else None,
                na_filter=not raw,
                low_memory=False,
                )

        except zipfile.BadZipFile as err:

            warnings.warn(f"unable to read {cachefile} ({source}: {err})--"\
                "deleting invalid cache file")
            if os.path.exists(cachefile):
                os.unlink(cachefile)
            raise RuntimeError(f"{cachefile} ({source}) is not a valid "\
                "workbook and was deleted (try again later)") from err

        if not raw:
            data.drop([x for x in data.columns if x not in self.COLUMNS],inplace=True,axis=1)
            data.rename({x:y[0] for x,y in self.COLUMNS.items()},inplace=True,axis=1)
            for value in self.COLUMNS.values():
                data[value[0]] = [value[1](x) for x in data[value[0]]] \
                    if value[0] in data.columns else value[1]("")
            data.insert(0,"timestamp",month_start(year,month))
            data = data.set_index(self.INDEX).sort_index()

        super().__init__(data)
