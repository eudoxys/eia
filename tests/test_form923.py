"""Form 923 tests"""
import datetime as dt
import pandas as pd
import pytest
from eia.form923 import Form923
import samples

@pytest.fixture
def zip_download(fake_get):
    """Serve the sample 2020 zip file from the second (recent years) URL"""
    content = samples.form923_zip(2020)
    second = Form923.FORM923_URLS[1].format(year=2020)
    return fake_get(lambda url,params: (200,content) if url == second else (404,b""))

def test_zip(zip_download):
    """The zip file is downloaded from the first URL that exists and parsed"""
    data = Form923(2020,8)
    assert [x[0] for x in zip_download] == [x.format(year=2020) for x in Form923.FORM923_URLS]
    assert list(data.index.names) == ["timestamp","state","ba","fuel"]
    assert list(data.columns) == ["gen_mwh"]
    august = pd.Timestamp("2020-08-01",tz="UTC")
    assert data.loc[(august,"CA","CISO","WAT"),"gen_mwh"] == 10
    assert data.loc[(august,"CA","CISO","NG"),"gen_mwh"] == 20

    # second call uses the cache
    zip_download.clear()
    assert len(Form923(2020)) == 24
    assert not zip_download, "cached data was downloaded again"

def test_plants(zip_download): # pylint: disable=unused-argument
    """by="plant" keeps plant and prime mover, and plants filters"""
    data = Form923(2020,8,by="plant",plants=6099)
    assert list(data.index.names) == ["timestamp","state","ba","plant","pm","fuel"]
    assert data.index[0][3:] == (6099,"HY","WAT")
    assert data["gen_mwh"].tolist() == [10]

def test_filters(zip_download): # pylint: disable=unused-argument
    """fuels filter is applied"""
    data = Form923(2020,8,fuels="NG")
    assert data.index.get_level_values("fuel").tolist() == ["NG"]

def test_raw(zip_download): # pylint: disable=unused-argument
    """raw=True keeps the EIA headers and only the requested month"""
    raw = Form923(2020,8,raw=True)
    assert isinstance(raw.index,pd.RangeIndex)
    assert "Netgen\nAugust" in raw.columns and "Netgen\nJuly" not in raw.columns

def test_missing(fake_get):
    """No zip file at any URL raises RuntimeError"""
    fake_get(lambda url,params: (404,b""))
    with pytest.raises(RuntimeError,match="year=2020"):
        Form923(2020,8)

@pytest.mark.network
def test_live():
    """Form 923 data from EIA by BA and by plant"""
    year = dt.datetime.now().year - 2
    data = Form923(year,8)
    assert len(data) > 0
    assert list(data.index.names) == ["timestamp","state","ba","fuel"]
    plants = Form923(year,8,by="plant")
    assert len(plants) > 0
    assert list(plants.index.names) == ["timestamp","state","ba","plant","pm","fuel"]
    assert abs(plants["gen_mwh"].sum() - data["gen_mwh"].sum()) < 1, "plant total does not match BA total"
