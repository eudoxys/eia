"""Form 930 tests"""
import datetime as dt
import pandas as pd
import pytest
from eia.form930 import Form930, Form930Fuel, _Form930Base
import samples

@pytest.fixture
def api(fake_get,monkeypatch,respondents): # pylint: disable=unused-argument
    """Serve sample API records, paged, for respondent CAL in August 2020"""
    monkeypatch.setenv("EIA_API_KEY","SECRET")
    monkeypatch.setattr(_Form930Base,"PAGE_LENGTH",1000)
    records = {
        "region-data": samples.form930_records(2020,8,"CAL","type",["D","NG","TI"]),
        "fuel-type-data": samples.form930_records(2020,8,"CAL","fueltype",["NG","WAT"]),
        }
    def handler(url,params):
        params = dict(params)
        data = records["fuel-type-data" if "fuel-type-data" in url else "region-data"]
        offset = params["offset"]
        page = data[offset:offset+params["length"]]
        return (200,b"",{"response":{"total":str(len(data)),"data":page}})
    return fake_get(handler)

def test_region_data(api):
    """Hourly demand, generation, and interchange from paged API responses"""
    data = Form930(2020,8,respondent="CAL")
    assert len(api) == 3, f"expected 3 pages, got {len(api)}"
    params = dict(api[0][1])
    assert params["api_key"] == "SECRET" and params["facets[respondent][]"] == "CAL"
    assert params["start"] == "2020-08-01T01" and params["end"] == "2020-09-01T00"
    assert [dict(x[1])["offset"] for x in api] == [0,1000,2000]
    assert list(data.index.names) == ["timestamp"] and len(data) == 744
    assert data.index[0] == pd.Timestamp("2020-08-01",tz="UTC"), "hour-ending not shifted"
    assert list(data.columns) == ["load_mw","generation_mw","interchange_mw"]
    assert (data == 1.0).all().all()

    # second call uses the cache
    api.clear()
    assert Form930(2020,8,respondent="CAL").equals(data)
    assert not api, "cached data was downloaded again"

def test_fuel_type_data(api):
    """Hourly generation by fuel, with fuels filter"""
    data = Form930Fuel(2020,8,respondent="CAL")
    assert list(data.columns) == ["ng_mw","wat_mw"] and len(data) == 744
    assert list(Form930Fuel(2020,8,respondent="CAL",fuels="wat").columns) == ["wat_mw"]
    raw = Form930Fuel(2020,8,respondent="CAL",fuels="wat",raw=True)
    assert len(raw) == 744*2, "raw applied the fuels filter"
    assert len(api) == 2, "fuel data downloaded more than once"

def test_reference_data(fake_get):
    """Reference data are cached, refreshed for unknown codes, and on request"""
    content = {"data":samples.form930_reference("CISO")}
    calls = fake_get(lambda url,params: (200,content["data"]))
    assert _Form930Base.respondents() == ["CAL","CISO"]
    assert len(calls) == 1

    # a new process reads the disk cache without network access
    _Form930Base.references.clear()
    _Form930Base._references_refreshed = False
    Form930._check_respondent("region","CISO")
    assert len(calls) == 1, "cached reference data was downloaded again"

    # an unknown code refreshes the cache once
    content["data"] = samples.form930_reference("CISO","NEWB")
    Form930._check_respondent("region","NEWB")
    assert len(calls) == 2, "unknown code did not refresh reference data"
    with pytest.raises(ValueError):
        Form930._check_respondent("region","NOPE")
    assert len(calls) == 2, "invalid code refreshed reference data twice"

    # refresh always downloads
    _Form930Base.respondents(refresh=True)
    assert len(calls) == 3, "refresh did not download reference data"

@pytest.mark.network
@pytest.mark.parametrize("year,month",[(2018,1),(2018,7)])
def test_live(api_key,year,month): # pylint: disable=unused-argument
    """Form 930 data from the EIA API"""
    data = Form930(year,month,respondent="CISO")
    assert len(data) == 744
    assert data.index[0] == dt.datetime(year,month,1,tzinfo=dt.timezone.utc)
    assert list(data.columns) == ["load_mw","generation_mw","interchange_mw"]

@pytest.mark.network
def test_live_fuel(api_key): # pylint: disable=unused-argument
    """Form 930 fuel mix totals match net generation"""
    data = Form930(2018,7,respondent="CISO")
    fuel = Form930Fuel(2018,7,respondent="CISO")
    assert len(fuel) == 744
    assert "sun_mw" in fuel.columns
    error = (fuel.sum(axis=1,min_count=1) - data.generation_mw).abs().median()
    assert error < 0.01*data.generation_mw.median(), f"fuel total differs from net generation by {error=}"
