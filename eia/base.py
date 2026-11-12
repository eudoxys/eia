"""Common base class for EIA form data frames

All form classes derive from `eia.base.FormBase`, which provides the
`makeargs()` method the command line tool uses to map its options to the
form constructor's arguments.

Cache location
--------------

Downloaded data are cached under `{cache_dir}/eia/{version}/...`, where
`cache_dir` is, in order of precedence,

  1. the folder given to `eia.base.set_cache_dir()` (also available as
     `eia.set_cache_dir()`),

  2. the environment variable `EIA_CACHE_DIR`, or

  3. the platform user cache folder for Eudoxys packages, e.g.,
     `~/.cache/eudoxys` on Linux, `~/Library/Caches/eudoxys` on macOS, and
     `%LOCALAPPDATA%\\eudoxys\\Cache` on Windows.

The cache is never written inside the installed package. Use
`eia.base.clear_cache()` to delete all cached `eia` data.

Network access
--------------

All downloads from EIA go through `eia.base.download()`, which applies a
timeout, retries transient failures (connection errors, timeouts, HTTP 429
and 5xx responses) with exponential backoff, and checks the HTTP status.
The defaults can be changed with `eia.base.set_download_options()` or the
environment variables `EIA_TIMEOUT` (seconds) and `EIA_RETRIES`.
"""
import os
import re
import time
import shutil
import inspect
import numbers
import datetime as dt
import types
import typing
import pandas as pd
import platformdirs
import requests
from cache import Cache

CACHE_ENV = "EIA_CACHE_DIR"
"""Environment variable that overrides the default cache folder"""

CACHE_PACKAGE = "eia"
"""@private Package name used for cache entries"""

_cache_dir = None
"""@private Cache folder set by `set_cache_dir()` (`None` uses the default)"""

def cache_dir() -> str:
    """Get the cache folder

    Returns
    -------

      - `str`: the folder under which `eia/{version}/...` cache files are
        stored (see the module documentation for how it is chosen)
    """
    if _cache_dir is not None:
        return _cache_dir
    path = os.environ.get(CACHE_ENV)
    if path:
        return os.path.abspath(os.path.expanduser(path))
    return platformdirs.user_cache_dir("eudoxys",appauthor=False)

def set_cache_dir(path:str|None) -> str:
    """Set the cache folder

    Arguments
    ---------

      - `path`: folder under which `eia/{version}/...` cache files are
        stored; `None` restores the default (`EIA_CACHE_DIR` or the
        platform user cache folder)

    Returns
    -------

      - `str`: the previous cache folder
    """
    global _cache_dir # pylint: disable=global-statement
    old = cache_dir()
    _cache_dir = None if path is None else os.path.abspath(os.path.expanduser(str(path)))
    return old

def clear_cache():
    """Delete all cached `eia` data in the current cache folder"""
    shutil.rmtree(os.path.join(cache_dir(),CACHE_PACKAGE),ignore_errors=True)

class _EIACache(Cache):
    """@private `cache.Cache` rooted at the `eia` cache folder"""
    CACHEDIR = None

def cache_entry(*path:str,version:int) -> Cache:
    """@private Get a cache entry for `eia` data

    Arguments
    ---------

      - `*path`: path of the cache file relative to the package cache
        folder, e.g., `"form923", "2020.csv.gz"`

      - `version`: cache schema version; bump it when the cached layout
        changes so that stale files are ignored

    Returns
    -------

      - `cache.Cache`: cache entry at `{cache_dir}/eia/{version}/{path}`
        (the parent folder is created if necessary)
    """
    _EIACache.CACHEDIR = cache_dir()
    return _EIACache(list(path),package=CACHE_PACKAGE,version=version)

TIMEOUT_ENV = "EIA_TIMEOUT"
"""Environment variable that overrides the default download timeout (seconds)"""

RETRIES_ENV = "EIA_RETRIES"
"""Environment variable that overrides the default number of download retries"""

DEFAULT_TIMEOUT = 300.0
"""Default download timeout in seconds (per request)"""

DEFAULT_RETRIES = 3
"""Default number of retries after a transient download failure"""

RETRY_STATUS = frozenset({429,500,502,503,504})
"""@private HTTP status codes that are retried"""

_download_options = {"timeout":None,"retries":None,"backoff":1.0}
"""@private Download options set by `set_download_options()`"""

def _env_number(name:str,kind:type,default):
    """@private Get a numeric environment variable (invalid values use `default`)"""
    try:
        value = kind(os.environ[name])
        return value if value >= 0 else default
    except (KeyError,ValueError):
        return default

def download_options() -> dict:
    """Get the current download options

    Returns
    -------

      - `dict`: `timeout` (seconds), `retries` (count), and `backoff`
        (seconds before the first retry, doubled after each retry)
    """
    timeout = _download_options["timeout"]
    retries = _download_options["retries"]
    return {
        "timeout": _env_number(TIMEOUT_ENV,float,DEFAULT_TIMEOUT) if timeout is None else timeout,
        "retries": _env_number(RETRIES_ENV,int,DEFAULT_RETRIES) if retries is None else retries,
        "backoff": _download_options["backoff"],
        }

def set_download_options(
        timeout:float|None=None,
        retries:int|None=None,
        backoff:float|None=None,
        ) -> dict:
    """Set the download options

    Arguments
    ---------

      - `timeout`: timeout in seconds for each request (`None` leaves it
        unchanged)

      - `retries`: number of retries after a transient failure (`None`
        leaves it unchanged)

      - `backoff`: seconds to wait before the first retry, doubled after
        each retry (`None` leaves it unchanged)

    Returns
    -------

      - `dict`: the previous download options (see `download_options()`)

    Raises
    ------

      - `ValueError`: an option is negative (or `timeout` is zero)
    """
    old = download_options()
    for name,value,kind in [("timeout",timeout,float),("retries",retries,int),
            ("backoff",backoff,float)]:
        if value is None:
            continue
        if isinstance(value,bool) or not isinstance(value,numbers.Real) or value < 0 \
                or (name == "timeout" and value == 0) or (kind is int and value != int(value)):
            raise ValueError(f"{name}={value!r} is not valid")
        _download_options[name] = kind(value)
    return old

def _redact(text:str) -> str:
    """@private Remove API keys from text"""
    return re.sub(r"(api_key=)[^&\s'\"]+",r"\1***",text)

def download(url:str,params=None,*,missing_ok:bool=False,
        timeout:float|None=None,retries:int|None=None) -> requests.Response|None:
    """Download a URL from EIA

    Arguments
    ---------

      - `url`: URL to download

      - `params`: query parameters (passed to `requests.get()`)

      - `missing_ok`: return `None` instead of raising an error when the
        server reports the URL does not exist (HTTP 404)

      - `timeout`: timeout in seconds (default from `download_options()`)

      - `retries`: retries after a transient failure (default from
        `download_options()`)

    Returns
    -------

      - `requests.Response`: the successful (HTTP 200) response, or `None`
        when `missing_ok` is set and the URL does not exist

    Raises
    ------

      - `RuntimeError`: the URL cannot be downloaded (API keys are removed
        from the message)
    """
    options = download_options()
    timeout = options["timeout"] if timeout is None else timeout
    retries = options["retries"] if retries is None else retries
    delay = options["backoff"]
    for attempt in range(retries+1):
        last = attempt == retries
        try:
            req = requests.get(url,params=params,timeout=timeout)
        except (requests.ConnectionError,requests.Timeout) as err:
            if last:
                detail = _redact(str(err))
                error = RuntimeError(f"'{url}' not available ({type(err).__name__} "
                    f"after {attempt+1} attempt(s), {timeout=}s: {detail})")
                # don't chain an exception whose text includes an API key
                raise error from (None if detail != str(err) else err)
        except requests.RequestException as err:
            detail = _redact(str(err))
            error = RuntimeError(f"'{url}' not available ({type(err).__name__}: {detail})")
            # don't chain an exception whose text includes an API key
            raise error from (None if detail != str(err) else err)
        else:
            if req.status_code == 200:
                return req
            if req.status_code == 404 and missing_ok:
                return None
            if req.status_code not in RETRY_STATUS or last:
                raise RuntimeError(f"'{url}' not available (HTTP error {req.status_code})")
        time.sleep(delay)
        delay *= 2
    raise AssertionError("unreachable") # pragma: no cover

def download_first(urls:list[str]) -> bytes:
    """Download the first of several URLs that exists

    Arguments
    ---------

      - `urls`: URLs to try in order; a URL the server reports does not
        exist (HTTP 404) is skipped

    Returns
    -------

      - `bytes`: the content of the first URL found

    Raises
    ------

      - `RuntimeError`: none of the URLs exists, or a URL cannot be
        downloaded (see `download()`)
    """
    for url in urls:
        req = download(url,missing_ok=True)
        if req is not None:
            return req.content
    raise RuntimeError(f"not found at any of {urls}")

def latest_month(lag:int=1) -> tuple[int,int]:
    """@private Get the latest month that can have been published

    Arguments
    ---------

      - `lag`: number of months after the current month (e.g., `1` means
        the month must have ended, `0` allows the current month)

    Returns
    -------

      - `tuple[int,int]`: year and month
    """
    now = dt.datetime.now()
    total = now.year*12 + now.month - 1 - lag
    return total // 12, total % 12 + 1

def check_published(year:int,month:int,lag:int=1):
    """@private Check that a month can have been published

    Arguments
    ---------

      - `year`: year

      - `month`: month (1 to 12)

      - `lag`: see `latest_month()`

    Raises
    ------

      - `ValueError`: the month is after the latest month that can have
        been published
    """
    last = latest_month(lag)
    if (year,month) > last:
        raise ValueError(f"{year=} {month=} is not published yet "
            f"(latest possible is {last[0]}-{last[1]:02d})")

MONTHS = ["january","february","march","april","may","june",
    "july","august","september","october","november","december"]
"""@private English month names (locale independent)"""

def month_number(month:int|str) -> int:
    """Convert a month to its number

    Arguments
    ---------

      - `month`: month number (`1` to `12`, as `int` or `str`), name
        (e.g., `"August"`), or abbreviation of at least three letters
        (e.g., `"Aug"`, `"Sept"`); names are not case sensitive

    Returns
    -------

      - `int`: month number (1 to 12)

    Raises
    ------

      - `TypeError`: `month` is not an `int` or `str`

      - `ValueError`: `month` is not a valid month number or name
    """
    if isinstance(month,str):
        text = month.strip().lower().rstrip(".")
        if text.isdigit():
            month = int(text)
        else:
            found = [n for n,x in enumerate(MONTHS,1) if len(text) >= 3 and x.startswith(text)]
            if len(found) != 1:
                raise ValueError(f"{month=} is not a valid month")
            return found[0]
    if not isinstance(month,numbers.Integral) or isinstance(month,bool):
        raise TypeError(f"month must be an int or str, not {type(month).__name__}")
    if not 1 <= month <= 12:
        raise ValueError(f"{month=} is not a valid month")
    return int(month)

def check_year(year:int|str|None,first:int,*,optional:bool=False) -> int|None:
    """@private Coerce and validate a year argument

    Arguments
    ---------

      - `year`: year as `int` or `str` (e.g., `2020` or `"2020"`)

      - `first`: first year for which the form publishes data

      - `optional`: accept `None` (returned unchanged)

    Returns
    -------

      - `int|None`: year

    Raises
    ------

      - `TypeError`: `year` is not an `int` or `str` (or `None` when
        `optional` is not set)

      - `ValueError`: `year` is not an integer, or is before `first` or
        after the current year
    """
    if year is None and optional:
        return None
    if isinstance(year,str):
        try:
            year = int(year.strip())
        except ValueError as err:
            raise ValueError(f"{year=} is not a valid year") from err
    if not isinstance(year,numbers.Integral) or isinstance(year,bool):
        raise TypeError(f"year must be an int or str, not {type(year).__name__}")
    year = int(year)
    last = dt.datetime.now().year
    if not first <= year <= last:
        raise ValueError(f"{year=} is not valid (must be {first} to {last})")
    return year

def check_month(month:int|str|None,*,optional:bool=False) -> int|None:
    """@private Coerce and validate a month argument

    Arguments
    ---------

      - `month`: month number, name or abbreviation (see
        `eia.base.month_number()`)

      - `optional`: accept `None` (returned unchanged)

    Returns
    -------

      - `int|None`: month number (1 to 12)

    Raises
    ------

      - `TypeError`: `month` is not an `int` or `str` (or `None` when
        `optional` is not set)

      - `ValueError`: `month` is not a valid month number or name
    """
    if month is None and optional:
        return None
    return month_number(month)

def check_bool(name:str,value:bool|None,default:bool=False) -> bool:
    """@private Validate a Boolean argument

    Arguments
    ---------

      - `name`: argument name (used in error messages)

      - `value`: argument value; `None` selects `default`

      - `default`: value used when `value` is `None`

    Returns
    -------

      - `bool`: argument value

    Raises
    ------

      - `TypeError`: `value` is not a `bool` or `None`
    """
    if value is None:
        return default
    if not isinstance(value,bool):
        raise TypeError(f"{name} must be a bool, not {type(value).__name__}")
    return value

def check_choice(name:str,value,choices) -> typing.Any:
    """@private Validate an argument that must be one of a set of choices

    Arguments
    ---------

      - `name`: argument name (used in error messages)

      - `value`: argument value

      - `choices`: valid values

    Returns
    -------

      - argument value

    Raises
    ------

      - `TypeError`: `value` is not hashable (when `choices` is a `dict` or
        `set`)

      - `ValueError`: `value` is not one of `choices`
    """
    try:
        valid = value in choices
    except TypeError as err:
        raise TypeError(f"{name}={value!r} has an invalid type") from err
    if not valid:
        raise ValueError(f"{name}={value!r} is not valid (must be one of {list(choices)})")
    return value

def check_list(name:str,value,item:type=str) -> list|None:
    """@private Coerce a filter argument to a list

    Arguments
    ---------

      - `name`: argument name (used in error messages)

      - `value`: a single value, a list (or tuple or set) of values, or
        `None`

      - `item`: type of each value

    Returns
    -------

      - `list|None`: list of values, or `None` when `value` is `None`
        (meaning "all")

    Raises
    ------

      - `TypeError`: a value is not of type `item`
    """
    if value is None:
        return None
    values = list(value) if isinstance(value,(list,tuple,set)) else [value]
    for x in values:
        if not isinstance(x,item) or (item is int and isinstance(x,bool)):
            raise TypeError(f"{name} must be a {item.__name__} or a list of {item.__name__}, "
                f"not {type(x).__name__}")
    return values

def month_start(year:int,month:int) -> pd.Timestamp:
    """@private Get the UTC timestamp of the beginning of a month"""
    return pd.Timestamp(year=year,month=month,day=1,tz="UTC")

class FormBase(pd.DataFrame):
    """Base class for EIA form data frames

    Public API convention
    ---------------------

    Every form follows the same convention (see `DESIGN.md` §5):

      - **Signature.** `Form(year, month=None, *, <filters>, raw=False,
        refresh=False)`. `year` and `month` are the only positional
        arguments; everything else is keyword-only. A required subject,
        such as the Form 930 `respondent`, is keyword-only with no default.

      - **Period.** `year` and `month` accept an `int` or a numeric `str`
        (`month` also accepts a name or abbreviation). `month=None`
        selects the whole year where the form supports it.

      - **Filters.** A filter accepts a single value or a list; `None`
        means "all".

      - **Time and shape.** The index is a `MultiIndex` (or, for Form 930,
        a `DatetimeIndex`) whose first level is `timestamp`, the
        tz-aware UTC beginning of the month or hour, followed by the
        natural keys of a row. Measured values are columns.

      - **Columns.** `lower_snake_case`, with a unit suffix on measured
        values (`_mw`, `_mwh`, `_kusd`, `_cpkwh`, `_qty`).

      - **Raw data.** `raw=True` returns the EIA data with only the period
        selection applied (no renaming, coercion, filtering or index).

    The form classes are loaders: the result of a pandas operation on a
    form (e.g., `.loc[]`, `.groupby()`, arithmetic) is a plain
    `pandas.DataFrame`, not an instance of the form class.
    """

    _metadata = []

    @property
    def _constructor(self):
        """@private pandas operations return plain data frames"""
        return pd.DataFrame

    @staticmethod
    def _accepts_int(annotation) -> bool:
        """@private Check whether an annotation accepts `int` values"""
        if annotation is int:
            return True
        if typing.get_origin(annotation) in (typing.Union,types.UnionType):
            return int in typing.get_args(annotation)
        return False

    @staticmethod
    def _list_item(annotation) -> type|None:
        """@private Get the item type of a `list` annotation (`None` if not a list)"""
        candidates = typing.get_args(annotation) \
            if typing.get_origin(annotation) in (typing.Union,types.UnionType) else [annotation]
        for candidate in candidates:
            if candidate is list:
                return str
            if typing.get_origin(candidate) is list:
                args = typing.get_args(candidate)
                return args[0] if args else str
        return None

    @classmethod
    def makeargs(cls,**kwargs) -> dict:
        """Get the arguments accepted by this class constructor

        Arguments
        ---------

          - `**kwargs`: candidate arguments (e.g., parsed command line options)

        Returns
        -------

          - `dict`: arguments accepted by the constructor; string values of
            arguments annotated as `int` are converted to `int`, string
            values of arguments annotated as `list` are split on commas
            (e.g., `"NG,WAT"` becomes `["NG","WAT"]`, and items of
            `list[int]` are converted to `int`), and `month` may be given as
            a name or abbreviation (see `eia.base.month_number()`); `None`
            values are omitted for optional arguments whose default is not
            `None`, so the constructor default applies
        """
        annotations = cls.__init__.__annotations__
        defaults = {name:param.default
            for name,param in inspect.signature(cls.__init__).parameters.items()
            if param.default is not inspect.Parameter.empty}
        result = {}
        for name,value in kwargs.items():
            if name not in annotations or name == "return":
                continue
            if value is None and name in defaults and defaults[name] is not None:
                continue
            item = cls._list_item(annotations[name])
            if name == "month" and isinstance(value,str):
                value = month_number(value)
            elif isinstance(value,str) and item is not None:
                items = [x.strip() for x in value.split(",") if x.strip()]
                if item is int:
                    try:
                        items = [int(x) for x in items]
                    except ValueError as err:
                        raise ValueError(f"{name}={value!r} is not a list of integers") from err
                value = items
            elif isinstance(value,str) and cls._accepts_int(annotations[name]):
                try:
                    value = int(value)
                except ValueError as err:
                    raise ValueError(f"{name}={value!r} is not an integer") from err
            result[name] = value
        return result
