"""Shared helper tests: arguments, cache folder, downloads, API key (offline)"""
import os
import sys
import subprocess
import datetime as dt
import importlib.metadata
from unittest import mock
import pytest
import requests
import eia
import eia.base
import eia.form930
from eia.base import month_number, check_year, check_month, check_bool, check_choice
from eia.form860m import Form860m
from eia.form861m import Form861m
from eia.form861msales import Form861mSales
from eia.form923 import Form923
from eia.form930 import Form930, Form930Fuel

FORMS = [Form860m,Form861m,Form861mSales,Form923,Form930,Form930Fuel]

def test_version():
    """Package version matches the installed package metadata"""
    assert eia.__version__ == importlib.metadata.version("eia")

# command line arguments

OPTIONS = {"form":"region_hourly","year":"2020","month":"8","respondent":"CAL",
    "subset":None,"refresh":False,"raw":False,"output":None}

@pytest.mark.parametrize("form",FORMS,ids=lambda x: x.__name__)
def test_makeargs_exists(form):
    """Every form accepts command line options"""
    assert hasattr(form,"makeargs")

def test_makeargs():
    """makeargs keeps the options each form accepts and coerces strings"""
    assert Form930.makeargs(**OPTIONS) == \
        {"respondent":"CAL","year":2020,"month":8,"refresh":False,"raw":False}
    assert Form861mSales.makeargs(**OPTIONS) == {"year":2020,"month":8,"refresh":False,"raw":False}
    args = Form860m.makeargs(**OPTIONS)
    assert args["year"] == 2020 and args["month"] == 8
    assert Form930.makeargs(month=None)["month"] is None

def test_makeargs_lists():
    """makeargs splits comma-separated filters"""
    args = Form923.makeargs(year="2020",states="CA, NV",bas="CISO",fuels="NG,WAT",
        plants="1,2",by=None,increments=False)
    assert args == {"year":2020,"states":["CA","NV"],"bas":["CISO"],"fuels":["NG","WAT"],
        "plants":[1,2],"increments":False}
    assert Form923.makeargs(states=None)["states"] is None

@pytest.mark.parametrize("kwargs",[{"plants":"1,x"},{"year":"last"}])
def test_makeargs_invalid(kwargs):
    """makeargs rejects invalid values"""
    form = Form923 if "plants" in kwargs else Form930
    with pytest.raises(ValueError):
        form.makeargs(**kwargs)

@pytest.mark.parametrize("text,number",
    [("August",8),("aug",8),("Sept",9),("sep.",9),("MAY",5),("12",12)])
def test_month_number(text,number):
    """Month names, abbreviations, and numbers are accepted"""
    assert month_number(text) == number
    assert Form930.makeargs(month=text)["month"] == number

@pytest.mark.parametrize("text",["ju","jux","13","0",""])
def test_month_number_invalid(text):
    """Ambiguous or invalid months are rejected"""
    with pytest.raises(ValueError):
        month_number(text)

# argument validation

VALIDATION_CASES = [
    (TypeError, check_year, (2020.0, 2015), {}),
    (TypeError, check_year, (True, 2015), {}),
    (TypeError, check_year, (None, 2015), {}),
    (ValueError, check_year, ("last", 2015), {}),
    (ValueError, check_year, (2014, 2015), {}),
    (ValueError, check_year, (9999, 2015), {}),
    (TypeError, check_month, (8.0,), {}),
    (TypeError, check_month, (None,), {}),
    (ValueError, check_month, (0,), {}),
    (ValueError, check_month, ("Foo",), {}),
    (TypeError, check_bool, ("refresh", 1), {}),
    (ValueError, check_choice, ("by", "state", {"ba": 1}), {}),
    (TypeError, check_choice, ("by", ["ba"], {"ba": 1}), {}),
    (ValueError, Form860m, (2014, 8), {}),
    (ValueError, Form860m, (2020, 13), {}),
    (TypeError, Form860m, (2020.5, 8), {}),
    (ValueError, Form860m, (2020, 8), {"subset": "Bogus"}),
    (TypeError, Form860m, (2020, 8), {"refresh": "yes"}),
    (TypeError, Form860m, (2020, 8, "Planned"), {}),
    (ValueError, Form861m, (2016, 8), {}),
    (ValueError, Form861m, ("2020", "Foo"), {}),
    (TypeError, Form861m, (2020, 8), {"raw": 1}),
    (ValueError, Form923, (2007,), {}),
    (ValueError, Form923, (2020, 13), {}),
    (ValueError, Form923, (2020,), {"by": "state"}),
    (TypeError, Form923, ([2020],), {}),
    (TypeError, Form923, (2020, 8, "CA"), {}),
    (TypeError, Form923, (2020, 8), {"plants": "6099"}),
    (TypeError, Form930, (2020, 8), {}),
    (TypeError, Form930, (2020, 8), {"respondent": None}),
    (TypeError, Form930, ("CAL", 2020, 8), {}),
    (ValueError, Form930, (2020, 8), {"respondent": "XXX"}),
    (ValueError, Form930, (2014, 8), {"respondent": "CAL"}),
    (ValueError, Form930, (2020, 13), {"respondent": "CAL"}),
    (TypeError, Form930, (2020, 8), {"respondent": "CAL", "refresh": "yes"}),
    (TypeError, Form930Fuel, (2020, 8), {"respondent": None}),
    (ValueError, Form930Fuel, (2020, 8), {"respondent": "XXX"}),
    (ValueError, Form930Fuel, (2017, 8), {"respondent": "CAL"}),
    (TypeError, Form930Fuel, (2020, 8), {"respondent": "CAL", "fuels": 1}),
    (TypeError, Form861mSales, (2020.0, 8), {}),
    (ValueError, Form861mSales, (1989, 8), {}),
    (ValueError, Form861mSales, (2020, "Foo"), {}),
    ]

def _case_id(case):
    expected,func,args,kwargs = case
    return f"{func.__name__}{args}{kwargs or ''}-{expected.__name__}"

@pytest.mark.parametrize("case",VALIDATION_CASES,ids=[_case_id(x) for x in VALIDATION_CASES])
def test_invalid_arguments(case,respondents,no_network): # pylint: disable=unused-argument
    """Invalid arguments raise TypeError or ValueError before any download"""
    expected,func,args,kwargs = case
    with pytest.raises(expected):
        func(*args,**kwargs)

def test_valid_arguments():
    """Validation helpers coerce valid values"""
    assert check_year("2020",2015) == 2020
    assert check_year(None,2015,optional=True) is None
    assert check_month("Aug") == 8
    assert check_month(None,optional=True) is None
    assert check_bool("raw",None) is False
    assert check_bool("raw",None,True) is True

def test_validation_optimized():
    """Validation does not rely on assert (the invalid argument tests pass under python -O)"""
    result = subprocess.run([sys.executable,"-O","-m","pytest","-q","-p","no:cacheprovider",
        f"{__file__}::test_invalid_arguments"],capture_output=True,text=True,check=False,
        cwd=os.path.dirname(__file__))
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]

# cache folder

def test_default_cache_dir(monkeypatch):
    """Default cache folder is the user cache folder, not the package folder"""
    monkeypatch.setattr(eia.base,"_cache_dir",None)
    monkeypatch.delenv(eia.base.CACHE_ENV,raising=False)
    default = eia.base.cache_dir()
    package_dir = os.path.dirname(os.path.abspath(eia.base.__file__))
    assert not os.path.abspath(default).startswith(package_dir)
    assert os.path.basename(default.rstrip(os.sep)) in ("eudoxys","Cache")

def test_cache_dir_selection(monkeypatch,tmp_path):
    """EIA_CACHE_DIR, set_cache_dir(), cache_entry(), and clear_cache()"""
    envdir,setdir = tmp_path/"env",tmp_path/"set"
    envdir.mkdir()
    setdir.mkdir()
    monkeypatch.setattr(eia.base,"_cache_dir",None)
    monkeypatch.setenv(eia.base.CACHE_ENV,str(envdir))
    assert eia.base.cache_dir() == os.path.abspath(envdir)
    entry = eia.base.cache_entry("form923","2020.csv.gz",version=1)
    assert entry.pathname == os.path.join(envdir,"eia","1","form923","2020.csv.gz")
    assert os.path.isdir(entry.dirname)

    assert eia.set_cache_dir(str(setdir)) == os.path.abspath(envdir), "previous folder not returned"
    assert eia.cache_dir() == os.path.abspath(setdir)
    entry = eia.base.cache_entry("hs861m.csv",version=0)
    assert entry.pathname.startswith(os.path.join(setdir,"eia","0"))
    with open(entry.pathname,"w",encoding="utf-8") as fh:
        fh.write("x")
    eia.clear_cache()
    assert not (setdir/"eia").exists(), "clear_cache() left files"
    eia.set_cache_dir(None)
    assert eia.cache_dir() == os.path.abspath(envdir)

# downloads

@pytest.fixture
def responses(fake_get):
    """Fake requests.get returning (or raising) the given items in order"""
    def install(*items):
        items = list(items)
        return fake_get(lambda url,params: items.pop(0) if isinstance(items[0],Exception)
            else (items.pop(0),b"data"))
    eia.base.set_download_options(backoff=0)
    return install

def test_download(responses):
    """Content is returned and the timeout passed through"""
    calls = responses(200)
    assert eia.base.download("u",timeout=7).content == b"data"
    assert calls == [("u",None,7)]

def test_download_first(responses):
    """The first URL that exists is used"""
    calls = responses(404,200,200)
    assert eia.base.download_first(["a","b","c"]) == b"data"
    assert [x[0] for x in calls] == ["a","b"]

def test_download_first_missing(responses):
    """All URLs missing raises RuntimeError naming them"""
    responses(404,404)
    with pytest.raises(RuntimeError,match=r"\['a', 'b'\]"):
        eia.base.download_first(["a","b"])

def test_download_retry(responses):
    """Transient failures are retried"""
    calls = responses(requests.ConnectionError("x"),503,requests.Timeout("y"),200)
    assert eia.base.download("u",retries=3) is not None
    assert len(calls) == 4

def test_download_retries_exhausted(responses):
    """Exhausted retries raise RuntimeError with the status"""
    calls = responses(503,503)
    with pytest.raises(RuntimeError,match="503"):
        eia.base.download("u",retries=1)
    assert len(calls) == 2

def test_download_missing(responses):
    """404 is not retried; missing_ok returns None"""
    calls = responses(404)
    assert eia.base.download("u",missing_ok=True) is None
    assert len(calls) == 1
    responses(404)
    with pytest.raises(RuntimeError,match="404"):
        eia.base.download("u")

@pytest.mark.parametrize("error,retries",[
    (requests.ConnectionError,0),
    (requests.exceptions.InvalidURL,None),
    ])
def test_download_redacts_api_key(responses,error,retries):
    """API keys are removed from error text and the error is not chained"""
    calls = responses(error("https://x/?api_key=SECRET&a=1"))
    with pytest.raises(RuntimeError) as info:
        eia.base.download("u",**({} if retries is None else {"retries":retries}))
    assert "SECRET" not in str(info.value) and info.value.__cause__ is None
    assert len(calls) == 1, "error was retried"

def test_download_options_environment(monkeypatch):
    """Timeout and retries are read from the environment"""
    monkeypatch.setenv(eia.base.TIMEOUT_ENV,"12")
    monkeypatch.setenv(eia.base.RETRIES_ENV,"bad")
    eia.base._download_options.update(timeout=None,retries=None)
    options = eia.base.download_options()
    assert options["timeout"] == 12
    assert options["retries"] == eia.base.DEFAULT_RETRIES

@pytest.mark.parametrize("bad",[{"timeout":0},{"retries":-1},{"retries":1.5},{"backoff":"1"}])
def test_download_options_invalid(bad):
    """Invalid download options are rejected"""
    with pytest.raises(ValueError):
        eia.base.set_download_options(**bad)

# API key

@pytest.fixture
def home(monkeypatch,tmp_path):
    """Empty home folder with no EIA_API_KEY or HOME in the environment"""
    monkeypatch.delenv("EIA_API_KEY",raising=False)
    monkeypatch.delenv("HOME",raising=False)
    monkeypatch.setattr(eia.form930.os.path,"expanduser",
        lambda path: path.replace("~",str(tmp_path),1) if path.startswith("~") else path)
    return tmp_path

def test_api_key_missing(home):
    """No key gives a clear, unchained error"""
    with pytest.raises(RuntimeError) as info:
        eia.form930._api_key()
    for text in ["EIA_API_KEY",os.path.join(home,".eia","api_key"),"register.php"]:
        assert text in str(info.value)
    assert info.value.__cause__ is None and info.value.__context__ is None

def test_api_key_sources(home,monkeypatch):
    """Key file is read; a non-empty environment variable takes precedence"""
    (home/".eia").mkdir()
    (home/".eia"/"api_key").write_text("  FILEKEY\n",encoding="utf-8")
    assert eia.form930._api_key() == "FILEKEY"
    monkeypatch.setenv("EIA_API_KEY"," ENVKEY ")
    assert eia.form930._api_key() == "ENVKEY"
    monkeypatch.setenv("EIA_API_KEY","")
    assert eia.form930._api_key() == "FILEKEY"

def test_api_key_empty_file(home):
    """An empty key file is an error"""
    (home/".eia").mkdir()
    (home/".eia"/"api_key").write_text("\n",encoding="utf-8")
    with pytest.raises(RuntimeError):
        eia.form930._api_key()

# publication bounds

def _months_ago(months:int) -> tuple[int,int]:
    now = dt.datetime.now()
    index = now.year*12 + now.month - 1 - months
    return index // 12, index % 12 + 1

def test_latest_month():
    """latest_month() counts back from the current month"""
    assert eia.base.latest_month(0) == _months_ago(0)
    assert eia.base.latest_month(1) == _months_ago(1)
    assert eia.base.latest_month(13) == _months_ago(13)
    eia.base.check_published(*_months_ago(1))
    eia.base.check_published(*_months_ago(0),lag=0)

@pytest.mark.filterwarnings("ignore:year=.* may not be finalized")
@pytest.mark.parametrize("form",[Form860m,Form861m,Form861mSales,Form923],ids=lambda x: x.__name__)
def test_unpublished_month(form,no_network): # pylint: disable=unused-argument
    """The current month is rejected without a download"""
    with pytest.raises(ValueError,match="not published"):
        form(*_months_ago(0))

def test_unpublished_month_form930(no_network): # pylint: disable=unused-argument
    """Form 930 rejects future months without a download"""
    if dt.datetime.now().month == 12:
        pytest.skip("next month is in the next year")
    year,month = _months_ago(-1)
    with mock.patch.object(Form930,"_check_respondent"), \
            pytest.raises(ValueError,match="not published"):
        Form930(year,month,respondent="CISO")

def test_form930_whole_year():
    """Form 930 whole-year requests stop at the current month"""
    now = dt.datetime.now()
    assert eia.form930._months(now.year,None) == list(range(1,now.month+1))
