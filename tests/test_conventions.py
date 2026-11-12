"""Public API convention tests for every form (offline, see DESIGN.md)"""
import inspect
import pandas as pd
import pytest
from eia.form860m import Form860m
from eia.form861m import Form861m
from eia.form861msales import Form861mSales
from eia.form923 import Form923
from eia.form930 import Form930, Form930Fuel
import samples

FORMS = [Form860m,Form861m,Form861mSales,Form923,Form930,Form930Fuel]

@pytest.mark.parametrize("form",FORMS,ids=lambda x: x.__name__)
def test_signature(form):
    """year and month are the only positional arguments; raw and refresh are last"""
    params = list(inspect.signature(form.__init__).parameters.values())[1:]
    assert [x.name for x in params if x.kind == x.POSITIONAL_OR_KEYWORD] == ["year","month"]
    assert [x.name for x in params][-2:] == ["raw","refresh"]

@pytest.fixture
def cached(cache_dir,sales,respondents,no_network): # pylint: disable=unused-argument
    """Cache files for August 2020 for every form; downloads fail the test"""
    samples.write_cache_files(str(cache_dir))
    sales(samples.sales_table(years=[2020],months=[7,8]))

FRAMES = {
    "Form860m": (lambda: Form860m(2020,8),["timestamp","plant","generator"],2),
    "Form861m": (lambda: Form861m(2020,8),["timestamp","state"],2),
    "Form861mSales": (lambda: Form861mSales(2020,8),["timestamp","state"],2),
    "Form923": (lambda: Form923(2020,8),["timestamp","state","ba","fuel"],2),
    "Form923 plant": (lambda: Form923(2020,8,by="plant",plants=6099),
        ["timestamp","state","ba","plant","pm","fuel"],1),
    "Form930": (lambda: Form930(2020,8,respondent="CAL"),["timestamp"],744),
    "Form930Fuel": (lambda: Form930Fuel(2020,8,respondent="CAL",fuels="wat"),["timestamp"],744),
    }

@pytest.mark.parametrize("name",FRAMES)
def test_frame(cached,name): # pylint: disable=unused-argument
    """UTC timestamp index starting at the period, lower-case columns, plain frame operations"""
    load,index,rows = FRAMES[name]
    data = load()
    assert list(data.index.names) == index
    assert len(data) == rows
    timestamps = data.index.get_level_values("timestamp")
    assert str(timestamps.tz) == "UTC"
    assert timestamps.min() == pd.Timestamp("2020-08-01",tz="UTC")
    assert all(x == x.lower() for x in data.columns), list(data.columns)
    assert type(data.head()) is pd.DataFrame # pylint: disable=unidiomatic-typecheck

def test_values(cached): # pylint: disable=unused-argument
    """Values and columns of the normalised frames"""
    data = Form860m(2020,8)
    assert data.index[0][2] == "G1", "Form860m is not sorted by generator"
    assert data["nameplate_mw"].sum() == 12.5
    assert Form923(2020,8)["gen_mwh"].sum() == 30
    assert list(Form930(2020,8,respondent="CAL").columns) == ["load_mw","generation_mw","interchange_mw"]
    assert list(Form930Fuel(2020,8,respondent="CAL",fuels="wat").columns) == ["wat_mw"]

@pytest.mark.parametrize("form,rows",[(Form861m,4),(Form923,24),(Form861mSales,4)],
    ids=lambda x: getattr(x,"__name__",str(x)))
def test_whole_year(cached,form,rows): # pylint: disable=unused-argument
    """month=None returns the whole year"""
    assert len(form(2020)) == rows

RAW = {
    "Form860m": lambda: Form860m(2020,8,raw=True),
    "Form861m": lambda: Form861m(2020,8,raw=True),
    "Form861mSales": lambda: Form861mSales(2020,8,raw=True),
    "Form923": lambda: Form923(2020,8,raw=True),
    "Form930": lambda: Form930(2020,8,respondent="CAL",raw=True),
    "Form930Fuel": lambda: Form930Fuel(2020,8,respondent="CAL",raw=True),
    }

@pytest.mark.parametrize("name",RAW)
def test_raw_index(cached,name): # pylint: disable=unused-argument
    """raw=True returns a default integer index"""
    data = RAW[name]()
    assert isinstance(data.index,pd.RangeIndex)
    assert len(data) > 0

def test_raw_contents(cached): # pylint: disable=unused-argument
    """raw=True keeps EIA names and applies only the period selection"""
    assert "Plant ID" in Form860m(2020,8,raw=True).columns
    raw = Form923(2020,8,raw=True)
    assert "Netgen\nAugust" in raw.columns and "Netgen\nJuly" not in raw.columns
    raw = Form930(2020,8,respondent="CAL",raw=True)
    assert len(raw) == 744*3 and "period" in raw.columns
    assert len(Form930Fuel(2020,8,respondent="CAL",raw=True)) == 744*2
