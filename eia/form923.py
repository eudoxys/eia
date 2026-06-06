"""Access Form 923 generation data

Example
-------

The following code

    from eia import Form923
    print(Form923(2020,8,fuels=["NG","WAT"],bas="CISO"))
    
outputs

                                                   gen_mwh
    timestamp                 state ba   fuel             
    2020-08-01 00:00:00+00:00 CA    CISO NG    9013312.798
                                         WAT   1773947.542
                              NV    CISO NG     153002.000

See also
--------

- [EIA Form 923 Data Download](https://www.eia.gov/electricity/data/eia923/)
"""

import os
import datetime as dt
from io import BytesIO
from warnings import warn

import requests
import pandas as pd
from zipfile import ZipFile
import calendar

from cache import Cache

class Form923(pd.DataFrame):
    """Form923 DataFrame

    Index
    -----
    - `timestamp`: month and year of record
    - `state`: state to which record applies
    - `ba`: balancing authority to which record applies
    - `fuel`: fuel type to which record applies

    Columns
    -------
    - `gen_mwh`: total energy production of record in MWh
    """
    FORM923_URL = "https://www.eia.gov/electricity/data/eia923/archive/xls/f923_{year}.zip"

    def __init__(self,
        year:int,
        month:int|None=None,
        states:list[str]|None=None,
        bas:list[str]|None=None,
        fuels:list[str]|None=None,
        *,
        precision:int=3,
        refresh:bool=False,
        nonzero:bool=True,
        ):
        """Construct Form923 data frame

        Arguments
        ---------
        - `year`: year of query
        - `month`: month to include (`None` returns entire year)
        - `states`: states to include (`None` returns all states found)
        - `bas`: balancing authorities to include (`None` returns all BAs found)
        - `fuels`: fuel types to include (`None` returns all fuel types found)
        - `precision`: precision of cached data
        - `refresh`: force cache refresh
        - `nonzero`: only include non-zero results
        """

        # check year
        assert year>=2008 and year<=dt.datetime.now().year, f"{year=} is not valid"
        if year >= dt.datetime.now().year-1:
            warn(f"{year=} may not be finalized yet")

        # locate cache
        cache = Cache(
            package="eia",
            version=0,
            path=["form923",f"{year}.csv"],
            )
        if cache.exists() and not refresh:

            try:
                df = pd.read_csv(cache.pathname)
            except Exception as err:
                warn(f"{cache.pathname=} {err=} - regenerating cache")
                os.unlink(cache.pathname)
                df = None
        
        else:

            df = None

        # unable to find/use cache
        if df is None:

            # download from EIA
            url = self.FORM923_URL.format(year=year)
            req = requests.get(url)
            if req.status_code != 200:
                raise RuntimeError(f"{url=} --> HTTP Error {req.status_code}")

            # extract data
            with ZipFile(BytesIO(req.content),"r") as fh:
                months = {f"Netgen\n{calendar.month_name[x+1]}":f"{year}-{x+1:02d}" for x in range(12)}
                index_cols = {
                    "Plant State": "STATE",
                    "Balancing\nAuthority Code" : "BA",
                    "Reported\nFuel Type Code": "FUEL",
                    }
                df = pd.read_excel(fh.open(f"EIA923_Schedules_2_3_4_5_M_12_{year}_Final_Revision.xlsx"),
                    skiprows=5,
                    na_values=["."],
                    usecols= list(index_cols) + list(months),
                    ).rename(index_cols,axis=1).rename(months,axis=1).round(precision)

                # save data to cache
                df.to_csv(cache.pathname,index=False,header=True,compression="gzip" if cache.pathname.endswith(".gz") else None)

        # index groups
        df = df.groupby(["STATE","BA","FUEL"])

        # extract months
        if month:
            df = df[[f"{year}-{month:02d}"]].sum().stack().to_frame("gen_mwh")
        else:
            df = df.sum().stack().to_frame("gen_mwh")
        df.index.names = ["state","ba","fuel","month"]
        df.reset_index(inplace=True)

        # select non-zero values if specified
        if nonzero:
            df = df[df["gen_mwh"]>0].dropna()

        # select states
        if not states is None:
            if isinstance(states,str):
                states = [states]
            df = df.loc[df["state"].isin(states)]

        # select balancing authories
        if not bas is None:
            if isinstance(bas,str):
                bas = [bas]
            df = df.loc[df["ba"].isin(bas)]

        # select fuels
        if not fuels is None:
            if isinstance(fuels,str):
                fuels = [fuels]
            df = df.loc[df["fuel"].isin(fuels)]

        # make date/time index
        df["timestamp"] = pd.DatetimeIndex([f"{x}-01 00:00:00+0000" for x in df["month"]])

        # construct final data frame
        super().__init__(df.set_index(["timestamp","state","ba","fuel"])["gen_mwh"])



if __name__ == '__main__':
    
    pd.options.display.width = None
    pd.options.display.max_columns = None
    # pd.options.display.max_rows = None

    test = []
    for year in range(2018,2023):
        test.append(Form923(year,states="CA",fuels="NG",bas="CISO"))
    print(pd.concat(test))

