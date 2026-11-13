"""Form 860m tests"""
import os
import datetime as dt
import pandas as pd
import pytest
from eia.form860m import Form860m
import samples

ROWS = [
    {"Entity ID":1,"Entity Name":"Owner","Plant ID":10,"Plant Name":"Plant","Plant State":"CA",
        "Generator ID":"G2","Balancing Authority Code":"CISO","Nameplate Capacity (MW)":5.0,
        "Energy Source Code":"SUN","Prime Mover Code":"PV","Operating Year":2019,"Latitude":"x"},
    {"Entity ID":1,"Entity Name":"Owner","Plant ID":10,"Plant Name":"Plant","Plant State":"CA",
        "Generator ID":"G1","Balancing Authority Code":"CISO","Nameplate Capacity (MW)":7.5,
        "Energy Source Code":"NG","Prime Mover Code":"GT","Operating Year":2001,"Latitude":36.5},
    ]

@pytest.mark.parametrize("year,month",[(2020,8),(2021,3)])
def test_workbook(fake_get,year,month):
    """A downloaded workbook is parsed, normalised, and cached"""
    month_name = dt.date(year,month,1).strftime("%B").lower()
    content = samples.form860m_workbook(year,month,ROWS)
    calls = fake_get(lambda url,params: (200,content))
    data = Form860m(year,month)
    assert [x[0] for x in calls] == ["https://www.eia.gov/electricity/data/eia860m/"
        f"archive/xls/{month_name}_generator{year}.xlsx"]
    assert list(data.index.names) == ["timestamp","plant","generator"]
    assert list(data.index) == [(pd.Timestamp(year=year,month=month,day=1,tz="UTC"),10,x)
        for x in ["G1","G2"]], "footnote row kept or not sorted"
    columns = [y[0] for x,y in Form860m.COLUMNS.items() if y[0] not in ("plant","generator")]
    assert sorted(data.columns) == sorted(columns)
    assert data["nameplate_mw"].tolist() == [7.5,5.0]
    assert data["fuel"].tolist() == ["NG","SUN"]
    assert data["operating_year"].tolist() == [2001,2019]
    assert data["summer_mw"].isna().all(), "missing float column is not NaN"
    assert (data["planned_derate_year"] == 0).all(), "missing integer column is not 0"
    assert (data["county"] == "").all(), "missing string column is not empty"
    assert pd.isna(data["latitude"].iloc[1]), "non-numeric float value is not NaN"
    assert data.index.get_level_values("plant").dtype == "int64"
    assert data["owner"].dtype == "int64" and data["operating_year"].dtype == "int64"
    assert data["nameplate_mw"].dtype == "float64" and data["latitude"].dtype == "float64"

    # second call reads the subset cache
    calls.clear()
    assert Form860m(year,month).equals(data)
    assert not calls, "cached workbook was downloaded again"

def test_raw(fake_get):
    """raw=True returns the worksheet with EIA column names as strings"""
    fake_get(lambda url,params: (200,samples.form860m_workbook(2020,8,ROWS)))
    raw = Form860m(2020,8,raw=True)
    assert isinstance(raw.index,pd.RangeIndex)
    assert list(raw.columns) == list(ROWS[0])
    assert raw["Plant Name"].tolist() == ["Plant","Plant"]
    assert raw["Plant ID"].tolist() == ["10","10"], "integer column is float text (#47)"
    assert raw["Entity ID"].tolist() == ["1","1"]
    assert raw["Operating Year"].tolist() == ["2019","2001"]
    assert raw["Nameplate Capacity (MW)"].tolist() == ["5","7.5"]
    assert raw["Latitude"].tolist() == ["x","36.5"]

    # a second call reads the subset cache and returns the same text
    assert Form860m(2020,8,raw=True).equals(raw)

def test_subset(fake_get):
    """subset selects the worksheet"""
    fake_get(lambda url,params: (200,samples.form860m_workbook(2020,8,ROWS,subset="Planned")))
    assert len(Form860m(2020,8,subset="Planned")) == 2

def test_bad_cache(cache_dir):
    """A corrupt cached workbook is reported, named, and deleted"""
    cachefile = os.path.join(cache_dir,"eia",str(Form860m.CACHE_VERSION),"form860m","2020-08.xlsx")
    os.makedirs(os.path.dirname(cachefile))
    with open(cachefile,"wb") as fh:
        fh.write(b"not a workbook")
    with pytest.warns(UserWarning,match=cachefile.replace("\\","\\\\")), \
            pytest.raises(RuntimeError) as info:
        Form860m(2020,8)
    assert cachefile in str(info.value)
    assert "august_generator2020.xlsx" in str(info.value)
    assert not os.path.exists(cachefile)

@pytest.mark.network
@pytest.mark.parametrize("month",range(1,13))
def test_live(month):
    """Form 860m data from EIA"""
    year = dt.datetime.now().year - 2
    raw = Form860m(year,month,raw=True)
    assert len(raw) > 0 and "Plant ID" in raw.columns
    data = Form860m(year,month)
    assert len(data) > 0
    assert list(data.index.names) == ["timestamp","plant","generator"]
    assert {"nameplate_mw","state","ba","fuel","pm","operating_year"} <= set(data.columns)
    assert data["nameplate_mw"].sum() > 1e5, "US operating capacity is under 100 GW"
