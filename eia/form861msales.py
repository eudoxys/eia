"""Form 861m retail sales data accessor

The `form861msales` module is used to access EIA Form 861 data archive of
monthly retail sales, revenue, customers, and price.

References
----------

  - https://www.eia.gov/electricity/data/eia861m/
"""

from io import BytesIO
import numpy as np
import pandas as pd
from eia.base import FormBase, cache_entry, check_year, check_month, check_bool, \
    check_published, download

_cache = None
"""@private In-process cache of the sales and revenue table"""

class Form861mSales(FormBase):
    """The `Form861mSales` class is a Pandas data frame loaded with the EIA
    Form 861 monthly retail sales, revenue, customers, and average price by
    state and sector, as published in the EIA `sales_revenue.xlsx` table.

    The data frame is indexed by

      - `timestamp`: the first day of the month (UTC)

      - `state`: the state for which the values are in effect

    and includes the following columns.

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

    Missing values are set to `0.0`.

    If the `raw` argument is `True`, the rows for the requested period are
    returned with a default integer index and the `year`, `month`, `state`,
    and `status` columns, without cleanup. (The column names are the
    flattened three-row EIA headers shown above, since the original headers
    span several rows.)
    """

    SOURCE = "https://www.eia.gov/electricity/data/eia861m/xls/sales_revenue.xlsx"
    """URL of the EIA Form 861m sales and revenue workbook"""

    INDEX = ["timestamp","state"]
    """Index levels of the data frame"""

    def __init__(
        self,
        year:int|str|None=None,
        month:int|str|None=None,
        *,
        raw:bool=False,
        refresh:bool=False,
        ):
        """Construct Form 861m retail sales data frame

        Arguments
        ---------

          - `year`: specifies the year (as `int` or `str`); `None` selects
            all years available (default `None`)

          - `month`: specifies the month (1 to 12, or a name or abbreviation
            such as `"Aug"`); `None` selects all months of the selected
            year(s) (default `None`)

          - `raw`: disable data frame cleanup, i.e., don't set `NaN` values
            to 0.0, construct the `timestamp` index, or remove the `year`,
            `month`, and `status` columns (default `False`); the `year` and
            `month` selection is applied

          - `refresh`: refresh data cache (default `False`)

        Raises
        ------

          - `TypeError`: an argument has the wrong type

          - `ValueError`: `year` or `month` is not valid, or no data is
            available for the selection

          - `RuntimeError`: the workbook cannot be downloaded
        """
        year = check_year(year,1990,optional=True)
        month = check_month(month,optional=True)
        if year is not None and month is not None:
            check_published(year,month)
        refresh = check_bool("refresh",refresh)
        raw = check_bool("raw",raw)

        global _cache # pylint: disable=global-statement
        if _cache is not None and not refresh:
            data = _cache.copy()
        else:
            data = self._load(refresh)
            _cache = data.copy()

        # select the requested period
        years = data["year"].astype(int)
        months = data["month"].astype(int)
        selected = np.ones(len(data),dtype=bool)
        if year is not None:
            selected &= years == year
        if month is not None:
            selected &= months == month
        data = data[selected]
        if len(data) == 0:
            raise ValueError(f"no data available for {year=}, {month=}")

        if not raw:
            data = data.assign(timestamp=pd.DatetimeIndex([f"{y}-{m:02d}-01 00:00:00+00:00"
                for y,m in zip(data["year"].astype(int),data["month"].astype(int))]))
            data = data.drop(["year","month","status"],axis=1).fillna(0.0)
            data = data.set_index(self.INDEX).sort_index()
        else:
            data = data.reset_index(drop=True)
        super().__init__(data)

    @classmethod
    def _load(cls,refresh:bool) -> pd.DataFrame:
        """@private Load the sales and revenue table from the cache or EIA"""
        cache = cache_entry("hs861m.csv",version=0)
        if cache.exists() and not refresh:
            return pd.read_csv(cache.pathname)
        content = download(cls.SOURCE).content
        data = pd.read_excel(BytesIO(content),header=[0,1,2]).round(2)
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
        data.columns = ["_".join([replace[y.lower()] for y in x if not y.startswith("Unnamed: ")])
            for x in data.columns]
        data = data.dropna(subset="status")
        data.to_csv(cache.pathname,index=False,header=True)
        return data


if __name__ == "__main__":

    pd.options.display.max_columns = None
    pd.options.display.width = None

    result = []
    for year in range(2018,2023):
        for month in range(12):
            result.append(Form861mSales(year,month+1))
    result = pd.concat(result)

    try:
        import matplotlib.pyplot as plt
        values = result.xs("CA",level="state")[[f"{x}_energy_mwh" for x in ["ind","res","com"]]]/1e6
        values.plot(kind="area",figsize=(20,10))
        plt.grid()
        plt.xlabel("Month")
        plt.ylabel("Energy (TWh)")
        plt.title("California Electricity Consumption")
        plt.show()
    except:
        print(result)
