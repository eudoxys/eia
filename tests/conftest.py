"""Shared pytest fixtures for the eia tests

Tests run offline by default. Tests that download data from EIA are marked
`@pytest.mark.network` and are deselected unless run with `pytest -m network`.

Every offline test gets an empty temporary cache folder and fresh in-process
caches, so tests never read or write the user's EIA cache.
"""
import io
import sys
from unittest import mock
import pandas as pd
import pytest
import eia.base
import eia.form861m
import eia.form861msales
from eia import cli
from eia.form930 import _Form930Base

def _reset_memory_caches():
    eia.form861m._cache.clear()
    eia.form861msales._cache = None
    _Form930Base.references.clear()
    _Form930Base._references_refreshed = False

@pytest.fixture(autouse=True)
def cache_dir(request,tmp_path):
    """Use an empty cache folder for each offline test (network tests use the user cache)"""
    if request.node.get_closest_marker("network"):
        yield None
        return
    saved = (eia.base._cache_dir,dict(eia.base._download_options))
    _reset_memory_caches()
    eia.base.set_cache_dir(str(tmp_path))
    try:
        yield tmp_path
    finally:
        eia.base._cache_dir = saved[0]
        eia.base._download_options.clear()
        eia.base._download_options.update(saved[1])
        _reset_memory_caches()

@pytest.fixture
def no_network():
    """Fail the test if anything tries to download data"""
    with mock.patch("eia.base.requests.get",side_effect=AssertionError("network accessed")):
        yield

@pytest.fixture
def fake_get():
    """Replace `requests.get` with a function returning `(status,content)` per URL

    Usage: `calls = fake_get(lambda url,params: (200,b"data"))`. The handler
    may also return an exception to raise, or a `(status,content,json)` tuple.
    Returns the list of `(url,params,timeout)` calls made.
    """
    patches = []
    def install(handler):
        calls = []
        def get(url,params=None,timeout=None):
            calls.append((url,params,timeout))
            result = handler(url,params)
            if isinstance(result,Exception):
                raise result
            status,content,*json = result
            response = mock.Mock(status_code=status,content=content)
            if json:
                response.json.return_value = json[0]
            return response
        patch = mock.patch("eia.base.requests.get",side_effect=get)
        patch.start()
        patches.append(patch)
        return calls
    yield install
    for patch in patches:
        patch.stop()

@pytest.fixture
def respondents(monkeypatch):
    """Accept only Form 930 respondent `CAL` without reading reference data"""
    monkeypatch.setattr(_Form930Base,"respondents",staticmethod(lambda refresh=False: ["CAL"]))

@pytest.fixture
def sales(monkeypatch):
    """Set the in-process Form 861m sales table (see `samples.sales_table()`)"""
    def install(table):
        monkeypatch.setattr(eia.form861msales,"_cache",table)
        return table
    return install

@pytest.fixture
def make_stub():
    """Make a subclass of a form class whose constructor does not access EIA data

    `make_stub(base,init)` returns a class named like `base` whose constructor
    calls `init(self,*args,**kwargs)` (default: an empty data frame). The CLI
    reads the constructor annotations of the original class.
    """
    def make(base,init=None):
        def __init__(self,*args,**kwargs):
            if init is None:
                pd.DataFrame.__init__(self)
            else:
                init(self,*args,**kwargs)
        cls = type(base.__name__,(base,),{"__init__":__init__})
        cls.__init__.__annotations__.update(base.__init__.__annotations__)
        return cls
    return make

@pytest.fixture
def run_cli(monkeypatch):
    """Run the CLI with a stub form class; returns `(code,stdout,stderr)`"""
    def run(command,form,*argv):
        monkeypatch.setitem(cli._FORMS,command,form)
        out,err = io.StringIO(),io.StringIO()
        with mock.patch.object(sys,"stdout",out), mock.patch.object(sys,"stderr",err):
            code = cli.main(command,*argv)
        return code,out.getvalue(),err.getvalue()
    return run

@pytest.fixture
def api_key():
    """Skip the test when no EIA API key is available"""
    try:
        return eia.form930._api_key()
    except RuntimeError:
        pytest.skip("no EIA API key (set EIA_API_KEY or create ~/.eia/api_key)")
