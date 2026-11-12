"""Form 861m (small-scale solar) tests"""
import os
import datetime as dt
import pandas as pd
import pytest
import eia.form861m
from eia.form861m import Form861m
import samples

COLUMNS = ["res_mw","com_mw","ind_mw","tot_mw","res_mwh","com_mwh","ind_mwh","tot_mwh"]

@pytest.fixture
def workbook(cache_dir):
    """Cached 2024 workbook containing January and February"""
    pathname = os.path.join(cache_dir,"eia","1","form861m","2024.xlsx")
    os.makedirs(os.path.dirname(pathname))
    samples.form861m_workbook(pathname,2024,[1,2])
    return pathname

def test_month(workbook,no_network): # pylint: disable=unused-argument
    """A month present in the cached workbook"""
    data = Form861m(2024,2)
    assert list(data.index.names) == ["timestamp","state"]
    assert list(data.index) == [(pd.Timestamp("2024-02-01",tz="UTC"),x) for x in ["CA","WA"]]
    assert list(data.columns) == COLUMNS
    assert data.loc[data.index[0]].tolist() == [1,2,3,6,10,20,30,60]

def test_whole_year(workbook,no_network): # pylint: disable=unused-argument
    """month=None returns the whole year"""
    assert len(Form861m(2024)) == 4

def test_raw(workbook,no_network): # pylint: disable=unused-argument
    """raw=True keeps the EIA columns and applies only the period selection"""
    raw = Form861m(2024,2,raw=True)
    assert isinstance(raw.index,pd.RangeIndex)
    assert "index" not in raw.columns
    assert list(raw.columns) == ["year","month","state","status"] + COLUMNS
    assert set(raw["month"]) == {2}

def test_unpublished_month(workbook,no_network): # pylint: disable=unused-argument
    """A month missing from the workbook raises ValueError and keeps the cache file"""
    with pytest.raises(ValueError,match="month=5"):
        Form861m(2024,5)
    assert os.path.exists(workbook)

def test_bad_cache(workbook):
    """A corrupt cached workbook is reported and deleted"""
    with open(workbook,"wb") as fh:
        fh.write(b"not a workbook")
    with pytest.warns(UserWarning), pytest.raises(RuntimeError) as info:
        Form861m(2024,1)
    assert workbook in str(info.value)
    assert not os.path.exists(workbook)

def test_download_fallback(fake_get,tmp_path):
    """Download falls back to the next URL when the first is missing"""
    good = tmp_path / "good.xlsx"
    samples.form861m_workbook(good,2024,[3])
    content = good.read_bytes()
    second = Form861m.FORM861M_URLS[1].format(year=2024)
    calls = fake_get(lambda url,params: (200 if url == second else 404,content))
    assert len(Form861m(2024,3)) == 2
    assert [x[0] for x in calls] == [x.format(year=2024) for x in Form861m.FORM861M_URLS]

def test_memory_cache(workbook,no_network): # pylint: disable=unused-argument
    """The workbook is read once per process"""
    Form861m(2024,1)
    assert 2024 in eia.form861m._cache
    os.unlink(workbook)
    assert len(Form861m(2024,2)) == 2

@pytest.mark.network
@pytest.mark.parametrize("month",range(1,13))
def test_live(month):
    """Form 861m data from EIA"""
    year = dt.datetime.now().year - 2
    raw = Form861m(year,month,raw=True)
    assert len(raw) > 0 and set(raw["month"]) == {month}
    data = Form861m(year,month)
    assert list(data.index.names) == ["timestamp","state"]
    assert list(data.columns) == COLUMNS
    assert {"CA","TX"} <= set(data.index.get_level_values("state"))
    assert data.loc[(slice(None),"CA"),"tot_mw"].iloc[0] > 1000, "CA small-scale solar under 1 GW"
