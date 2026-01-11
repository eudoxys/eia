"""Form 861m customer data accessor"""

import pandas as pd
from cache import Cache

refresh=False

_cache = None

class HS861m(pd.DataFrame):
    """Form 861m customer data frame"""

    CACHEDIR = None

    SOURCE = "https://www.eia.gov/electricity/data/eia861m/xls/sales_revenue.xlsx"
    """EIA data source"""

    def __init__(
        self,
        year:int,
        month:int,
        refresh:bool=False,
        raw:bool=False,
        ):
        """Construct Form 861m customer historical data

        Arguments
        ---------

          - `year`: specifies the year (2017 to present)

          - `month`: specifies the month (1 to 12)

          - `refresh`: refresh data cache (default `False`)

          - `raw`: disable data frame cleanup, i.e., don't set `NaN` values
            to 0.0, construct the `date` index, or remove the `status`
            column (default `False`)
        """  

        global _cache
        if not _cache is None:
            data = _cache.copy()
        else:    
            if self.CACHEDIR:
                cache.CACHEDIR = self.CACHEDIR      
            cache = Cache(package="eia",version=0,path=["hs861m.csv"])
            if cache.exists() and not refresh:
                data = pd.read_csv(cache.pathname)
            else:
                data = pd.read_excel(self.SOURCE,header=[0,1,2]).round(2)
                replace = {
                    "year":"year",
                    "month":"month",
                    "state":"state",
                    "data status":"status",
                    "residential":"res",
                    "commercial":"com",
                    "industrial":"ind",
                    "transportation":"tra",
                    "total":"tot",
                    "revenue":"revenue",
                    "sales":"energy",
                    "price":"price",
                    "customers":"customers",
                    "thousand dollars":"kusd",
                    "count":"qty",
                    "megawatthours":"mwh",
                    "cents/kwh":"cpkwh",
                }                
                data.columns = ["_".join([replace[y.lower()] for y in x if not y.startswith("Unnamed: ")]) for x in data.columns]
                data.dropna(subset="status",inplace=True)
                data.to_csv(cache.pathname,index=False,header=True)
            _cache = data.copy()

        if not raw:
            data.year = data.year.astype(int)
            data.month = data.month.astype(int)
            data["date"] = pd.DatetimeIndex([f"{y}-{m:02d}-01 00:00:00+00:00"
                for y,m in zip(data.year,data.month)],tz=0)
            data.set_index(["date","state"],inplace=True)
            data.drop(["year","month","status"],inplace=True,axis=1)
            data.fillna(0.0,inplace=True)
            data.sort_index(inplace=True)

        super().__init__(data.loc[f"{year}-{month}"])

    @classmethod
    def makeargs(cls,**kwargs):
        """@private Return dict of accepted kwargs by this class constructor"""
        return {x:y for x,y in kwargs.items() if x in cls.__init__.__annotations__}

if __name__ == "__main__":

    pd.options.display.max_columns = None
    pd.options.display.width = None

    result = []
    for year in range(2018,2023):
        for month in range(12):
            result.append(HS861m(year,month+1))
    result = pd.concat(result).reset_index().set_index(["state","date"])

    try:
        import matplotlib.pyplot as plt
        values = result.loc["CA"][[f"{x}_energy_mwh" for x in ["ind","res","com"]]]/1e6
        values.plot(kind="area",figsize=(20,10))
        plt.grid()
        plt.xlabel("Month")
        plt.ylabel("Energy (TWh)")
        plt.title("California Electricity Consumption")
        plt.show()
    except:
        print(result)