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
    assert data.notna().all(axis=1).mean() > 0.99, "API returned no or few values"
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

@pytest.fixture
def bulk(fake_get,monkeypatch):
    """Serve a six-month balance file for July-December 2018 (no API key)"""
    monkeypatch.delenv("EIA_API_KEY",raising=False)
    monkeypatch.setattr(_Form930Base,"respondents",
        staticmethod(lambda refresh=False: ["BANC","CAL","CISO","US48"]))
    monkeypatch.setattr(Form930Fuel,"_bulk",{})
    monkeypatch.setattr(Form930Fuel,"_bulk_refreshed",set())
    content = {
        "EIA930_BALANCE_2018_Jul_Dec.csv": samples.form930_balance(2018,"Jul_Dec",
            {"CISO":"CAL","BANC":"CAL"}),
        "EIA930_BALANCE_2018_Jan_Jun.csv": samples.form930_balance(2018,"Jan_Jun",
            {"CISO":"CAL","BANC":"CAL"},fuels=False),
        }
    def handler(url,params):
        assert "api.eia.gov" not in url, "API used for a month before 2019"
        return (200,content[url.rsplit("/",1)[1]])
    return fake_get(handler)

def test_fuel_six_month_file(bulk):
    """July-December 2018 energy source data from the six-month file"""
    data = Form930Fuel(2018,8,respondent="CISO")
    assert list(data.columns) == ["col_mw","sun_mw"], "reported columns only"
    assert len(data) == 744 and data.index.name == "timestamp"
    assert data.index[0] == pd.Timestamp("2018-08-01",tz="UTC")
    assert (data["col_mw"] == 1000).all(), "thousands separator not parsed"
    assert (data["sun_mw"] == (data.index.hour+1) % 24).all(), "not converted to hour-beginning"
    assert [x[0].rsplit("/",1)[1] for x in bulk] == ["EIA930_BALANCE_2018_Jul_Dec.csv"]

def test_fuel_six_month_file_cached(bulk,cache_dir):
    """The six-month file is downloaded once and its energy source data cached"""
    Form930Fuel(2018,8,respondent="CISO")
    Form930Fuel(2018,9,respondent="BANC")
    assert len(bulk) == 1
    Form930Fuel._bulk.clear()
    assert (Form930Fuel(2018,10,respondent="CISO")["col_mw"] == 1000).all()
    assert len(bulk) == 1, "cached six-month data was downloaded again"
    assert list(cache_dir.rglob("EIA930_BALANCE_2018_Jul_Dec.csv.gz"))
    Form930Fuel(2018,10,respondent="CISO",refresh=True)
    assert len(bulk) == 1, "already downloaded by this process"
    Form930Fuel._bulk_refreshed.clear()  # as in a new process
    Form930Fuel(2018,10,respondent="CISO",refresh=True)
    Form930Fuel(2018,11,respondent="CISO",refresh=True)
    assert len(bulk) == 2, "refresh must download the six-month file once per process"

def test_fuel_six_month_file_region(bulk):
    """A region is the sum of its balancing authorities"""
    assert (Form930Fuel(2018,8,respondent="CAL")["col_mw"] == 1001).all()
    assert (Form930Fuel(2018,8,respondent="US48")["col_mw"] == 1001).all()

def test_fuel_six_month_file_year(bulk):
    """2018 starts in July; earlier months are not available"""
    data = Form930Fuel(2018,respondent="CISO")
    assert data.index[0] == pd.Timestamp("2018-07-01",tz="UTC")
    assert data.index[-1] == pd.Timestamp("2018-12-31 23:00",tz="UTC")
    with pytest.raises(ValueError):
        Form930Fuel(2018,6,respondent="CISO")
    with pytest.raises(ValueError):
        Form930Fuel(2017,respondent="CISO")

def test_fuel_six_month_file_raw(bulk):
    """Raw six-month file data are API-style records"""
    raw = Form930Fuel(2018,8,respondent="CISO",raw=True)
    assert list(raw.columns) == ["period","respondent","fueltype","value"]
    assert raw["period"].iloc[0] == "2018-08-01T01" and set(raw["fueltype"]) == {"COL","SUN"}

def test_fuel_six_month_file_missing_columns():
    """A six-month file without the expected columns is an error"""
    with pytest.raises(RuntimeError):
        Form930Fuel._parse_bulk(b"a,b\n1,2\n")

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
@pytest.mark.parametrize("year,month",[(2019,1),(2019,7)])
def test_live(api_key,year,month): # pylint: disable=unused-argument
    """Form 930 data from the EIA API"""
    data = Form930(year,month,respondent="CISO")
    assert len(data) == 744
    assert data.index[0] == dt.datetime(year,month,1,tzinfo=dt.timezone.utc)
    assert list(data.columns) == ["load_mw","generation_mw","interchange_mw"]
    assert data.notna().all(axis=1).mean() > 0.99, "API returned no or few values"

@pytest.mark.network
def test_live_fuel(api_key): # pylint: disable=unused-argument
    """Form 930 fuel mix totals match net generation"""
    data = Form930(2019,7,respondent="CISO")
    fuel = Form930Fuel(2019,7,respondent="CISO")
    assert len(fuel) == 744
    assert "sun_mw" in fuel.columns
    error = (fuel.sum(axis=1,min_count=1) - data.generation_mw).abs().median()
    assert error < 0.01*data.generation_mw.median(), f"fuel total differs from net generation by {error=}"
