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
    check_published, download

_cache = {}

class Form861m(FormBase):
    """The `Form861m` class is a Pandas data frame loaded with the EIA Form 861
    distributed/small scale solar data for US states starting in 2017.

    The data frame has a default integer index, one row per state, and the
    following columns.

      - `date`: the first day of the requested month (UTC).

      - `state`: the state for which the values are in effect.

      - `res_mw`: the residential power capacity in megaWatts.

      - `com_mw`: the commercial power capacity in megaWatts.

      - `ind_mw`: the industrial power capacity in megaWatts.

      - `tot_mw`: the total power capacity in megaWatts.

      - `res_mwh`: the residential energy production in megaWatts hours.

      - `com_mwh`: the commercial energy production in megaWatts hours.

      - `ind_mwh`: the industrial energy production in megaWatts hours.

      - `tot_mwh`: the total energy production in megaWatts hours.

    Missing and non-numeric values are set to `0.0`.

    If the `raw` argument is `True`, the EIA rows for the requested month are
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

    def __init__(self,
        year:int|str,
        month:int|str,
        refresh:bool=False,
        raw:bool=False,
        ):
        """Construct EIA Form 861 data frame

        Arguments
        ---------

          - `year`: specifies the year (2017 to present)

          - `month`: specifies the month (1 to 12, or a name or abbreviation
            such as `"August"` or `"Aug"`)

          - `refresh`: refresh data cache (default `False`)

          - `raw`: disable data frame cleanup, i.e., don't set `NaN` values
            to 0.0, construct the `date` column, or remove the `year`,
            `month`, and `status` columns (default `False`)

        Raises
        ------

          - `TypeError`: an argument has the wrong type

          - `ValueError`: `year` or `month` is not valid, or the month is
            not published

          - `RuntimeError`: the workbook cannot be downloaded or read
        """

        year = check_year(year,2017)
        month = check_month(month)
        check_published(year,month)
        refresh = check_bool("refresh",refresh)
        raw = check_bool("raw",raw)

        global _cache
        cache_key = f"{year}-{month:02d}"
        if not cache_key in _cache or refresh:

            # download data from EIA
            cachefile = cache_entry("form861m",f"{year}.xlsx",
                version=self.CACHE_VERSION).pathname

            # read data from network if necessary
            if refresh or not os.path.exists(cachefile):
                content = None
                urls = [x.format(year=year) for x in self.FORM861M_URLS]
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
                workbook = pd.read_excel(cachefile,
                    engine="openpyxl",
                    sheet_name="Monthly Totals- States",
                    skiprows=3,
                    names=["year","month","state","status",
                        "res_mw","com_mw","ind_mw","tot_mw",
                        "res_mwh","com_mwh","ind_mwh","tot_mwh",
                        ],
                    # na_values = ["NM","."],
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

            # extract requested month
            try:
                data = workbook.loc[(year,month),:].reset_index()
            except KeyError as err:
                raise ValueError(f"{year=} {month=} is not available in {cachefile} "
                    "(not yet published by EIA, or use refresh=True to "
                    "download a newer workbook)") from err

            _cache[cache_key] = data.copy()
        else:
            data = _cache[cache_key].copy()

        # construct dataframe
        if not raw:
            data.dropna(subset="status",inplace=True)
            data.fillna(0.0,inplace=True)
            data.index = pd.DatetimeIndex([f"{year}-{month:02d}-01 00:00:00+00:00"
                for y,m in zip(data.year,data.month)],tz=0)
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
            data.reset_index(inplace=True)
        else:
            data.month = data.month.astype(int)
            data.year = data.year.astype(int)
            data.reset_index(drop=True,inplace=True)
        super().__init__(data)


if __name__ == '__main__':

    pd.options.display.width = None
    pd.options.display.max_columns = None
    pd.options.display.max_rows = None

    result = []
    for year in range(2018,2023):
        for month in range(12):
            result.append(Form861m(year,month+1))
    result = pd.concat(result).set_index("state").loc["WA"].set_index("date")
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

