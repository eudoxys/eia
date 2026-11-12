"""Common base class for EIA form data frames

All form classes derive from `eia.base.FormBase`, which provides the
`makeargs()` method the command line tool uses to map its options to the
form constructor's arguments.
"""
import inspect
import types
import typing
import pandas as pd

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
    if not isinstance(month,int) or isinstance(month,bool) or not 1 <= month <= 12:
        raise ValueError(f"{month=} is not a valid month")
    return month

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
