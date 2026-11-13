"""Small synthetic EIA data files used by the offline tests

Each function writes (or returns) a minimal copy of an EIA source file with
the same layout as the real one, so that the parsing code can be tested
without network access.
"""
import io
import os
import zipfile
import datetime as dt
import pandas as pd
from eia.form860m import Form860m

def form860m_workbook(year:int,month:int,rows:list[dict],subset:str="Operating") -> bytes:
    """Form 860m generator workbook with one subset sheet

    Rows are dicts keyed by EIA column names. Workbooks before November 2020
    have one title row above the header; later workbooks have two.
    """
    skip = 2 if year > 2020 or (year == 2020 and month > 10) else 1
    columns = list(dict.fromkeys(x for row in rows for x in row))
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer,engine="openpyxl") as writer:
        pd.DataFrame([["title"]+[""]*(len(columns)-1)]*skip + [columns]
                + [[row.get(x,"") for x in columns] for row in rows]
                + [["footnote"]+[""]*(len(columns)-1)]) \
            .to_excel(writer,sheet_name=subset,index=False,header=False)
    return buffer.getvalue()

def form861m_workbook(pathname:str,year:int,months:list[int]):
    """Write a Form 861m small-scale solar workbook containing only the given months"""
    rows = [["header"]*12]*4 + [[year,month,state,"E",1,2,3,6,10,20,30,60]
        for month in months for state in ["CA","WA"]]
    pd.DataFrame(rows).to_excel(pathname,
        sheet_name="Monthly Totals- States",
        index=False,
        header=False,
        )

def form861msales_workbook(rows:list[tuple]) -> bytes:
    """Form 861m sales and revenue workbook (three header rows)

    Rows are `(year,month,state,status,revenue,sales,customers,price)` for the
    residential sector; a footnote row with no status is appended.
    """
    header = [
        ["","","","","RESIDENTIAL","RESIDENTIAL","RESIDENTIAL","RESIDENTIAL"],
        ["","","","","Revenue","Sales","Customers","Price"],
        ["Year","Month","State","Data Status","Thousand Dollars","Megawatthours","Count","Cents/kWh"],
        ]
    footnote = [["Source: EIA",None,None,None,None,None,None,None]]
    buffer = io.BytesIO()
    pd.DataFrame(header + [list(x) for x in rows] + footnote) \
        .to_excel(buffer,index=False,header=False,engine="openpyxl")
    return buffer.getvalue()

FORM923_ROWS = [[6099,"Hydro","CA","CISO","HY","WAT"],[286,"Gas","CA","CISO","CT","NG"]]
"""Plants in the sample Form 923 data (net generation 10 and 20 MWh per month)"""

def form923_table(year:int) -> pd.DataFrame:
    """Form 923 generation and fuel worksheet with the original EIA headers"""
    months = [dt.date(year,x,1).strftime("%B") for x in range(1,13)]
    columns = ["Plant Id","Plant Name","Plant State","Balancing\nAuthority Code",
        "Reported\nPrime Mover","Reported\nFuel Type Code"] \
        + [f"Quantity\n{x}" for x in months] + [f"Netgen\n{x}" for x in months]
    return pd.DataFrame([x + ["1"]*12 + [str(10*(n+1))]*12 for n,x in enumerate(FORM923_ROWS)],
        columns=columns)

def form923_zip(year:int) -> bytes:
    """Form 923 zip file containing the generation and fuel workbook"""
    table = form923_table(year)
    sheet = io.BytesIO()
    pd.DataFrame([["title"]+[""]*(len(table.columns)-1)]*5 + [list(table.columns)]
            + table.values.tolist()) \
        .to_excel(sheet,index=False,header=False,engine="openpyxl")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer,"w") as fh:
        fh.writestr(f"EIA923_Schedules_2_3_4_5_M_12_{year}_Final.xlsx",sheet.getvalue())
        fh.writestr("readme.txt","other file")
    return buffer.getvalue()

def form930_records(year:int,month:int,respondent:str,column:str,codes:list[str]) -> list[dict]:
    """Form 930 API records for one month (UTC hour-ending periods)"""
    start = pd.Timestamp(year=year,month=month,day=1,hour=1)
    hours = pd.date_range(start,start+pd.DateOffset(months=1)-pd.Timedelta(hours=1),freq="h")
    return [{"period":x.strftime("%Y-%m-%dT%H"),"respondent":respondent,column:c,"value":1.0}
        for x in hours for c in codes]

def form930_reference(*codes:str) -> bytes:
    """Form 930 reference workbook containing the given BA codes"""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer,engine="openpyxl") as writer:
        pd.DataFrame({"BA Code":list(codes)}).to_excel(writer,sheet_name="BAs",index=False)
        pd.DataFrame({"Region/Country Code":["CAL"]}).to_excel(writer,sheet_name="Regions",index=False)
    return buffer.getvalue()

def sales_table(years=(2021,2022),months=range(1,13),states=("CA","WA")) -> pd.DataFrame:
    """Form 861m sales table as cached in memory by `eia.form861msales`"""
    return pd.DataFrame([{"year":y,"month":m,"state":s,"status":"Final","tot_energy_mwh":1.0}
        for y in years for m in months for s in states])

def write_cache_files(cachedir:str):
    """Write cache files for August 2020 for every form under `cachedir`"""
    base = os.path.join(cachedir,"eia","1")

    # Form 860m: workbook placeholder and subset cache with EIA headers
    form860m = os.path.join(cachedir,"eia",str(Form860m.CACHE_VERSION),"form860m")
    os.makedirs(form860m)
    with open(os.path.join(form860m,"2020-08.xlsx"),"wb") as fh:
        fh.write(b"placeholder")
    pd.DataFrame({
        "Entity ID":[1,1],"Entity Name":["Owner","Owner"],"Plant ID":[10,10],
        "Plant Name":["Plant","Plant"],"Plant State":["CA","CA"],"Generator ID":["G2","G1"],
        "Balancing Authority Code":["CISO","CISO"],"Nameplate Capacity (MW)":[5.0,7.5],
        "Energy Source Code":["SUN","NG"],"Prime Mover Code":["PV","GT"],"Operating Year":[2019,2001],
        }).to_csv(os.path.join(form860m,"2020-08-operating.csv.gz"),index=False,compression="gzip")

    # Form 861m: workbook with two months
    os.makedirs(os.path.join(base,"form861m"))
    form861m_workbook(os.path.join(base,"form861m","2020.xlsx"),2020,[7,8])

    # Form 923: raw worksheet cache with the original EIA headers
    os.makedirs(os.path.join(base,"form923"))
    form923_table(2020).to_csv(os.path.join(base,"form923","2020-raw.csv.gz"),
        index=False,compression="gzip")

    # Form 930: API records cache
    for route,column,codes in [("region-data","type",["D","NG","TI"]),
            ("fuel-type-data","fueltype",["NG","WAT"])]:
        os.makedirs(os.path.join(base,"form930",route))
        pd.DataFrame(form930_records(2020,8,"CAL",column,codes)).to_csv(
            os.path.join(base,"form930",route,"CAL-2020-08.csv.gz"),index=False,compression="gzip")
