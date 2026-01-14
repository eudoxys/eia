"""Access Form930 data for NERC regions

Example
-------

To get the August 2020 California load, generation, and interchange use the following

    from eia import Form930
    Form930("CAL","")

Caveat
------

  - You must register with the EIA Open Data API
    at https://www.eia.gov/opendata/register.php to obtain an API key. The API
    key must be stored in `~/.eia/api_key`.

References
----------

  - https://www.eia.gov/electricity/gridmonitor/about
"""
import sys
import os
import datetime as dt
import json
import pandas as pd
import requests

from cache import Cache

class Form930(pd.DataFrame):
    """Form930 data frame

    Columns
    -------

      - `timestamp`: date and time of record (index)

      - `load_MW`: load value

      - `generation_MW`: net generation value

      - `interchange_MW`: exports value
    """

    FORM930_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/?frequency=hourly&data[0]=value&facets[respondent][]={region}&facets[type][]=D&facets[type][]=NG&facets[type][]=TI&start={start}-01T00&end={end}-01T00&sort[0][column]=period&sort[0][direction]=desc&offset=0&length=5000&api_key={apikey}"
    """URL for Form 930 API queries"""

    REFERENCE_URL = "https://www.eia.gov/electricity/930-content/EIA930_Reference_Tables.xlsx"
    """URL for Form 930 reference sheets"""
    
    references = {}
    """@private runtime cache of reference data"""

    TIMEZONES = { 
        # do not use pytz.timezone() because source data does not use DST
        "Eastern":-5,
        "Central":-6,
        "Mountain":-7,
        "Arizona":-7,
        "Pacific":-8,
    }
    """Timezone offsets for regions"""

    def __init__(self,
        region:str,
        year:int,
        month:int|None=None,
        ):
        """Access Form 930 data for a region

        Arguments
        ---------

          - `region`: region name (see `eia.Form930.reference_data("Regions")`)

          - `year`: year of data

          - `month`: month of data (`None` accesses entire year)
        """
        with open(os.path.join(os.environ["HOME"],".eia","api_key"),"r") as fh:
            apikey = fh.read().strip()
        
        region_info = Form930.reference_data("Regions").set_index("Region/Country Code")
        assert region in region_info.index, f"{region=} is not valid"

        assert isinstance(year,int) and 2018 < year < dt.datetime.now().year, \
            f"{year=} is invalid"
        
        if month is None:
            months = list(range(1,13))
        else:
            assert isinstance(month,int) and 1 <= month <= 12, f"{month=} is invalid"
            months = [month]

        tz = self.TIMEZONES[region_info.loc[region].to_frame().T["Time Zone"].values[0]]

        result = []
        for month in months:
            cache = Cache(
                package="eia",
                version=0,
                path=["form930","region",f"{region}-{year}-{month:02d}.csv.gz"],
                )
            if cache.exists():
                try:
                    data = pd.read_csv(cache.pathname)
                except:
                    data = None
            else:
                data = None
            if data is None:
                start = f"{year}-{month:02d}"
                end = f"{year+1 if month == 12 else year}-{month+1 if month < 12 else 1:02d}"
                fmt = "%Y-%m-%dT%H"
                url = self.FORM930_URL.format(
                    region=region,
                    start=start,
                    end=end,
                    apikey=apikey,
                    )
                req = requests.get(url)
                if req.status_code != 200:
                    raise RuntimeError(f"{url} --> HTTP {req.status_code}")
                data = pd.DataFrame(json.loads(req.text)["response"]["data"])
                data.to_csv(cache.pathname,
                    index=False,
                    header=True,
                    compression="gzip" if cache.pathname.endswith(".gz") else None)
            
            data.drop(
                ["respondent","respondent-name","type-name","value-units"],
                inplace=True,
                axis=1,
                )
            data.period = pd.DatetimeIndex(data.period,tz=tz*3600).tz_convert("UTC")
            data.set_index(["period","type"],inplace=True)
            data = data.unstack().sort_index().iloc[:-1].reset_index()
            data.columns = ["timestamp","load_MW","generation_MW","interchange_MW"]
            for column in [x for x in data.columns if x.endswith("_MW")]:
                data[column] = data[column].astype(float)
            result.append(data)

        super().__init__(pd.concat(result))

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
        if sheet in Form930.references:
            return Form930.references[sheet]

        cache = Cache(package="eia",version=0,path=["reference",f"{sheet}.csv"])
        if cache.exists():
            try:
                data = pd.read_csv(cache.pathname)
            except:
                data = None
        else:
            data = None
        if data is None:
            data = pd.read_excel(
                Form930.REFERENCE_URL,
                sheet_name=sheet,
                )
            data.to_csv(cache.pathname,index=False,header=True)

        Form930.references[sheet] = data
        return data

if __name__ == "__main__":


    import matplotlib.pyplot as plt
    for region in ["CAL","NW","SW"]:
        test = Form930(region,2025).set_index("timestamp")
        test.columns = ["Load","Generation","Exports"]
        # test["Error"] = test.Load + test.Exports - test.Generation 
        (test/1000).plot(grid=True,ylabel="Power (GW)",xlabel="Date/Time",title=region)
        plt.show()