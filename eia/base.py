"""Common base class for EIA form data frames

All form classes derive from `eia.base.FormBase`, which provides the
`makeargs()` method the command line tool uses to map its options to the
form constructor's arguments.
"""
import types
import typing
import pandas as pd

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

    @classmethod
    def makeargs(cls,**kwargs) -> dict:
        """Get the arguments accepted by this class constructor

        Arguments
        ---------

          - `**kwargs`: candidate arguments (e.g., parsed command line options)

        Returns
        -------

          - `dict`: arguments accepted by the constructor; string values of
            arguments annotated as `int` are converted to `int`
        """
        annotations = cls.__init__.__annotations__
        result = {}
        for name,value in kwargs.items():
            if name not in annotations or name == "return":
                continue
            if isinstance(value,str) and cls._accepts_int(annotations[name]):
                try:
                    value = int(value)
                except ValueError as err:
                    raise ValueError(f"{name}={value!r} is not an integer") from err
            result[name] = value
        return result
