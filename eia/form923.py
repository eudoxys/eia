"""Access Form 923 generation data

Example
-------

The following code

    from eia import Form923
    print(Form923(2020,8,fuels=["NG","WAT"],bas="CISO"))

outputs

                                                   gen_mwh
    timestamp                 state ba   fuel
    2020-08-01 00:00:00+00:00 CA    CISO NG    9013312.798
                                         WAT   1773947.542
                              NV    CISO NG     153002.000

Plant-level data is returned when `by="plant"`, e.g.,

    from eia import Form923
    print(Form923(2020,8,states="CA",fuels="WAT",by="plant"))

returns one row per plant, prime mover and fuel, indexed by `timestamp`,
`state`, `ba`, `plant`, `pm`, and `fuel`.

Caveats
-------

- Net generation can be negative (e.g., pumped storage, batteries, and plants
  whose station use exceeds output). `nonzero=True` removes only zero and
  missing values, not negative values.

- Plant id `99999` rows are EIA's "State-Fuel Level Increment" estimates for
  plants not surveyed monthly. They are included by default and can be
  excluded with `increments=False`.

See also
--------

- [EIA Form 923 Data Download](https://www.eia.gov/electricity/data/eia923/)
"""

import datetime as dt
from io import BytesIO
from warnings import warn
from zipfile import ZipFile
import calendar

import requests
import pandas as pd

from cache import Cache

class Form923(pd.DataFrame):
    """Form923 DataFrame

    Index
    -----
    - `timestamp`: month and year of record
    - `state`: state to which record applies
    - `ba`: balancing authority to which record applies
    - `plant`: EIA plant id (only when `by="plant"`)
    - `pm`: EIA prime mover code (only when `by="plant"`)
    - `fuel`: fuel type to which record applies

    Columns
    -------
    - `gen_mwh`: total net energy production of record in MWh
    """
    FORM923_URLS = [
        "https://www.eia.gov/electricity/data/eia923/archive/xls/f923_{year}.zip",
        "https://www.eia.gov/electricity/data/eia923/xls/f923_{year}.zip",
        ]
    """URLs to try for Form 923 zip files (archived years, then recent years)"""

    FORM923_URL = FORM923_URLS[0]
    """@private retained for backward compatibility"""

    FILENAME = "EIA923_Schedules_2_3_4_5_M_12_{year}"
    """Prefix of the generation and fuel workbook in the zip file"""

    PLANT_INCREMENT = 99999
    """Plant id EIA uses for state-fuel level increment estimates"""

    COLUMNS = {
        "plant id": "PLANT",
        "plant name": "NAME",
        "plant state": "STATE",
        "balancing authority code": "BA",
        "reported prime mover": "PM",
        "reported fuel type code": "FUEL",
        }
    """@private normalized raw header -> cache column name"""

    INDEX = {
        "ba": ["STATE","BA","FUEL"],
        "plant": ["STATE","BA","PLANT","PM","FUEL"],
        }
    """@private grouping columns by aggregation level"""

    def __init__(self,
        year:int,
        month:int|None=None,
        states:list[str]|None=None,
        bas:list[str]|None=None,
        fuels:list[str]|None=None,
        *,
        by:str="ba",
        plants:list[int]|None=None,
        increments:bool=True,
        precision:int=3,
        refresh:bool=False,
        nonzero:bool=True,
        ):
        """Construct Form923 data frame

        Arguments
        ---------
        - `year`: year of query
        - `month`: month to include (`None` returns entire year)
        - `states`: states to include (`None` returns all states found)
        - `bas`: balancing authorities to include (`None` returns all BAs found)
        - `fuels`: fuel types to include (`None` returns all fuel types found)
        - `by`: aggregation level, `"ba"` (default) or `"plant"`
        - `plants`: plant ids to include (`None` returns all plants found)
        - `increments`: include state-fuel level increment rows (plant `99999`)
        - `precision`: precision of cached data
        - `refresh`: force cache refresh
        - `nonzero`: drop zero and missing values (negative values are kept)
        """
        # pylint: disable=too-many-arguments,too-many-locals,too-many-branches

        # check arguments
        assert 2008 <= year <= dt.datetime.now().year, f"{year=} is not valid"
        if year >= dt.datetime.now().year-1:
            warn(f"{year=} may not be finalized yet")
        assert by in self.INDEX, f"{by=} is not valid (must be one of {list(self.INDEX)})"
        assert month is None or 1 <= month <= 12, f"{month=} is not valid"

        # load plant-level data (cached)
        df = self._load(year,precision=precision,refresh=refresh)

        # select plant-level rows before aggregating
        if not increments:
            df = df.loc[df["PLANT"]!=self.PLANT_INCREMENT]
        if plants is not None:
            if isinstance(plants,int):
                plants = [plants]
            df = df.loc[df["PLANT"].isin(plants)]

        # aggregate to requested level
        months = [f"{year}-{month:02d}"] if month else [f"{year}-{x:02d}" for x in range(1,13)]
        index = self.INDEX[by]
        df = df.groupby(index,dropna=False)[months].sum(min_count=1).reset_index().melt(
            id_vars=index,
            value_vars=months,
            var_name="month",
            value_name="gen_mwh",
            ).rename({x:x.lower() for x in index},axis=1)

        # select non-zero values if specified
        if nonzero:
            df = df[(df["gen_mwh"]!=0) & df["gen_mwh"].notna()]

        # select states, balancing authorities, and fuels
        for column,values in {"state":states,"ba":bas,"fuel":fuels}.items():
            if values is not None:
                if isinstance(values,str):
                    values = [values]
                df = df.loc[df[column].isin(values)]

        # make date/time index
        df = df.assign(timestamp=pd.DatetimeIndex([f"{x}-01 00:00:00+0000" for x in df["month"]]))

        # construct final data frame
        super().__init__(df.set_index(["timestamp"]+[x.lower() for x in index])[["gen_mwh"]])

    @classmethod
    def _load(cls,year:int,precision:int=3,refresh:bool=False) -> pd.DataFrame:
        """@private Load plant-level monthly net generation for a year

        Returns a data frame with columns `PLANT`, `NAME`, `STATE`, `BA`, `PM`,
        `FUEL`, and one column per month named `YYYY-MM`.
        """
        cache = Cache(
            package="eia",
            version=1,
            path=["form923",f"{year}.csv.gz"],
            )
        if cache.exists() and not refresh:
            try:
                return pd.read_csv(cache.pathname,
                    dtype={"STATE":str,"BA":str,"PM":str,"FUEL":str,"NAME":str},
                    keep_default_na=False,
                    na_values=[""],
                    )
            except Exception as err: # pylint: disable=broad-exception-caught
                warn(f"{cache.pathname=} {err=} - regenerating cache")
                cache.delete()

        # download from EIA
        content = None
        for url in [x.format(year=year) for x in cls.FORM923_URLS]:
            req = requests.get(url,timeout=300)
            if req.status_code == 200:
                content = req.content
                break
        if content is None:
            raise RuntimeError(f"{year=} not found at any of {cls.FORM923_URLS}")

        # extract data
        with ZipFile(BytesIO(content),"r") as fh:
            prefix = cls.FILENAME.format(year=year)
            names = [x for x in fh.namelist() if x.startswith(prefix) and x.endswith(".xlsx")]
            if not names:
                raise RuntimeError(f"no file starting with {prefix=} found for {year=}")
            df = pd.read_excel(fh.open(names[0]),
                skiprows=5,
                na_values=["."],
                dtype={"Plant State":str},
                )

        # normalize headers (e.g., "Reported\\nFuel Type Code" -> "reported fuel type code")
        df.columns = [" ".join(str(x).split()).lower() for x in df.columns]
        months = {f"netgen {calendar.month_name[x].lower()}":f"{year}-{x:02d}" for x in range(1,13)}
        missing = [x for x in list(cls.COLUMNS)+list(months) if x not in df.columns]
        if missing:
            raise RuntimeError(f"{year=} workbook is missing columns {missing}")
        df = df[list(cls.COLUMNS)+list(months)].rename(cls.COLUMNS|months,axis=1)
        df["PLANT"] = df["PLANT"].astype(int)
        df[list(months.values())] = df[list(months.values())].astype(float).round(precision)

        # save data to cache
        df.to_csv(cache.pathname,index=False,header=True,compression="gzip")
        return df

if __name__ == '__main__':

    pd.options.display.width = None
    pd.options.display.max_columns = None

    print(Form923(2020,8,fuels=["NG","WAT"],bas="CISO"))
    print(Form923(2020,8,states="CA",fuels="WAT",by="plant"))
