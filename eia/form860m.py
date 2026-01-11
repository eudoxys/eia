"""EIA Form 860m data accessor

The `Form860m` module accesses the EIA Form 860m data archive of monthly
electric generator inventory.

The `Form860m` class is a Pandas data frame.

See https://www.eia.gov/electricity/data/eia860m/ for details.
"""

import os
import datetime as dt
import warnings
import zipfile
import pandas as pd
import requests

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

class Form860m(pd.DataFrame):
    """The `Form860m` class is a Pandas data frame loaded with the EIA Form 860m
    monthly archive of electric generator inventory.

    The data frame includes the following columns.

      - `date`: the primary index indicate the date on which the new values go
        into effect.

      - `state`: the state for which the values are in effect.

    If the `raw` argument is `True`, the original EIA data is returned.
    """

    # pylint: disable=invalid-name
    CACHEDIR = None
    """Folder in which downloaded files are cached (default is `{package}/.cache`)"""

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
    """Table mapping EIA data columns to `eia.form860m.Format860M` data frame columns"""

    def __init__(self,
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        # pylint: disable=too-many-locals,too-many-branches
        year:int|str,
        month:int|str,
        subset:str=None,
        refresh:bool=None,
        raw:bool=None,
        ):
        """Construct EIA Forma 860m data frame

        Arguments
        ---------

          - `year`: specifies the year (2015 to present)

          - `month`: specifies the month (1 to 12)

          - `subset`: data subset requested

          - `refresh`: refresh data cache (default `False`)

          - `raw`: return raw data (default `False`)
        """

        # check arguments
        if isinstance(year,str):
            year = int(year)
        assert isinstance(year,int), "year must be an integer"
        assert 2015 <= year <= dt.datetime.now().year, f"{year=} is not valid"

        if isinstance(month,str):
            month = int(month)
        assert isinstance(month,int), "month must be an integer"
        assert 1 <= month <= 12, f"{month=} is not valid"

        if subset is None:
            subset = "Operating"
        assert subset in self.SUBSETS, f"{subset=} is not valid"

        if refresh is None:
            refresh=False
        assert isinstance(refresh,bool), "refresh must be Boolean"
        if raw is None:
            raw = False
        assert isinstance(raw,bool), "raw must be Boolean"

        # load data
        if self.CACHEDIR is None:
            self.CACHEDIR = os.path.join(os.path.dirname(__file__),".cache")
        os.makedirs(self.CACHEDIR,exist_ok=True)
        cachefile = os.path.join(self.CACHEDIR,f"form860_{year}_{month:02d}.xlsx")
        data = None # indicates no data yet
        try:
            if refresh or not os.path.exists(cachefile):

                # download data from EIA
                month_str = dt.date(year,month,1).strftime("%B").lower()
                url = "https://www.eia.gov/electricity/data/eia860m/"\
                    f"archive/xls/{month_str}_generator{year}.xlsx"
                req = requests.get(url,timeout=10)
                assert req.status_code == 200, \
                    f"'{url}' not available (HTTP error {req.status_code})"
                with open(cachefile,"wb") as fh:
                    fh.write(req.content)
                data = {} # indicates data is now cached but not loaded

            # read from cache
            subsetfile = f"{cachefile.replace('.xlsx',f'_{subset.lower()}.csv.gz')}"
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

            if isinstance(data,dict) and not data:
                warnings.warn(f"unable to read {cachefile} ({err})--"\
                    "deleting invalid cache file (try again later)")

            os.unlink(cachefile)
            data = None

        if data is None:
            raise RuntimeError(f"{url=} is not valid")

        if not raw:
            data.drop([x for x in data.columns if x not in self.COLUMNS],inplace=True,axis=1)
            data.rename({x:y[0] for x,y in self.COLUMNS.items()},inplace=True,axis=1)
            for value in self.COLUMNS.values():
                data[value[0]] = [value[1](x) for x in data[value[0]]] \
                    if value[0] in data.columns else value[1]("")

        super().__init__(data.sort_index())

    @classmethod
    def makeargs(cls,**kwargs):
        """@private Return dict of accepted kwargs by this class constructor"""
        return {x:y for x,y in kwargs.items()
            if x in cls.__init__.__annotations__}

if __name__ == '__main__':
    pd.options.display.width = None
    pd.options.display.max_columns = None
    pd.options.display.max_rows = None
    print(Form860m(2025,9,subset="Planned"))
