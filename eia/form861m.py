"""EIA Form 861 data accessor

The `Form861m` module accesses the EIA Form 861 data archive of
distributed/small scale solar not included in the Form 860 or Form 923 data.

The `Form861m` class is a Pandas data frame with both capacity (MW) and energy (MWh)
data for each year, month, and state in the US since 2017.

References
----------

  - https://www.eia.gov/electricity/data/eia861m/
"""

import os
import warnings
import pandas as pd
from eia.base import FormBase, cache_entry, check_year, check_month, check_bool, \
    check_published, download, month_start

_cache = {}
"""@private In-process cache of workbooks by year"""

class Form861m(FormBase):
    """The `Form861m` class is a Pandas data frame loaded with the EIA Form 861
    distributed/small scale solar data for US states starting in 2017.

    The data frame is indexed by

      - `timestamp`: the first day of the month (UTC)

      - `state`: the state for which the values are in effect

    and has the following columns.

      - `res_mw`: the residential power capacity in megaWatts.

      - `com_mw`: the commercial power capacity in megaWatts.

      - `ind_mw`: the industrial power capacity in megaWatts.

      - `tot_mw`: the total power capacity in megaWatts.

      - `res_mwh`: the residential energy production in megaWatts hours.

      - `com_mwh`: the commercial energy production in megaWatts hours.

      - `ind_mwh`: the industrial energy production in megaWatts hours.

      - `tot_mwh`: the total energy production in megaWatts hours.

    Missing and non-numeric values are set to `0.0`.

    If the `raw` argument is `True`, the EIA rows for the requested period are
    returned with a default integer index and the columns `year`, `month`,
    `state`, `status`, and the capacity and energy columns above, without
    cleanup.
    """

    # pylint: disable=invalid-name
    CACHE_VERSION = 1
    """@private Cache schema version (see `eia.base.cache_entry()`)"""

    FORM861M_URLS = [
        "https://www.eia.gov/electricity/data/eia861m/archive/xls/small_scale_solar_{year}.xlsx",
        "https://www.eia.gov/electricity/data/eia861m/xls/small_scale_solar_{year}.xlsx",
        ]
    """URLs to try for Form 861m workbooks (archived years, then recent years)"""

    INDEX = ["timestamp","state"]
    """Index levels of the data frame"""

    def __init__(self,
        year:int|str,
        month:int|str|None=None,
        *,
        raw:bool=False,
        refresh:bool=False,
        ):
        """Construct EIA Form 861 data frame

        Arguments
        ---------

          - `year`: specifies the year (2017 to present)

          - `month`: specifies the month (1 to 12, or a name or abbreviation
            such as `"August"` or `"Aug"`); `None` selects every month of
            `year` that EIA has published (default `None`)

          - `raw`: disable data frame cleanup, i.e., don't set `NaN` values
            to 0.0, construct the `timestamp` index, or remove the `year`,
            `month`, and `status` columns (default `False`)

          - `refresh`: refresh data cache (default `False`)

        Raises
        ------

          - `TypeError`: an argument has the wrong type

          - `ValueError`: `year` or `month` is not valid, or the period is
            not published

          - `RuntimeError`: the workbook cannot be downloaded or read
        """

        year = check_year(year,2017)
        month = check_month(month,optional=True)
        if month is not None:
            check_published(year,month)
        refresh = check_bool("refresh",refresh)
        raw = check_bool("raw",raw)

        cachefile = cache_entry("form861m",f"{year}.xlsx",version=self.CACHE_VERSION).pathname
        if year not in _cache or refresh:
            _cache[year] = self._load(year,cachefile,refresh)
        workbook = _cache[year]

        # extract requested period
        selected = workbook.index.get_level_values("year") == year
        if month is not None:
            selected &= workbook.index.get_level_values("month") == month
        data = workbook[selected]
        if len(data) == 0:
            raise ValueError(f"{year=} {month=} is not available in {cachefile} "
                "(not yet published by EIA, or use refresh=True to "
                "download a newer workbook)")
        data = data.reset_index()
        data["year"] = data["year"].astype(int)
        data["month"] = data["month"].astype(int)

        # construct dataframe
        if not raw:
            data = data.dropna(subset="status").fillna(0.0)
            data["timestamp"] = [month_start(y,m) for y,m in zip(data["year"],data["month"])]
            data = data.drop(["year","month","status"],axis=1)
            def tofloat(x):
                try:
                    return float(x)
                except ValueError:
                    return 0.0
            for column in [x for x in data.columns if x.endswith("_mw") or x.endswith("_mwh")]:
                data[column] = [tofloat(x) for x in data[column]]
            data = data.set_index(self.INDEX).sort_index()
        else:
            data = data.reset_index(drop=True)
        super().__init__(data)

    @classmethod
    def _load(cls,year:int,cachefile:str,refresh:bool) -> pd.DataFrame:
        """@private Load a year's workbook, indexed by `year` and `month`"""

        # read data from network if necessary
        if refresh or not os.path.exists(cachefile):
            content = None
            urls = [x.format(year=year) for x in cls.FORM861M_URLS]
            for url in urls:
                req = download(url,missing_ok=True)
                if req is not None:
                    content = req.content
                    break
            if content is None:
                raise RuntimeError(f"{year=} not found at any of {urls}")
            with open(cachefile,"wb") as fh:
                fh.write(content)

        # load workbook from cache
        try:
            return pd.read_excel(cachefile,
                engine="openpyxl",
                sheet_name="Monthly Totals- States",
                skiprows=3,
                names=["year","month","state","status",
                    "res_mw","com_mw","ind_mw","tot_mw",
                    "res_mwh","com_mwh","ind_mwh","tot_mwh",
                    ],
                dtype = {"state":str},
                index_col=[0,1],
                ).sort_index()
        # pylint: disable=broad-exception-caught
        except Exception as err:
            warnings.warn(f"unable to read {cachefile} ({err})--"\
                "deleting invalid cache file")
            if os.path.exists(cachefile):
                os.unlink(cachefile)
            raise RuntimeError(f"{cachefile=} is not valid") from err


if __name__ == '__main__':

    pd.options.display.width = None
    pd.options.display.max_columns = None
    pd.options.display.max_rows = None

    result = []
    for year in range(2018,2023):
        for month in range(12):
            result.append(Form861m(year,month+1))
    result = pd.concat(result).xs("WA",level="state")
    sectors = ["res","com","ind"]
    for sector in sectors:
        result[f"{sector}_cf"] = result[f"{sector}_mwh"] / result["tot_mwh"]
    try:
        import matplotlib.pyplot as plt
        result[[f"{x}_cf" for x in sectors]].plot(kind="area")
        plt.show()
        print(result[[f"{x}_cf" for x in sectors]])
    except ModuleNotFoundError:
        print(result[[f"{x}_cf" for x in sectors]])

