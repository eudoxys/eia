"""Access Form930 hourly data for balancing authorities and regions

Examples
--------

To get the August 2020 California load, generation, and interchange use the
following

    from eia import Form930
    Form930("CAL",2020,8)

To get the August 2020 Bonneville Power Administration net generation by
energy source use the following

    from eia import Form930Fuel
    Form930Fuel("BPAT",2020,8)

which returns one `{code}_MW` column per energy source reported by the
respondent, e.g., `NG_MW`, `NUC_MW`, `SUN_MW`, `WAT_MW`, `WND_MW`.

Time convention
---------------

The EIA API reports hourly values in UTC with the timestamp at the end of
the hour. Both classes return a `timestamp` column in UTC at the **beginning**
of the hour, so the value at `2020-08-01 00:00:00+00:00` covers
00:00 to 01:00 UTC.

Caveat
------

  - You must register with the EIA Open Data API
    at https://www.eia.gov/opendata/register.php to obtain an API key. The API
    key must be stored in `~/.eia/api_key` or in the environment variable
    `EIA_API_KEY`.

  - Balancing authority and region data starts in July 2015. Data by energy
    source starts in July 2018.

References
----------

  - https://www.eia.gov/electricity/gridmonitor/about

  - https://www.eia.gov/opendata/browser/electricity/rto
"""
import os
import datetime as dt
import pandas as pd
import requests

from cache import Cache

def _api_key() -> str:
    """@private Get the EIA API key"""
    if "EIA_API_KEY" in os.environ:
        return os.environ["EIA_API_KEY"]
    with open(os.path.join(os.environ["HOME"],".eia","api_key"),"r",encoding="utf-8") as fh:
        return fh.read().strip()

def _months(month:int|None) -> list[int]:
    """@private Get list of months to load"""
    if month is None:
        return list(range(1,13))
    assert isinstance(month,int) and 1 <= month <= 12, f"{month=} is invalid"
    return [month]

def _hours(year:int,month:int) -> pd.DatetimeIndex:
    """@private Get hour-beginning UTC timestamps for a month"""
    start = pd.Timestamp(year=year,month=month,day=1,tz="UTC")
    return pd.date_range(start,start+pd.DateOffset(months=1),freq="h",inclusive="left",name="timestamp")

class _Form930Base(pd.DataFrame):
    """@private Common Form 930 API access"""

    API_URL = "https://api.eia.gov/v2/electricity/rto/{route}/data/"
    """@private URL for Form 930 API queries"""

    PAGE_LENGTH = 5000
    """@private maximum number of rows per API request"""

    REFERENCE_URL = "https://www.eia.gov/electricity/930-content/EIA930_Reference_Tables.xlsx"
    """URL for Form 930 reference sheets"""

    references = {}
    """@private runtime cache of reference data"""

    @classmethod
    def _download(cls,route:str,facets:dict[str,list[str]],year:int,month:int) -> pd.DataFrame:
        """@private Download one month of hourly data from the API

        The API timestamps are UTC hour-ending, so the request starts at hour
        ending 01:00 on the first of the month and ends at hour ending 00:00
        on the first of the next month.
        """
        start = pd.Timestamp(year=year,month=month,day=1)
        end = start + pd.DateOffset(months=1)
        params = [
            ("frequency","hourly"),
            ("data[0]","value"),
            ("start",(start+pd.Timedelta(hours=1)).strftime("%Y-%m-%dT%H")),
            ("end",end.strftime("%Y-%m-%dT%H")),
            ("sort[0][column]","period"),
            ("sort[0][direction]","asc"),
            ("length",cls.PAGE_LENGTH),
            ("api_key",_api_key()),
            ] + [(f"facets[{x}][]",z) for x,y in facets.items() for z in y]
        url = cls.API_URL.format(route=route)
        result = []
        offset = 0
        while True:
            req = requests.get(url,params=params+[("offset",offset)],timeout=300)
            if req.status_code != 200:
                raise RuntimeError(f"{url} {route=} {facets=} {year=} {month=} --> HTTP {req.status_code}")
            response = req.json()["response"]
            data = response["data"]
            result.extend(data)
            offset += len(data)
            if not data or offset >= int(response.get("total",0)):
                break
        if not result:
            return pd.DataFrame(columns=["period","respondent","type","fueltype","value"])
        return pd.DataFrame(result)

    @classmethod
    def _cached(cls,route:str,respondent:str,facets:dict[str,list[str]],
            year:int,month:int,refresh:bool) -> pd.DataFrame:
        """@private Get one month of raw API data, using the cache if possible"""
        cache = Cache(
            package="eia",
            version=1,
            path=["form930",route,f"{respondent}-{year}-{month:02d}.csv.gz"],
            )
        if cache.exists() and not refresh:
            try:
                return pd.read_csv(cache.pathname,keep_default_na=False,na_values=[""])
            except Exception: # pylint: disable=broad-exception-caught
                cache.delete()
        data = cls._download(route,facets,year,month)
        data.to_csv(cache.pathname,index=False,header=True,compression="gzip")
        return data

    @staticmethod
    def _timestamp(period:pd.Series) -> pd.DatetimeIndex:
        """@private Convert API UTC hour-ending periods to hour-beginning timestamps"""
        return pd.DatetimeIndex(pd.to_datetime(period,format="%Y-%m-%dT%H",utc=True)) - pd.Timedelta(hours=1)

    @staticmethod
    def respondents() -> list[str]:
        """Get valid respondent codes (balancing authorities and regions)

        Returns
        -------

          - `list[str]`: balancing authority and region codes
        """
        codes = set()
        for sheet,column in [("BAs","BA Code"),("Regions","Region/Country Code")]:
            try:
                codes |= set(_Form930Base.reference_data(sheet)[column].dropna())
            except (KeyError,ValueError) as err:
                raise RuntimeError(f"Form 930 reference sheet {sheet=} has no {column=}") from err
        return sorted(codes)

    @staticmethod
    def reference_data(sheet):
        """Download Form930 reference data sheets

        Arguments
        ---------

          - `sheet`: sheet name to return

        Returns
        -------

          - `pandas.DataFrame`: sheet data
        """
        if sheet in _Form930Base.references:
            return _Form930Base.references[sheet]

        cache = Cache(package="eia",version=0,path=["reference",f"{sheet}.csv"])
        if cache.exists():
            try:
                data = pd.read_csv(cache.pathname)
            except Exception: # pylint: disable=broad-exception-caught
                data = None
        else:
            data = None
        if data is None:
            data = pd.read_excel(
                _Form930Base.REFERENCE_URL,
                sheet_name=sheet,
                )
            data.to_csv(cache.pathname,index=False,header=True)

        _Form930Base.references[sheet] = data
        return data

class Form930(_Form930Base):
    """Form930 load, generation, and interchange data frame

    Columns
    -------

      - `timestamp`: UTC date and time of the beginning of the hour

      - `load_MW`: load value

      - `generation_MW`: net generation value

      - `interchange_MW`: total interchange value (positive is export)
    """

    TYPES = {
        "D": "load_MW",
        "NG": "generation_MW",
        "TI": "interchange_MW",
        }
    """API data types and the columns they are returned in"""

    FIRST_MONTH = (2015,7)
    """First year and month of data available"""

    TIMEZONES = {
        "Eastern":-5,
        "Central":-6,
        "Mountain":-7,
        "Arizona":-7,
        "Pacific":-8,
    }
    """@private Standard time offsets of respondent time zones (no longer used
    for timestamps, which are UTC)"""

    def __init__(self,
        region:str,
        year:int,
        month:int|None=None,
        *,
        refresh:bool=False,
        ):
        """Access Form 930 data for a region or balancing authority

        Arguments
        ---------

          - `region`: region or balancing authority code (see
            `eia.Form930.respondents()`)

          - `year`: year of data

          - `month`: month of data (`None` accesses entire year)

          - `refresh`: force cache refresh
        """
        assert region in self.respondents(), f"{region=} is not valid"
        assert isinstance(year,int) and self.FIRST_MONTH[0] <= year <= dt.datetime.now().year, \
            f"{year=} is invalid"

        result = []
        for mon in _months(month):
            if (year,mon) < self.FIRST_MONTH:
                continue
            data = self._cached("region-data",region,{"respondent":[region],"type":list(self.TYPES)},
                year,mon,refresh)
            data = data.assign(timestamp=self._timestamp(data["period"]),value=data["value"].astype(float))
            data = data.pivot_table(index="timestamp",columns="type",values="value",aggfunc="sum")
            data = data.reindex(index=_hours(year,mon),columns=list(self.TYPES)).rename(self.TYPES,axis=1)
            data.columns.name = None
            result.append(data.reset_index())

        super().__init__(pd.concat(result,ignore_index=True) if result \
            else pd.DataFrame(columns=["timestamp"]+list(self.TYPES.values())))

class Form930Fuel(_Form930Base):
    """Form930 net generation by energy source data frame

    Columns
    -------

      - `timestamp`: UTC date and time of the beginning of the hour

      - `{code}_MW`: net generation from energy source `code`, one column per
        code the respondent reports, e.g., `COL`, `NG`, `NUC`, `OIL`, `OTH`,
        `SUN`, `WAT`, `WND`, and the newer storage and geothermal codes.

    Missing hours are `NaN`. Codes a respondent never reports in the period are
    not included as columns.
    """

    FIRST_MONTH = (2018,7)
    """First year and month of data available"""

    def __init__(self,
        respondent:str,
        year:int,
        month:int|None=None,
        *,
        fuels:list[str]|None=None,
        refresh:bool=False,
        ):
        """Access Form 930 net generation by energy source

        Arguments
        ---------

          - `respondent`: balancing authority or region code (see
            `eia.Form930Fuel.respondents()`)

          - `year`: year of data (2018 or later)

          - `month`: month of data (`None` accesses entire year; months
            before July 2018 are omitted)

          - `fuels`: energy source codes to include (`None` includes all)

          - `refresh`: force cache refresh
        """
        assert respondent in self.respondents(), f"{respondent=} is not valid"
        assert isinstance(year,int) and self.FIRST_MONTH[0] <= year <= dt.datetime.now().year, \
            f"{year=} is invalid"
        if isinstance(fuels,str):
            fuels = [fuels]

        result = []
        for mon in _months(month):
            if (year,mon) < self.FIRST_MONTH:
                continue
            data = self._cached("fuel-type-data",respondent,{"respondent":[respondent]},
                year,mon,refresh)
            if fuels is not None:
                data = data.loc[data["fueltype"].isin(fuels)]
            data = data.assign(timestamp=self._timestamp(data["period"]),value=data["value"].astype(float))
            data = data.pivot_table(index="timestamp",columns="fueltype",values="value",aggfunc="sum")
            data = data.reindex(index=_hours(year,mon))
            data.columns = [f"{x}_MW" for x in data.columns]
            result.append(data.reset_index())

        if not result:
            raise ValueError(f"no energy source data before {self.FIRST_MONTH} ({year=}, {month=})")
        data = pd.concat(result,ignore_index=True)
        super().__init__(data[["timestamp"]+sorted(x for x in data.columns if x != "timestamp")])

if __name__ == "__main__":

    pd.options.display.width = None
    pd.options.display.max_columns = None

    print(Form930("CAL",2020,8))
    print(Form930Fuel("BPAT",2020,8))
