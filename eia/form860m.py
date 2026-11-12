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
    check_published, download

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

    The data frame has a default integer index and one row per generator in
    the requested `subset` of the fleet as of the requested month. The
    columns are the values of `COLUMNS`:

      - `OWNER_ID`, `OWNER_NAME`: EIA entity (owner) id and name

      - `ID`, `NAME`: EIA plant id and name

      - `STATE`, `COUNTY`, `BA_CODE`: plant location and balancing authority

      - `SECTOR`, `GENERATOR_ID`, `UNIT_CODE`: sector, generator id, and unit
        code

      - `NAMEPLATE_MW`, `SUMMER_MW`, `WINTER_MW`, `DC_NET_MW`: nameplate,
        net summer, net winter, and DC net capacity in MW

      - `NAMEPLATE_MWH`: nameplate energy capacity in MWh (storage)

      - `TECHNOLOGY`, `ENERGY_SOURCE_CODE`, `PRIME_MOVER_CODE`: technology,
        energy source, and prime mover

      - `OPERATING_MONTH`, `OPERATING_YEAR`: month and year the generator
        began operating

      - `PLANNED_RETIREMENT_MONTH`, `PLANNED_RETIREMENT_YEAR`: planned
        retirement month and year

      - `STATUS`: generator status code

      - `PLANNED_DERATE_YEAR`, `PLANNED_DERATE_MONTH`, `DERATE_SUMMER_MW`,
        `PLANNED_UPRATE_YEAR`, `PLANNED_UPRATE_MONTH`, `UPRATE_SUMMER_MW`:
        planned changes to net summer capacity

      - `LAT`, `LON`: plant latitude and longitude

    Columns absent from a month's workbook are filled with `0` (integers),
    `NaN` (floats), or `""` (strings); missing or non-numeric values in
    existing integer and float columns are set the same way.

    If the `raw` argument is `True`, the EIA worksheet is returned with its
    original column names and all values as strings.
    """

    # pylint: disable=invalid-name
    CACHE_VERSION = 1
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
        "Entity ID": ("OWNER_ID",_int),
        "Entity Name": ("OWNER_NAME",str),
        "Plant ID": ("ID",_int),
        "Plant Name": ("NAME",str),
        "Plant State": ("STATE",str),
        "County": ("COUNTY",str),
        "Balancing Authority Code": ("BA_CODE",str),
        "Sector": ("SECTOR",str),
        "Generator ID": ("GENERATOR_ID",str),
        "Unit Code": ("UNIT_CODE",str),
        "Nameplate Capacity (MW)": ("NAMEPLATE_MW",_float),
        "Net Summer Capacity (MW)": ("SUMMER_MW",_float),
        "Net Winter Capacity (MW)": ("WINTER_MW",_float),
        "Technology": ("TECHNOLOGY",str),
        "Energy Source Code": ("ENERGY_SOURCE_CODE",str),
        "Prime Mover Code": ("PRIME_MOVER_CODE",str),
        "Operating Month": ("OPERATING_MONTH",_int),
        "Operating Year": ("OPERATING_YEAR",_int),
        "Planned Retirement Month": ("PLANNED_RETIREMENT_MONTH",_int),
        "Planned Retirement Year": ("PLANNED_RETIREMENT_YEAR",_int),
        "Status": ("STATUS",str),
        "Nameplate Energy Capacity (MWh)": ("NAMEPLATE_MWH",_float),
        "DC Net Capacity (MW)": ("DC_NET_MW",_float),
        "Planned Derate Year": ("PLANNED_DERATE_YEAR",_int),
        "Planned Derate Month": ("PLANNED_DERATE_MONTH",_int),
        "Planned Derate of Summer Capacity (MW)": ("DERATE_SUMMER_MW",_float),
        "Planned Uprate Year": ("PLANNED_UPRATE_YEAR",_int),
        "Planned Uprate Month": ("PLANNED_UPRATE_MONTH",_int),
        "Planned Uprate of Summer Capacity (MW)": ("UPRATE_SUMMER_MW",_float),
        "Latitude": ("LAT",_float),
        "Longitude": ("LON",_float)
    }
    """Table mapping EIA data columns to `eia.form860m.Form860m` data frame columns"""

    def __init__(self,
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        # pylint: disable=too-many-locals,too-many-branches
        year:int|str,
        month:int|str,
        subset:str=None,
        refresh:bool=None,
        raw:bool=None,
        ):
        """Construct EIA Form 860m data frame

        Arguments
        ---------

          - `year`: specifies the year (2015 to present)

          - `month`: specifies the month (1 to 12, or a name or abbreviation
            such as `"August"` or `"Aug"`)

          - `subset`: data subset requested

          - `refresh`: refresh data cache (default `False`)

          - `raw`: return raw data (default `False`)

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
                data = pd.read_excel(cachefile,
                    skiprows=2 if year > 2020 or (year == 2020 and month > 10) else 1,
                    sheet_name=subset,
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

        super().__init__(data.sort_index())


if __name__ == '__main__':
    pd.options.display.width = None
    pd.options.display.max_columns = None
    pd.options.display.max_rows = None
    print(Form860m(2025,9,subset="Planned"))
