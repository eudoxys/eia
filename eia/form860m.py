"""EIA Form 860m data accessor

The `Form860m` module accesses the EIA Form 860m data archive of monthly
electric generator inventory.

The `Form860m` class is a Pandas data frame.

See https://www.eia.gov/electricity/data/eia860m/ for details.
"""

import os
import sys
import datetime as dt
import pytz
import warnings
import pandas as pd
import requests
import zipfile

class Form860m(pd.DataFrame):
    """The `Form860m class is a Pandas data frame loaded with the EIA Form 860m
    monthly archive of electric generator inventory.

    For details see https://www.eia.gov/electricity/data/eia860m/.
    """

    CACHEDIR = None
    SUBSETS = ["Operating","Planned","Retired","Canceled or Postponed","Operating_PR","Planned_PR","Retired_PR"]

    def __init__(self,
        year:int|str,
        month:int|str,
        refresh:bool=None,
        subset:str=None,
        ):
        """Construct EIA Forma 860m data frame

        Arguments:

            - `year`: specifies the year (2015 to present)

            - `month`: specifies the month (1 to 12)

            - `refresh`: refresh data cache (default `False`)

            - `subset`: data subset requested
        """

        # check arguments
        assert isinstance(year,(int,str)), f"year must be an integer or a string"
        if isinstance(year,str):
            year = int(year)
        assert isinstance(month,(int,str)), f"month must be an integer or a string"
        if isinstance(month,str):
            month = int(month)
        if refresh is None:
            refresh=False
        assert isinstance(refresh,bool), f"refresh must be Boolean"
        if subset is None:
            subset = "Operating"
            assert subset in self.SUBSETS, f"{subset=} is not valid"

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
                file = f"{month_str}_generator{year}.xlsx"
                url = f"https://www.eia.gov/electricity/data/eia860m/archive/xls/{month_str}_generator{year}.xlsx"
                req = requests.get(url)
                assert req.status_code == 200, \
                    f"'{url}' not available (HTTP error {req.status_code})"
                with open(cachefile,"wb") as fh:
                    fh.write(req.content)
                data = {} # indicates data is now cached but not loaded

            # read from cache
            subsetfile = f"{cachefile.replace('.xlsx',f'_{subset.lower()}.csv.gz')}"
            if refresh or not os.path.exists(subsetfile):
                data = pd.read_excel(cachefile,
                    skiprows=2,
                    sheet_name=subset,
                    engine="openpyxl").dropna(subset="Plant ID")

                # save subset cache data
                data.to_csv(subsetfile,
                    index=False,
                    header=True,
                    compression="gzip" if subsetfile.endswith(".gz") else None,
                    )
            else:

                # load subset cache data
                data = pd.read_csv(subsetfile)

        except zipfile.BadZipFile as err:

            if isinstance(data,dict) and data == {}:
                warnings.warn(f"unable to read {cachefile} ({err})--"\
                    "deleting invalid cache file (try again later)")

            os.unlink(cachefile)
            data = None
        
        if data is None:
            raise RuntimeError(f"{url=} is not valid")

        super().__init__(data)

    @classmethod
    def makeargs(cls,**kwargs):
        return {x:y for x,y in kwargs.items() if x in cls.__init__.__annotations__}

if __name__ == '__main__':
    print(Form860m(2025,9))
