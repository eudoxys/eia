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
"""
import os
import shutil
import inspect
import numbers
import datetime as dt
import types
import typing
import pandas as pd
import platformdirs
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

class FormBase(pd.DataFrame):
    """Base class for EIA form data frames"""

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
