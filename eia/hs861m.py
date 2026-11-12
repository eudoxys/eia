"""Form 861m customer data accessor

The `hs861m` module is used to access EIA Form 861 data archive of monthly
customer energy consumption.

References
----------

  - https://www.eia.gov/electricity/data/eia861m/
"""

import datetime as dt
import numpy as np
import pandas as pd
from cache import Cache
from eia.base import FormBase, month_number

refresh=False

_cache = None

class HS861m(FormBase):
    """Form 861m customer data frame"""

    CACHEDIR = None

    SOURCE = "https://www.eia.gov/electricity/data/eia861m/xls/sales_revenue.xlsx"
    """The `HS861m` class is a Pandas data frame loaded with the EIA Form 861
    customer consumption data for US states starting in 2017.

    The data frame includes the following columns.

      - `res_revenue_kusd`: residential revenue in thousands of US dollars

      - `res_energy_mwh`: residential energy sales in MWh

      - `res_customers_qty`: number of residential customers

      - `res_price_cpkwh`: average residential energy price in US cents per kWh

      - `com_revenue_kusd`: commercial revenue in thousands of US dollars

      - `com_energy_mwh`: commercial energy sales in MWh

      - `com_customers_qty`: number of commercial customers

      - `com_price_cpkwh`: average commercial energy price in US cents per kWh

      - `ind_revenue_kusd`: industrial revenue in thousands of US dollars

      - `ind_energy_mwh`: industrial energy sales in MWh

      - `ind_customers_qty`: number of industrial customers

      - `ind_price_cpkwh`: average industrial energy price in US cents per kWh

      - `tra_revenue_kusd`: transportation revenue in thousands of US dollars

      - `tra_energy_mwh`: transportation energy sales in MWh

      - `tra_customers_qty`: number of transportation customers

      - `tra_price_cpkwh`: average transportation energy price in US cents per kWh

      - `tot_revenue_kusd`: total revenue in thousands of US dollars

      - `tot_energy_mwh`: total energy sales in MWh

      - `tot_customers_qty`: number of total customers

      - `tot_price_cpkwh`: average total energy price in US cents per kWh
    """

    def __init__(
        self,
        year:int|str|None=None,
        month:int|str|None=None,
        refresh:bool=False,
        raw:bool=False,
        ):
        """Construct Form 861m customer historical data

        Arguments
        ---------

          - `year`: specifies the year (as `int` or `str`); `None` selects
            all years available (default `None`)

          - `month`: specifies the month (1 to 12, or a name or abbreviation
            such as `"Aug"`); `None` selects all months of the selected
            year(s) (default `None`)

            When both `year` and `month` are given the result is indexed by
            `state` only; otherwise it is indexed by `date` and `state`.

          - `refresh`: refresh data cache (default `False`)

          - `raw`: disable data frame cleanup, i.e., don't set `NaN` values
            to 0.0, construct the `date` index, or remove the `status`
            column (default `False`); `year` and `month` are validated but
            no selection is applied to raw data

        Raises
        ------

          - `ValueError`: `year` or `month` is not valid, or no data is
            available for the selection
        """
        if isinstance(year,str):
            try:
                year = int(year.strip())
            except ValueError as err:
                raise ValueError(f"{year=} is not a valid year") from err
        if year is not None:
            if not isinstance(year,int) or isinstance(year,bool) \
                    or not 1990 <= year <= dt.datetime.now().year:
                raise ValueError(f"{year=} is not a valid year")
        if month is not None:
            month = month_number(month)

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

            dates = data.index.get_level_values("date")
            selected = np.ones(len(data),dtype=bool)
            if year is not None:
                selected &= dates.year == year
            if month is not None:
                selected &= dates.month == month
            if year is not None or month is not None:
                data = data[selected]
                if len(data) == 0:
                    raise ValueError(f"no data available for {year=}, {month=}")
            if year is not None and month is not None:
                # a single month is indexed by state only
                data = data.droplevel("date")
            super().__init__(data)
        else:
            super().__init__(data)


if __name__ == "__main__":

    pd.options.display.max_columns = None
    pd.options.display.width = None

    result = []
    for year in range(2018,2023):
        for month in range(12):
            result.append(HS861m(year,month+1))
    result = pd.concat(result)

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
