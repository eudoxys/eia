"""Command line interface tests (offline)"""
import gzip
import sys
import zipfile
import pandas as pd
import pytest
from eia import cli
from eia.form860m import Form860m
from eia.form861m import Form861m
from eia.form861msales import Form861mSales
from eia.form923 import Form923
from eia.form930 import Form930, Form930Fuel
import samples

@pytest.mark.parametrize("command,form",[
    ("bulk_generation",Form860m),
    ("customer_demand",Form861mSales),
    ("distributed_generation",Form861m),
    ("generation_monthly",Form923),
    ("region_hourly",Form930),
    ("region_fuel_hourly",Form930Fuel),
    ])
def test_subcommand_form(command,form):
    """Each subcommand uses the right form class"""
    assert cli._FORMS[command] is form

def recorder(make_stub,base,called):
    """Stub form class recording its constructor arguments in `called`"""
    def init(self,*args,**kwargs):
        pd.DataFrame.__init__(self)
        called.append(kwargs if not args else dict(zip(["year","month"],args))|kwargs)
    return make_stub(base,init)

def test_bulk_generation_subset(make_stub,run_cli):
    """bulk_generation passes --subset to Form860m"""
    called = []
    code,_,err = run_cli("bulk_generation",recorder(make_stub,Form860m,called),
        "-y","2020","-m","8","--subset","Planned")
    assert code == cli.E_OK, err
    assert called[0]["subset"] == "Planned"
    assert called[0]["year"] == 2020 and called[0]["month"] == 8

@pytest.mark.parametrize("option,month",[("--region","8"),("--respondent","Aug")])
def test_region_hourly(make_stub,run_cli,option,month):
    """region_hourly passes respondent, year, and month to Form930"""
    called = []
    code,_,err = run_cli("region_hourly",recorder(make_stub,Form930,called),
        option,"CAL","-y","2020","-m",month)
    assert code == cli.E_OK, err
    assert called == [{"respondent":"CAL","year":2020,"month":8,"raw":False,"refresh":False}]

@pytest.mark.parametrize("argv,expected",[
    (["-y","2020","-m","8","--ba","CISO","--fuels","NG,WAT"],
        {"year":2020,"month":8,"states":None,"bas":["CISO"],"fuels":["NG","WAT"],
            "by":None,"plants":None,"increments":True,"refresh":False}),
    (["-y","2020","--state","CA","--fuel","WAT","--by","plant","--plants","6099,286","--no-increments"],
        {"year":2020,"month":None,"states":["CA"],"bas":None,"fuels":["WAT"],
            "by":"plant","plants":[6099,286],"increments":False,"refresh":False}),
    ])
def test_generation_monthly(make_stub,run_cli,argv,expected):
    """generation_monthly passes filters to Form923"""
    called = []
    code,_,err = run_cli("generation_monthly",recorder(make_stub,Form923,called),*argv)
    assert code == cli.E_OK, err
    assert {x:called[0].get(x) for x in expected} == expected # None: form default

@pytest.mark.parametrize("argv,expected",[
    (["--region","BPAT","-y","2020","-m","8"],
        {"respondent":"BPAT","year":2020,"month":8,"fuels":None,"refresh":False}),
    (["--respondent","BPAT","-y","2020","-m","aug","--fuels","WAT,WND","--refresh"],
        {"respondent":"BPAT","year":2020,"month":8,"fuels":["WAT","WND"],"refresh":True}),
    ])
def test_region_fuel_hourly(make_stub,run_cli,argv,expected):
    """region_fuel_hourly passes respondent and fuels to Form930Fuel"""
    called = []
    code,_,err = run_cli("region_fuel_hourly",recorder(make_stub,Form930Fuel,called),*argv)
    assert code == cli.E_OK, err
    assert {x:called[0].get(x) for x in expected} == expected

def test_customer_demand(sales,run_cli):
    """customer_demand coerces year and month (Form861mSales, no stub)"""
    sales(samples.sales_table())
    code,out,err = run_cli("customer_demand",Form861mSales,"-y","2022","-m","8")
    assert code == cli.E_OK, err
    assert "tot_energy_mwh" in out and "WA" in out

# output formats

EXPECTED_CSV = ",PLANT,MW\n0,1,10.0\n1,2,20.0\n"

@pytest.fixture
def small_form(make_stub):
    """Form860m stand-in returning a two-row frame"""
    return make_stub(Form860m,lambda self,**_: pd.DataFrame.__init__(self,{"PLANT":[1,2],"MW":[10.0,20.0]}))

@pytest.fixture
def bulk(run_cli,small_form):
    """Run bulk_generation with the small frame and extra options"""
    return lambda *argv: run_cli("bulk_generation",small_form,"-y","2020","-m","8",*argv)

def test_output_stdout(bulk):
    """No --output prints the frame"""
    code,out,err = bulk()
    assert code == cli.E_OK, err
    assert "PLANT" in out and "20.0" in out and err == ""

@pytest.mark.parametrize("name",["a.csv","a.csv.gz","a.csv.zip","a.xlsx"])
def test_output_extension(bulk,tmp_path,name):
    """Output format is inferred from the file extension"""
    path = tmp_path / name
    code,_,err = bulk("-o",str(path))
    assert code == cli.E_OK, err
    if name == "a.csv":
        assert pd.read_csv(path,index_col=0).MW.sum() == 30
    elif name == "a.csv.gz":
        with gzip.open(path,"rt") as fh:
            assert "20.0" in fh.read()
    elif name == "a.csv.zip":
        assert zipfile.is_zipfile(path)
        assert pd.read_csv(path,index_col=0).MW.sum() == 30
    else:
        sheets = pd.read_excel(path,sheet_name=None)
        assert list(sheets) == ["Form860m"], "sheet is not named after the form"
        assert sheets["Form860m"].MW.sum() == 30

def test_output_format_precedence(bulk,tmp_path):
    """--format takes precedence over the file extension"""
    code,_,err = bulk("-o",str(tmp_path/"b.csv"),"-f","gzip")
    assert code == cli.E_OK, err
    with gzip.open(tmp_path/"b.csv","rt") as fh:
        assert "20.0" in fh.read()
    code,_,err = bulk("-o",str(tmp_path/"b.dat"),"-f","csv")
    assert code == cli.E_OK, err
    assert pd.read_csv(tmp_path/"b.dat",index_col=0).MW.sum() == 30

def test_output_unknown_extension(bulk,tmp_path):
    """Unknown extension without --format is an error that names the file"""
    path = tmp_path / "c.dat"
    code,out,err = bulk("-o",str(path))
    assert code == cli.E_FAILED
    assert not path.exists()
    assert "None" not in err and "c.dat" in err and "--format" in err
    assert out == ""

def test_output_format_without_file(bulk):
    """--format csv without --output writes CSV to stdout"""
    code,out,err = bulk("-f","csv")
    assert code == cli.E_OK, err
    assert out.replace("\r","") == EXPECTED_CSV

@pytest.mark.parametrize("fmt",["gzip","zip","xlsx"])
def test_binary_format_without_file(bulk,fmt):
    """Binary formats require --output"""
    code,out,err = bulk("-f",fmt)
    assert code == cli.E_FAILED
    assert "--output" in err and out == ""

def test_xlsx_timestamps(make_stub,run_cli,tmp_path):
    """XLSX output writes tz-aware timestamps without a time zone"""
    def init(self,*_,**__):
        index = pd.MultiIndex.from_tuples([(pd.Timestamp("2020-08-01",tz="UTC"),"CA")],
            names=["timestamp","state"])
        pd.DataFrame.__init__(self,{"tot_mw":[1.0]},index=index)
    output = tmp_path / "out.xlsx"
    code,_,err = run_cli("distributed_generation",make_stub(Form861m,init),
        "-y","2020","-m","8","-o",str(output))
    assert code == cli.E_OK, err
    data = pd.read_excel(output)
    assert list(data.columns) == ["timestamp","state","tot_mw"]
    assert data["timestamp"].iloc[0] == pd.Timestamp("2020-08-01")

# errors

@pytest.fixture
def failing_form(make_stub):
    """Form860m stand-in that raises on construction"""
    def init(self,**_):
        raise RuntimeError("stub failure")
    return make_stub(Form860m,init)

def test_error_to_stderr(run_cli,failing_form):
    """Errors go to stderr with exit code E_FAILED"""
    code,out,err = run_cli("bulk_generation",failing_form,"-y","2020","-m","8")
    assert code == cli.E_FAILED
    assert "stub failure" in err and out == ""

def test_debug_raises(run_cli,failing_form):
    """--debug re-raises the exception"""
    with pytest.raises(RuntimeError,match="stub failure"):
        run_cli("bulk_generation",failing_form,"-y","2020","-m","8","--debug")

def test_argv_unchanged(bulk):
    """cli.main() does not change sys.argv"""
    argv = list(sys.argv)
    bulk()
    assert sys.argv == argv

def test_error_before_parsing(bulk,monkeypatch):
    """An exception before parsing finishes is reported, not an AttributeError"""
    def broken(*_,**__):
        raise RuntimeError("parser failure")
    monkeypatch.setattr(cli.argparse.ArgumentParser,"parse_args",broken)
    code,_,err = bulk()
    assert code == cli.E_FAILED and "parser failure" in err
