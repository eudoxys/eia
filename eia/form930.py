"""Access Form930 hourly data for balancing authorities and regions

Examples
--------

To get the August 2020 California load, generation, and interchange use the
following

    from eia import Form930
    Form930(2020,8,respondent="CAL")

To get the August 2020 Bonneville Power Administration net generation by
energy source use the following

    from eia import Form930Fuel
    Form930Fuel(2020,8,respondent="BPAT")

which returns one `{code}_mw` column per energy source reported by the
respondent, e.g., `ng_mw`, `nuc_mw`, `sun_mw`, `wat_mw`, `wnd_mw`.

Time convention
---------------

The EIA API reports hourly values in UTC with the timestamp at the end of
the hour. Both classes are indexed by `timestamp` in UTC at the **beginning**
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
import zipfile
import pandas as pd

from eia.base import FormBase, cache_entry, check_year, check_month, check_bool, \
    check_published, check_list, latest_month, download

API_KEY_ENV = "EIA_API_KEY"
"""Environment variable holding the EIA Open Data API key"""

API_KEY_FILE = os.path.join("~",".eia","api_key")
"""File holding the EIA Open Data API key (used when `EIA_API_KEY` is not set)"""

REGISTER_URL = "https://www.eia.gov/opendata/register.php"
"""URL where an EIA Open Data API key can be obtained"""

def _api_key() -> str:
    """@private Get the EIA API key

    The key is read from the `EIA_API_KEY` environment variable or, when that
    is not set or empty, from the file `~/.eia/api_key`.

    Raises
    ------

      - `RuntimeError`: no API key was found
    """
    key = os.environ.get(API_KEY_ENV,"").strip()
    if key:
        return key
    path = os.path.expanduser(API_KEY_FILE)
    try:
        with open(path,"r",encoding="utf-8") as fh:
            key = fh.read().strip()
    except FileNotFoundError:
        key = ""
    except OSError as err:
        raise RuntimeError(f"unable to read EIA API key file '{path}' "
            f"({type(err).__name__})") from None
    if not key:
        raise RuntimeError(f"no EIA API key found: set the environment variable {API_KEY_ENV} "
            f"or save the key in '{path}' (register for a key at {REGISTER_URL})")
    return key

def _months(year:int,month:int|None) -> list[int]:
    """@private Get list of months to load

    A single month is checked against the current month (Form 930 data are
    published hourly, so the current month is allowed). When `month` is
    `None`, months after the current month are omitted.
    """
    if month is not None:
        check_published(year,month,lag=0)
        return [month]
    last = latest_month(lag=0)
    return [x for x in range(1,13) if (year,x) <= last]

def _hours(year:int,month:int) -> pd.DatetimeIndex:
    """@private Get hour-beginning UTC timestamps for a month"""
    start = pd.Timestamp(year=year,month=month,day=1,tz="UTC")
    return pd.date_range(start,start+pd.DateOffset(months=1),freq="h",inclusive="left",
        name="timestamp")

class _Form930Base(FormBase):
    """@private Common Form 930 API access"""

    API_URL = "https://api.eia.gov/v2/electricity/rto/{route}/data/"
    """@private URL for Form 930 API queries"""

    PAGE_LENGTH = 5000
    """@private maximum number of rows per API request"""

    REFERENCE_URL = "https://www.eia.gov/electricity/930-content/EIA930_Reference_Tables.xlsx"
    """URL for Form 930 reference sheets"""

    references = {}
    """@private runtime cache of reference data"""

    _references_refreshed = False
    """@private whether the reference workbook was downloaded by this process"""

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
            try:
                req = download(url,params=params+[("offset",offset)])
            except RuntimeError as err:
                raise RuntimeError(f"{route=} {facets=} {year=} {month=}: {err}") from err
            response = req.json()["response"]
            data = response["data"]
            result.extend(data)
            offset += len(data)
            if not data or offset >= int(response.get("total",0)):
                break
        if not result:
            return cls._empty_raw()
        return pd.DataFrame(result)

    @classmethod
    def _cached(cls,route:str,respondent:str,facets:dict[str,list[str]],
            year:int,month:int,refresh:bool) -> pd.DataFrame:
        """@private Get one month of raw API data, using the cache if possible"""
        cache = cache_entry("form930",route,f"{respondent}-{year}-{month:02d}.csv.gz",version=1)
        if cache.exists() and not refresh:
            try:
                return pd.read_csv(cache.pathname,keep_default_na=False,na_values=[""])
            except Exception: # pylint: disable=broad-exception-caught
                cache.delete()
        data = cls._download(route,facets,year,month)
        data.to_csv(cache.pathname,index=False,header=True,compression="gzip")
        return data

    @staticmethod
    def _empty_raw() -> pd.DataFrame:
        """@private Empty API record frame"""
        return pd.DataFrame(columns=["period","respondent","type","fueltype","value"])

    @staticmethod
    def _timestamp(period:pd.Series) -> pd.DatetimeIndex:
        """@private Convert API UTC hour-ending periods to hour-beginning timestamps"""
        return pd.DatetimeIndex(pd.to_datetime(period,format="%Y-%m-%dT%H",utc=True)) \
            - pd.Timedelta(hours=1)

    @classmethod
    def _check_respondent(cls,name:str,value:str,refresh:bool=False):
        """@private Validate a respondent code argument

        When `refresh` is set, or the code is not found in the cached
        reference data, the reference data are downloaded again (at most
        once per process unless `refresh` is set) so that respondent codes
        EIA added since the cache was made are accepted.
        """
        if not isinstance(value,str):
            raise TypeError(f"{name} must be a str, not {type(value).__name__} "
                "(`--respondent` or `--region` on the command line)")
        if value in cls.respondents(refresh=refresh):
            return
        if not refresh and not _Form930Base._references_refreshed \
                and value in cls.respondents(refresh=True):
            return
        raise ValueError(f"{name}={value!r} is not a valid respondent code "
            "(see `respondents()`)")

    @staticmethod
    def respondents(refresh:bool=False) -> list[str]:
        """Get valid respondent codes (balancing authorities and regions)

        Arguments
        ---------

          - `refresh`: download the reference data again (default `False`)

        Returns
        -------

          - `list[str]`: balancing authority and region codes
        """
        if refresh:
            _Form930Base._refresh_references()
        codes = set()
        for sheet,column in [("BAs","BA Code"),("Regions","Region/Country Code")]:
            try:
                codes |= set(_Form930Base.reference_data(sheet)[column].dropna())
            except (KeyError,ValueError) as err:
                raise RuntimeError(f"Form 930 reference sheet {sheet=} has no {column=}") from err
        return sorted(codes)

    @staticmethod
    def _reference_cache():
        """@private Cache entry for the reference workbook"""
        return cache_entry("reference","EIA930_Reference_Tables.xlsx",version=1)

    @staticmethod
    def _refresh_references():
        """@private Download the reference workbook into the cache"""
        cache = _Form930Base._reference_cache()
        content = download(_Form930Base.REFERENCE_URL).content
        with open(cache.pathname,"wb") as fh:
            fh.write(content)
        _Form930Base.references.clear()
        _Form930Base._references_refreshed = True

    @staticmethod
    def reference_data(sheet:str,refresh:bool=False) -> pd.DataFrame:
        """Get Form 930 reference data sheets

        The reference workbook is downloaded once and cached; use `refresh`
        to download it again (e.g., when EIA adds respondents).

        Arguments
        ---------

          - `sheet`: sheet name to return

          - `refresh`: download the reference workbook again (default
            `False`)

        Returns
        -------

          - `pandas.DataFrame`: sheet data
        """
        if refresh:
            _Form930Base._refresh_references()
        if sheet in _Form930Base.references:
            return _Form930Base.references[sheet]

        cache = _Form930Base._reference_cache()
        if not cache.exists():
            _Form930Base._refresh_references()
        try:
            data = pd.read_excel(cache.pathname,sheet_name=sheet)
        except zipfile.BadZipFile:
            # corrupt cache file: download again
            _Form930Base._refresh_references()
            data = pd.read_excel(cache.pathname,sheet_name=sheet)

        _Form930Base.references[sheet] = data
        return data

class Form930(_Form930Base):
    """Form930 load, generation, and interchange data frame

    Index
    -----

      - `timestamp`: UTC date and time of the beginning of the hour

    Columns
    -------

      - `load_mw`: load (demand) in MW

      - `generation_mw`: net generation in MW

      - `interchange_mw`: total interchange in MW (positive is export)

    Missing hours are `NaN`.

    If the `raw` argument is `True`, the EIA API records for the requested
    period are returned unchanged (columns `period`, `respondent`, `type`,
    `value`, and the other fields the API returns; `period` is UTC
    hour-ending) with a default integer index.
    """

    TYPES = {
        "D": "load_mw",
        "NG": "generation_mw",
        "TI": "interchange_mw",
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
        year:int|str,
        month:int|str|None=None,
        *,
        respondent:str,
        raw:bool=False,
        refresh:bool=False,
        ):
        """Access Form 930 data for a region or balancing authority

        Arguments
        ---------

          - `year`: year of data (2015 or later, as `int` or `str`)

          - `month`: month of data (1 to 12, or a name or abbreviation such
            as `"Aug"`; `None` accesses entire year; months before July 2015
            are omitted)

          - `respondent`: region or balancing authority code (required; see
            `eia.Form930.respondents()`)

          - `raw`: return the EIA API records unchanged (default `False`)

          - `refresh`: force cache refresh (including the respondent
            reference data)

        Raises
        ------

          - `TypeError`: an argument has the wrong type, or `respondent` is
            missing

          - `ValueError`: `respondent`, `year` or `month` is not valid, or
            the month is in the future
        """
        year = check_year(year,self.FIRST_MONTH[0])
        month = check_month(month,optional=True)
        raw = check_bool("raw",raw)
        refresh = check_bool("refresh",refresh)
        self._check_respondent("respondent",respondent,refresh=refresh)

        result = []
        for mon in _months(year,month):
            if (year,mon) < self.FIRST_MONTH:
                continue
            data = self._cached("region-data",respondent,
                {"respondent":[respondent],"type":list(self.TYPES)},year,mon,refresh)
            if raw:
                result.append(data)
                continue
            data = data.assign(timestamp=self._timestamp(data["period"]),
                value=data["value"].astype(float))
            data = data.pivot_table(index="timestamp",columns="type",values="value",aggfunc="sum")
            data = data.reindex(index=_hours(year,mon),columns=list(self.TYPES)) \
                .rename(self.TYPES,axis=1)
            data.columns.name = None
            result.append(data)

        if raw:
            super().__init__(pd.concat(result,ignore_index=True) if result else self._empty_raw())
        elif result:
            super().__init__(pd.concat(result))
        else:
            super().__init__(pd.DataFrame(columns=list(self.TYPES.values()),dtype=float,
                index=pd.DatetimeIndex([],tz="UTC",name="timestamp")))

class Form930Fuel(_Form930Base):
    """Form930 net generation by energy source data frame

    Index
    -----

      - `timestamp`: UTC date and time of the beginning of the hour

    Columns
    -------

      - `{code}_mw`: net generation in MW from energy source `code`
        (lower-cased EIA code), one column per code the respondent reports,
        e.g., `col_mw`, `ng_mw`, `nuc_mw`, `oil_mw`, `oth_mw`, `sun_mw`,
        `wat_mw`, `wnd_mw`, and the newer storage and geothermal codes.

    Missing hours are `NaN`. Codes a respondent never reports in the period are
    not included as columns.

    If the `raw` argument is `True`, the EIA API records for the requested
    period are returned unchanged (columns `period`, `respondent`,
    `fueltype`, `value`, and the other fields the API returns; `period` is
    UTC hour-ending) with a default integer index; `fuels` is ignored.
    """

    FIRST_MONTH = (2018,7)
    """First year and month of data available"""

    def __init__(self,
        year:int|str,
        month:int|str|None=None,
        *,
        respondent:str,
        fuels:list[str]|None=None,
        raw:bool=False,
        refresh:bool=False,
        ):
        """Access Form 930 net generation by energy source

        Arguments
        ---------

          - `year`: year of data (2018 or later, as `int` or `str`)

          - `month`: month of data (1 to 12, or a name or abbreviation such
            as `"Aug"`; `None` accesses entire year; months before July 2018
            are omitted)

          - `respondent`: balancing authority or region code (required; see
            `eia.Form930Fuel.respondents()`)

          - `fuels`: energy source code or codes to include, e.g., `"NG"` or
            `["wat","wnd"]` (not case sensitive; `None` includes all)

          - `raw`: return the EIA API records unchanged (default `False`)

          - `refresh`: force cache refresh

        Raises
        ------

          - `TypeError`: an argument has the wrong type, or `respondent` is
            missing

          - `ValueError`: `respondent`, `year` or `month` is not valid, the
            month is in the future, or no data is available before the first
            published month
        """
        year = check_year(year,self.FIRST_MONTH[0])
        month = check_month(month,optional=True)
        fuels = check_list("fuels",fuels)
        raw = check_bool("raw",raw)
        refresh = check_bool("refresh",refresh)
        self._check_respondent("respondent",respondent,refresh=refresh)
        if fuels is not None:
            fuels = [x.upper() for x in fuels]

        result = []
        for mon in _months(year,month):
            if (year,mon) < self.FIRST_MONTH:
                continue
            data = self._cached("fuel-type-data",respondent,{"respondent":[respondent]},
                year,mon,refresh)
            if raw:
                result.append(data)
                continue
            if fuels is not None:
                data = data.loc[data["fueltype"].str.upper().isin(fuels)]
            data = data.assign(timestamp=self._timestamp(data["period"]),
                value=data["value"].astype(float))
            data = data.pivot_table(index="timestamp",columns="fueltype",values="value",
                aggfunc="sum")
            data = data.reindex(index=_hours(year,mon))
            data.columns = [f"{x.lower()}_mw" for x in data.columns]
            result.append(data)

        if not result:
            raise ValueError(f"no energy source data before {self.FIRST_MONTH} ({year=}, {month=})")
        if raw:
            super().__init__(pd.concat(result,ignore_index=True))
            return
        data = pd.concat(result)
        super().__init__(data[sorted(data.columns)])
