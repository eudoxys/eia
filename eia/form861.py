"""EIA Form861 data accessor

The `Form861` module accesses the EIA Form 861 data archive of
distributed/small scale solar not included in the Form 860 or Form 923 data.

The `Form861` class is a Pandas data frame with both capacity (MW) and energy (MWh)
data for each year, month, and state in the US since 2017.
"""

import os
import sys
import datetime as dt
import pytz
import warnings
import pandas as pd
import requests

class Form861(pd.DataFrame):
    """The `Form861` class is a Pandas dataframe loaded with the EIA Form 861
    distributed/small scale solar data for US states starting in 2017.

    The data frame includes the following columns.

        - `date`: the primary index indicate the date on which the new values
          go into effect.

        - `state`: the state for which the values are in effect.

        - `res_mw`: the residential power capacity in megaWatts.

        - `com_mw`: the commercial power capacity in megaWatts.

        - `ind_mw`: the industrial power capacity in megaWatts.

        - `tot_mw`: the total power capacity in megaWatts.

        - `res_mwh`: the residential energy production in megaWatts hours.

        - `com_mwh`: the commercial energy production in megaWatts hours.

        - `ind_mwh`: the industrial energy production in megaWatts hours.

        - `tot_mwh`: the total energy production in megaWatts hours.
    """
    CACHEDIR = None

    def __init__(self,
        years:list[int]=None,
        refresh:bool=False,
        raw:bool=False):
        """Construct EIA Form 861 dataframe

        Arguments:

            - `years`: specify years to include (default 2017 to present)

            - `refresh`: refresh data cache (default `False`)

            - `raw`: disable dataframe cleanup, i.e., don't set `NaN` values
              to 0.0, construct the `date` index, or remove the `status`
              column (default `False`)
        """

        # download data from EIA
        if self.CACHEDIR is None:
            self.CACHEDIR = os.path.join(os.path.dirname(__file__),".cache")
        os.makedirs(self.CACHEDIR,exist_ok=True)
        thisyear = dt.datetime.now().year
        data = []
        for year in range(2017,thisyear+1) if years is None else years:
            filename = f"small_scale_solar_{year}.xlsx"
            httpfile = f"https://www.eia.gov/electricity/data/eia861m/archive/xls/{filename}"
            cachefile = os.path.join(self.CACHEDIR,filename)

            # read data from network if necessary
            if refresh or not os.path.exists(cachefile):
                req = requests.get(httpfile)
                assert req.status_code == 200, \
                    f"{httpfile} not available (HTTP error {req.status_code})"
                with open(cachefile,"wb") as fh:
                    fh.write(req.content)
            
            # load data from cache
            try:
                data.append(pd.read_excel(cachefile,
                    engine="openpyxl",
                    sheet_name="Monthly Totals- States",
                    skiprows=3,
                    names=["year","month","state","status",
                        "res_mw","com_mw","ind_mw","tot_mw",
                        "res_mwh","com_mwh","ind_mwh","tot_mwh",
                        ],
                    # na_values = ["NM","."],
                    dtype = {"state":str},
                    ).dropna(subset="status")
                )
            except Exception as err:
                warnings.warn(f"unable to read {filename} ({err})--"\
                    "deleting invalid cache file (try again later)")
                os.unlink(cachefile)

        # construct dataframe
        data = pd.concat(data)
        if not raw:
            data.fillna(0.0,inplace=True)
            data.index = pd.DatetimeIndex([dt.date(int(y),int(m),1) for y,m in zip(data.year,data.month)])
            data.index.name = "date"
            data.drop(["year","month","status"],axis=1,inplace=True)
            def tofloat(x):
                try:
                    return float(x)
                except ValueError:
                    return 0.0
            for column in [x for x in data.columns if x.endswith("_mw") or x.endswith("_mwh")]:
                data[column] = [tofloat(x) for x in data[column]]
            data.reset_index(inplace=True)
            data.set_index(["date","state"],inplace=True)
            data.sort_index(inplace=True)
        else:
            data.month = data.month.astype(int)
            data.year = data.year.astype(int)
        super().__init__(data)
