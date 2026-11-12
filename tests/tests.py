"""Test EIA package modules"""
import os
import sys
import datetime as dt
from eia.form860m import Form860m
from eia.form923 import Form923
from eia.form930 import Form930, Form930Fuel
from eia.form861m import Form861m
from eia.form861msales import Form861mSales
from eia import cli
from eia.base import month_number
import eia.base
import eia.form930

def test_version():
    """Test package version matches the installed package metadata"""
    import importlib.metadata # pylint: disable=import-outside-toplevel
    errors = 0
    try:
        assert eia.__version__ == importlib.metadata.version("eia"), f"{eia.__version__=} does not match package metadata"
    except AssertionError as err:
        print(f"ERROR [eia.tests]: version --> {err}",file=sys.stderr,flush=True)
        errors += 1
    else:
        print("version ok.",file=sys.stderr,flush=True)
    return errors

def test_cli_forms():
    """Test CLI subcommands map to the correct form class"""
    errors = 0
    expected = {
        "bulk_generation": Form860m,
        "customer_demand": Form861mSales,
        "distributed_generation": Form861m,
        "generation_monthly": Form923,
        "region_hourly": Form930,
        "region_fuel_hourly": Form930Fuel,
    }
    saved = cli._FORMS["bulk_generation"]
    try:
        for command,form in expected.items():
            assert cli._FORMS[command] is form, f"eia {command} uses {cli._FORMS[command].__name__} instead of {form.__name__}"

        # check bulk_generation passes --subset through to Form860m without accessing EIA data
        called = {}
        class Stub(Form860m):
            """Record constructor arguments"""
            # pylint: disable=super-init-not-called
            def __init__(self,**kwargs):
                called.update(kwargs)
            def __str__(self):
                return ""
        Stub.__init__.__annotations__.update(Form860m.__init__.__annotations__)
        cli._FORMS["bulk_generation"] = Stub
        with open(os.devnull,"w",encoding="utf-8") as null:
            stdout,sys.stdout = sys.stdout,null
            try:
                code = cli.main("bulk_generation","-y","2020","-m","8","--subset","Planned")
            finally:
                sys.stdout = stdout
        assert code == cli.E_OK, f"eia bulk_generation returned {code=}"
        assert called.get("subset") == "Planned", f"eia bulk_generation passed {called=} without subset"
    except Exception as err:
        print(f"ERROR [eia.tests]: cli --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("cli ok.",file=sys.stderr,flush=True)
    finally:
        cli._FORMS["bulk_generation"] = saved
    return errors

def test_cli_output():
    """Test CLI output formats, errors, and argument handling without accessing EIA data"""
    # pylint: disable=too-many-locals,too-many-statements
    import io
    import gzip
    import zipfile
    import tempfile
    import pandas as pd
    errors = 0
    saved = cli._FORMS["bulk_generation"]
    class Stub(Form860m):
        """Small data frame standing in for Form860m"""
        # pylint: disable=super-init-not-called,unused-argument
        def __init__(self,**kwargs):
            pd.DataFrame.__init__(self,{"PLANT":[1,2],"MW":[10.0,20.0]})
    Stub.__init__.__annotations__.update(Form860m.__init__.__annotations__)
    Stub.__name__ = "Form860m"
    def run(*argv):
        """Run bulk_generation and return (code,stdout,stderr)"""
        out,err = io.StringIO(),io.StringIO()
        stdout,stderr = sys.stdout,sys.stderr
        sys.stdout,sys.stderr = out,err
        try:
            code = cli.main("bulk_generation","-y","2020","-m","8",*argv)
        finally:
            sys.stdout,sys.stderr = stdout,stderr
        return code,out.getvalue(),err.getvalue()
    expected = ",PLANT,MW\n0,1,10.0\n1,2,20.0\n"
    try:
        cli._FORMS["bulk_generation"] = Stub
        argv = list(sys.argv)
        with tempfile.TemporaryDirectory() as tmp:
            path = lambda name: os.path.join(tmp,name)

            # format inferred from extension
            for name in ["a.csv","a.csv.gz","a.csv.zip","a.xlsx"]:
                code,_,err = run("-o",path(name))
                assert code == cli.E_OK, f"-o {name} returned {code=}: {err}"
            assert pd.read_csv(path("a.csv"),index_col=0).MW.sum() == 30, "a.csv invalid"
            with gzip.open(path("a.csv.gz"),"rt") as fh:
                assert "20.0" in fh.read(), "a.csv.gz invalid"
            assert zipfile.is_zipfile(path("a.csv.zip")), "a.csv.zip is not a zip file"
            sheets = pd.read_excel(path("a.xlsx"),sheet_name=None)
            assert list(sheets) == ["Form860m"], f"a.xlsx has sheets {list(sheets)}"

            # --format takes precedence over extension
            code,_,err = run("-o",path("b.csv"),"-f","gzip")
            assert code == cli.E_OK, f"-o b.csv -f gzip returned {code=}: {err}"
            with gzip.open(path("b.csv"),"rt") as fh:
                assert "20.0" in fh.read(), "-o b.csv -f gzip did not write gzip"
            code,_,err = run("-o",path("b.dat"),"-f","csv")
            assert code == cli.E_OK, f"-o b.dat -f csv returned {code=}: {err}"
            assert pd.read_csv(path("b.dat"),index_col=0).MW.sum() == 30, "-o b.dat -f csv invalid"

            # unknown extension without --format
            code,out,err = run("-o",path("c.dat"))
            assert code == cli.E_FAILED, f"-o c.dat returned {code=}"
            assert not os.path.exists(path("c.dat")), "-o c.dat wrote a file"
            assert "None" not in err and "c.dat" in err and "--format" in err, \
                f"-o c.dat reported {err=}"
            assert out == "", f"error written to stdout {out=}"

        # --format without --output
        code,out,err = run("-f","csv")
        assert code == cli.E_OK, f"-f csv returned {code=}: {err}"
        assert out.replace("\r","") == expected, f"-f csv wrote {out=}"
        for fmt in ["gzip","zip","xlsx"]:
            code,out,err = run("-f",fmt)
            assert code == cli.E_FAILED, f"-f {fmt} without --output returned {code=}"
            assert "--output" in err and out == "", f"-f {fmt} reported {out=} {err=}"

        # errors go to stderr; --debug raises; sys.argv is not changed
        class Fail(Stub):
            """Raise on construction"""
            def __init__(self,**kwargs):
                raise RuntimeError("stub failure")
        Fail.__init__.__annotations__.update(Form860m.__init__.__annotations__)
        cli._FORMS["bulk_generation"] = Fail
        code,out,err = run()
        assert code == cli.E_FAILED, f"failure returned {code=}"
        assert "stub failure" in err and out == "", f"failure reported {out=} {err=}"
        try:
            run("--debug")
            raise AssertionError("--debug did not raise")
        except RuntimeError:
            pass
        assert sys.argv == argv, f"cli.main changed {sys.argv=}"

        # exception before parsing finishes does not raise AttributeError
        def broken(*args,**kwargs):
            raise RuntimeError("parser failure")
        parse_args = cli.argparse.ArgumentParser.parse_args
        cli.argparse.ArgumentParser.parse_args = broken
        try:
            code,out,err = run()
        finally:
            cli.argparse.ArgumentParser.parse_args = parse_args
        assert code == cli.E_FAILED and "parser failure" in err, \
            f"early failure returned {code=} {err=}"
    except Exception as err:
        print(f"ERROR [eia.tests]: cli output --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("cli output ok.",file=sys.stderr,flush=True)
    finally:
        cli._FORMS["bulk_generation"] = saved
    return errors

def test_makeargs():
    """Test every form accepts command line options through makeargs"""
    errors = 0
    options = {"form":"region_hourly","year":"2020","month":"8","respondent":"CAL",
        "subset":None,"refresh":False,"raw":False,"output":None}
    try:
        for form in [Form860m,Form861m,Form861mSales,Form923,Form930,Form930Fuel]:
            assert hasattr(form,"makeargs"), f"{form.__name__} has no makeargs"
        args = Form930.makeargs(**options)
        assert args == {"respondent":"CAL","year":2020,"month":8,"refresh":False,"raw":False}, \
            f"Form930 got {args=}"
        args = Form861mSales.makeargs(**options)
        assert args == {"year":2020,"month":8,"refresh":False,"raw":False}, f"Form861mSales got {args=}"
        args = Form860m.makeargs(**options)
        assert args["year"] == 2020 and args["month"] == 8, f"Form860m got {args=}"
        assert Form930.makeargs(month=None)["month"] is None, "month=None was not kept"
        args = Form923.makeargs(year="2020",states="CA, NV",bas="CISO",fuels="NG,WAT",
            plants="1,2",by=None,increments=False)
        assert args == {"year":2020,"states":["CA","NV"],"bas":["CISO"],"fuels":["NG","WAT"],
            "plants":[1,2],"increments":False}, f"Form923 got {args=}"
        assert Form923.makeargs(states=None)["states"] is None, "states=None was not kept"
        try:
            Form923.makeargs(plants="1,x")
        except ValueError:
            pass
        else:
            raise AssertionError("plants='1,x' was accepted")
        for text,number in [("August",8),("aug",8),("Sept",9),("sep.",9),("MAY",5),("12",12)]:
            assert month_number(text) == number, f"month_number({text!r}) is not {number}"
            assert Form930.makeargs(month=text)["month"] == number, f"makeargs(month={text!r}) is not {number}"
        for text in ["ju","jux","13","0",""]:
            try:
                month_number(text)
            except ValueError:
                pass
            else:
                raise AssertionError(f"month_number({text!r}) was accepted")
        try:
            Form930.makeargs(year="last")
        except ValueError:
            pass
        else:
            raise AssertionError("year='last' was accepted")
    except Exception as err:
        print(f"ERROR [eia.tests]: makeargs --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("makeargs ok.",file=sys.stderr,flush=True)
    return errors

def test_cli_region_hourly():
    """Test region_hourly passes respondent, year, and month to Form930 without accessing EIA data"""
    errors = 0
    saved = cli._FORMS["region_hourly"]
    called = {}
    class Stub(Form930):
        """Record constructor arguments"""
        # pylint: disable=super-init-not-called
        def __init__(self,year,month=None,*,respondent,raw=False,refresh=False):
            called.update(respondent=respondent,year=year,month=month,refresh=refresh)
        def __str__(self):
            return ""
    Stub.__init__.__annotations__.update(Form930.__init__.__annotations__)
    try:
        cli._FORMS["region_hourly"] = Stub
        with open(os.devnull,"w",encoding="utf-8") as null:
            stdout,sys.stdout = sys.stdout,null
            try:
                codes = [
                    cli.main("region_hourly","--region","CAL","-y","2020","-m","8"),
                    cli.main("region_hourly","--respondent","CAL","-y","2020","-m","Aug"),
                    ]
            finally:
                sys.stdout = stdout
        assert codes == [cli.E_OK]*2, f"eia region_hourly returned {codes=}"
        assert called == {"respondent":"CAL","year":2020,"month":8,"refresh":False}, \
            f"eia region_hourly passed {called=}"
    except Exception as err:
        print(f"ERROR [eia.tests]: cli region_hourly --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("cli region_hourly ok.",file=sys.stderr,flush=True)
    finally:
        cli._FORMS["region_hourly"] = saved
    return errors

def _run_cli(command,stub,*argv) -> list[int]:
    """@private Run CLI command lines with a stub form class and stdout discarded"""
    saved = cli._FORMS[command]
    try:
        cli._FORMS[command] = stub
        with open(os.devnull,"w",encoding="utf-8") as null:
            stdout,sys.stdout = sys.stdout,null
            try:
                return [cli.main(command,*x) for x in argv]
            finally:
                sys.stdout = stdout
    finally:
        cli._FORMS[command] = saved

def test_cli_generation_monthly():
    """Test generation_monthly passes filters to Form923 without accessing EIA data"""
    errors = 0
    called = []
    class Stub(Form923):
        """Record constructor arguments"""
        # pylint: disable=super-init-not-called,unused-argument
        def __init__(self,year,month=None,*,states=None,bas=None,fuels=None,plants=None,
                by="ba",increments=True,nonzero=True,precision=3,raw=False,refresh=False):
            called.append(dict(year=year,month=month,states=states,bas=bas,fuels=fuels,
                by=by,plants=plants,increments=increments,refresh=refresh))
        def __str__(self):
            return ""
    Stub.__init__.__annotations__.update(Form923.__init__.__annotations__)
    try:
        codes = _run_cli("generation_monthly",Stub,
            ["-y","2020","-m","8","--ba","CISO","--fuels","NG,WAT"],
            ["-y","2020","--state","CA","--fuel","WAT","--by","plant","--plants","6099,286",
                "--no-increments"],
            )
        assert codes == [cli.E_OK]*2, f"eia generation_monthly returned {codes=}"
        assert called[0] == {"year":2020,"month":8,"states":None,"bas":["CISO"],"fuels":["NG","WAT"],
            "by":"ba","plants":None,"increments":True,"refresh":False}, \
            f"eia generation_monthly passed {called[0]=}"
        assert called[1] == {"year":2020,"month":None,"states":["CA"],"bas":None,"fuels":["WAT"],
            "by":"plant","plants":[6099,286],"increments":False,"refresh":False}, \
            f"eia generation_monthly passed {called[1]=}"
    except Exception as err:
        print(f"ERROR [eia.tests]: cli generation_monthly --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("cli generation_monthly ok.",file=sys.stderr,flush=True)
    return errors

def test_cli_region_fuel_hourly():
    """Test region_fuel_hourly passes respondent and fuels to Form930Fuel without accessing EIA data"""
    errors = 0
    called = []
    class Stub(Form930Fuel):
        """Record constructor arguments"""
        # pylint: disable=super-init-not-called
        def __init__(self,year,month=None,*,respondent,fuels=None,raw=False,refresh=False):
            called.append(dict(respondent=respondent,year=year,month=month,fuels=fuels,refresh=refresh))
        def __str__(self):
            return ""
    Stub.__init__.__annotations__.update(Form930Fuel.__init__.__annotations__)
    try:
        codes = _run_cli("region_fuel_hourly",Stub,
            ["--region","BPAT","-y","2020","-m","8"],
            ["--respondent","BPAT","-y","2020","-m","aug","--fuels","WAT,WND","--refresh"],
            )
        assert codes == [cli.E_OK]*2, f"eia region_fuel_hourly returned {codes=}"
        assert called == [
            {"respondent":"BPAT","year":2020,"month":8,"fuels":None,"refresh":False},
            {"respondent":"BPAT","year":2020,"month":8,"fuels":["WAT","WND"],"refresh":True},
            ], f"eia region_fuel_hourly passed {called=}"
    except Exception as err:
        print(f"ERROR [eia.tests]: cli region_fuel_hourly --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("cli region_fuel_hourly ok.",file=sys.stderr,flush=True)
    return errors

def test_form860m():
    """Test Form 860m data frame"""
    errors = 0
    year = dt.datetime.now().year - 2
    for month in range(1,13):
        try:
            raw = Form860m(year,month,raw=True)
            data = Form860m(year,month,raw=False)
            assert len(data) > 0, f"no data"
        except Exception as err:
            print(f"ERROR [eia.tests]: Form860m({year=},{month=}) --> {err}",file=sys.stderr,flush=True)
            errors += 1
            raise
        else:
            print(f"Form860m({year=},{month=}) ok.",file=sys.stderr,flush=True)
    return errors

def test_form860m_badcache():
    """Test Form 860m reports a corrupt cached workbook without accessing EIA data"""
    import tempfile
    import warnings
    errors = 0
    saved = eia.base._cache_dir
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            eia.base.set_cache_dir(tmpdir)
            cachefile = os.path.join(tmpdir,"eia","1","form860m","2020-08.xlsx")
            os.makedirs(os.path.dirname(cachefile))
            with open(cachefile,"wb") as fh:
                fh.write(b"not a workbook")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    Form860m(2020,8)
                except RuntimeError as err:
                    message = str(err)
                else:
                    raise AssertionError("corrupt cache file did not raise RuntimeError")
            assert cachefile in message, f"cache path missing from error: {message}"
            assert "august_generator2020.xlsx" in message, f"URL missing from error: {message}"
            assert any(cachefile in str(x.message) for x in caught), \
                f"no warning naming the cache file ({[str(x.message) for x in caught]})"
            assert not os.path.exists(cachefile), "corrupt cache file was not deleted"
    except Exception as err:
        print(f"ERROR [eia.tests]: Form860m bad cache --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("Form860m bad cache ok.",file=sys.stderr,flush=True)
    finally:
        eia.base._cache_dir = saved
    return errors

def test_form861m():
    """Test Form 861m data frame"""
    errors = 0
    year = dt.datetime.now().year - 2
    for month in range(1,13):
        try:
            raw = Form861m(year,month,raw=True)
            data = Form861m(year,month,raw=False)
            assert len(data) > 0, f"no data"
        except Exception as err:
            print(f"ERROR [eia.tests]: Form861m({year=},{month=}) --> {err}",file=sys.stderr,flush=True)
            errors += 1
            raise
        else:
            print(f"Form861m({year=},{month=}) ok.",file=sys.stderr,flush=True)
    return errors

def _form861m_workbook(pathname,year,months):
    """Write a minimal Form 861m workbook containing only the given months"""
    import pandas as pd
    rows = [["header"]*12]*4 + [[year,month,state,"E",1,2,3,6,10,20,30,60]
        for month in months for state in ["CA","WA"]]
    pd.DataFrame(rows).to_excel(pathname,
        sheet_name="Monthly Totals- States",
        index=False,
        header=False,
        )

def test_form861m_cache():
    """Test Form 861m cache handling without accessing EIA data"""
    import tempfile
    import warnings
    from unittest import mock
    import eia.form861m
    errors = 0
    saved = eia.base._cache_dir
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            eia.base.set_cache_dir(tmpdir)
            eia.form861m._cache.clear()
            cachefile = os.path.join(tmpdir,"eia","1","form861m","2024.xlsx")
            os.makedirs(os.path.dirname(cachefile))

            # month present in cached workbook
            _form861m_workbook(cachefile,2024,[1,2])
            data = Form861m(2024,2)
            assert len(data) == 2, f"expected 2 rows, got {len(data)}"
            assert list(data.index.names) == ["timestamp","state"], \
                f"unexpected index {list(data.index.names)}"
            assert len(Form861m(2024)) == 4, "month=None did not return the whole year"
            raw = Form861m(2024,2,raw=True)
            assert "index" not in raw.columns, f"stray index column in {list(raw.columns)}"
            assert list(raw.columns[:4]) == ["year","month","state","status"], \
                f"unexpected raw columns {list(raw.columns)}"

            # month not yet published keeps the valid cache file
            try:
                Form861m(2024,5)
            except ValueError as err:
                assert "month=5" in str(err), f"month missing from error: {err}"
            else:
                raise AssertionError("missing month did not raise ValueError")
            assert os.path.exists(cachefile), "valid cache file was deleted"

            # corrupt cache file is reported and deleted
            eia.form861m._cache.clear()
            with open(cachefile,"wb") as fh:
                fh.write(b"not a workbook")
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                try:
                    Form861m(2024,1)
                except RuntimeError as err:
                    assert cachefile in str(err), f"cache path missing from error: {err}"
                else:
                    raise AssertionError("corrupt cache file did not raise RuntimeError")
            assert not os.path.exists(cachefile), "corrupt cache file was not deleted"

            # download falls back to the next URL when the first is missing
            good = os.path.join(tmpdir,"good.xlsx")
            _form861m_workbook(good,2024,[3])
            with open(good,"rb") as fh:
                content = fh.read()
            requested = []
            def fake_get(url,**_):
                requested.append(url)
                ok = url == Form861m.FORM861M_URLS[1].format(year=2024)
                return mock.Mock(status_code=200 if ok else 404,content=content)
            with mock.patch("eia.base.requests.get",side_effect=fake_get):
                data = Form861m(2024,3)
            assert len(data) == 2, f"expected 2 rows, got {len(data)}"
            assert len(requested) == 2, f"expected 2 URLs tried, got {requested}"
    except Exception as err:
        print(f"ERROR [eia.tests]: Form861m cache --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("Form861m cache ok.",file=sys.stderr,flush=True)
    finally:
        eia.base._cache_dir = saved
        eia.form861m._cache.clear()
    return errors

def test_form861msales():
    """Test Form 861m sales data frame"""
    errors = 0
    year = dt.datetime.now().year - 2
    for month in range(1,13):
        try:
            raw = Form861mSales(year,month,raw=True)
            data = Form861mSales(year,month,raw=False)
            assert len(data) > 0, f"no data"
        except Exception as err:
            print(f"ERROR [eia.tests]: Form861mSales({year=},{month=}) --> {err}",file=sys.stderr,flush=True)
            errors += 1
            raise
        else:
            print(f"Form861mSales({year=},{month=}) ok.",file=sys.stderr,flush=True)
    return errors

def test_form861msales_args():
    """Test HS 861m year/month coercion and selection without accessing EIA data"""
    import pandas as pd
    import eia.form861msales as form861msales
    errors = 0
    saved = form861msales._cache
    rows = [{"year":y,"month":m,"state":s,"status":"Final","tot_energy_mwh":1.0}
        for y in (2021,2022) for m in range(1,13) for s in ("CA","WA")]
    form861msales._cache = pd.DataFrame(rows)
    try:
        data = Form861mSales("2022","8")
        assert list(data.index.names) == ["timestamp","state"] and len(data) == 2, \
            f"year+month got {data.index.names=}, {len(data)=}"
        raw = Form861mSales(2022,8,raw=True)
        assert len(raw) == 2 and set(raw["month"]) == {8}, f"raw selection not applied ({len(raw)=})"
        assert list(raw.columns[:4]) == ["year","month","state","status"], f"raw got {list(raw.columns)}"
        assert Form861mSales(2022,"Aug").equals(data), "month name not accepted"
        data = Form861mSales(2022)
        assert len(data) == 24, f"year only got {len(data)=}"
        assert set(data.index.get_level_values("timestamp").year) == {2022}, "year filter not applied"
        assert len(Form861mSales()) == 48, "year=None did not return all years"
        assert len(Form861mSales(month=3)) == 4, "month only did not select that month in every year"
        assert cli.main("customer_demand","-y","2022","-m","8") == cli.E_OK, "CLI failed"
        for year,month in [("abc",1),(2022,13),(2022,"Foo"),(1800,1),(2019,1)]:
            try:
                Form861mSales(year,month)
            except ValueError:
                pass
            else:
                raise AssertionError(f"Form861mSales({year=},{month=}) did not raise ValueError")
    except Exception as err:
        print(f"ERROR [eia.tests]: Form861mSales arguments --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("Form861mSales arguments ok.",file=sys.stderr,flush=True)
    finally:
        form861msales._cache = saved
    return errors

_VALIDATION_SCRIPT = '''
import sys
from eia.base import check_year, check_month, check_bool, check_choice
from eia.form860m import Form860m
from eia.form861m import Form861m
from eia.form923 import Form923
from eia.form930 import Form930, Form930Fuel, _Form930Base
from eia.form861msales import Form861mSales
_Form930Base.respondents = staticmethod(lambda refresh=False: ["CAL"])
cases = [
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
    (ValueError, Form861m, (2016, 8), {}),
    (ValueError, Form861m, ("2020", "Foo"), {}),
    (TypeError, Form861m, (2020, 8), {"raw": 1}),
    (ValueError, Form923, (2007,), {}),
    (ValueError, Form923, (2020, 13), {}),
    (ValueError, Form923, (2020,), {"by": "state"}),
    (TypeError, Form923, ([2020],), {}),
    (TypeError, Form923, (2020, 8, "CA"), {}),
    (TypeError, Form923, (2020, 8), {"plants": "6099"}),
    (TypeError, Form860m, (2020, 8, "Planned"), {}),
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
for expected, func, args, kwargs in cases:
    try:
        func(*args, **kwargs)
    except expected:
        continue
    except Exception as err:
        sys.exit(f"{func.__name__}{args} {kwargs} raised {type(err).__name__}: {err}")
    sys.exit(f"{func.__name__}{args} {kwargs} did not raise {expected.__name__}")
assert check_year("2020", 2015) == 2020 and check_year(None, 2015, optional=True) is None
assert check_month("Aug") == 8 and check_month(None, optional=True) is None
assert check_bool("raw", None) is False and check_bool("raw", None, True) is True
print("ok")
'''

def test_argument_validation():
    """Test argument validation raises TypeError/ValueError, also under `python -O`"""
    import subprocess
    errors = 0
    try:
        for flags in [[],["-O"]]:
            result = subprocess.run([sys.executable,*flags,"-c",_VALIDATION_SCRIPT],
                capture_output=True,text=True,check=False)
            assert result.returncode == 0 and result.stdout.strip() == "ok", \
                f"python {' '.join(flags)} validation failed: {result.stderr.strip()}"
    except Exception as err:
        print(f"ERROR [eia.tests]: argument validation --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("argument validation ok.",file=sys.stderr,flush=True)
    return errors

def test_form861msales_cachedir():
    """Test HS 861m uses the eia cache folder without accessing EIA data"""
    import tempfile
    import pandas as pd
    import eia.form861msales as form861msales
    from cache import Cache
    errors = 0
    saved = (form861msales._cache,eia.base._cache_dir,Cache.CACHEDIR)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            pathname = os.path.join(tmpdir,"eia","0","hs861m.csv")
            os.makedirs(os.path.dirname(pathname))
            pd.DataFrame([{"year":2022,"month":8,"state":"CA","status":"Final",
                "tot_energy_mwh":1.0}]).to_csv(pathname,index=False)
            form861msales._cache = None
            eia.base.set_cache_dir(tmpdir)
            data = Form861mSales(2022,8)
            assert len(data) == 1, f"cache file in cache folder not used ({len(data)=})"
            assert Cache.CACHEDIR == saved[2], "default Cache.CACHEDIR was changed"
    except Exception as err:
        print(f"ERROR [eia.tests]: Form861mSales cache folder --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("Form861mSales cache folder ok.",file=sys.stderr,flush=True)
    finally:
        form861msales._cache = saved[0]
        eia.base._cache_dir = saved[1]
        Cache.CACHEDIR = saved[2]
    return errors

def test_cache_dir():
    """Test cache folder selection without accessing EIA data"""
    import tempfile
    from unittest import mock
    import eia as package
    errors = 0
    saved = eia.base._cache_dir
    try:
        package_dir = os.path.dirname(os.path.abspath(eia.base.__file__))
        with mock.patch.dict(os.environ,{},clear=False):
            os.environ.pop(eia.base.CACHE_ENV,None)
            default = eia.base.cache_dir()
            assert not os.path.abspath(default).startswith(package_dir), \
                f"default cache folder {default} is inside the package"
            assert os.path.basename(default.rstrip(os.sep)) in ("eudoxys","Cache"), \
                f"default cache folder {default} is not the eudoxys user cache folder"
            with tempfile.TemporaryDirectory() as envdir, tempfile.TemporaryDirectory() as setdir:
                os.environ[eia.base.CACHE_ENV] = envdir
                assert eia.base.cache_dir() == os.path.abspath(envdir), "EIA_CACHE_DIR ignored"
                entry = eia.base.cache_entry("form923","2020.csv.gz",version=1)
                assert entry.pathname == os.path.join(envdir,"eia","1","form923","2020.csv.gz"), \
                    f"unexpected cache path {entry.pathname}"
                assert os.path.isdir(entry.dirname), "cache entry folder not created"
                assert package.set_cache_dir(setdir) == os.path.abspath(envdir), "previous folder not returned"
                assert package.cache_dir() == os.path.abspath(setdir), "set_cache_dir() ignored"
                entry = eia.base.cache_entry("hs861m.csv",version=0)
                assert entry.pathname.startswith(os.path.join(setdir,"eia","0")), \
                    f"set_cache_dir() not used by cache entries ({entry.pathname})"
                with open(entry.pathname,"w",encoding="utf-8") as fh:
                    fh.write("x")
                package.clear_cache()
                assert not os.path.exists(os.path.join(setdir,"eia")), "clear_cache() left files"
                package.set_cache_dir(None)
                assert package.cache_dir() == os.path.abspath(envdir), "set_cache_dir(None) did not restore default"
    except Exception as err:
        print(f"ERROR [eia.tests]: cache folder --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("cache folder ok.",file=sys.stderr,flush=True)
    finally:
        eia.base._cache_dir = saved
    return errors

def test_download():
    """Test the download helper without accessing EIA data"""
    # pylint: disable=too-many-statements
    from unittest import mock
    import requests
    errors = 0
    saved = eia.base.set_download_options(backoff=0)
    try:
        def responses(*items):
            """Fake requests.get returning/raising items in order"""
            calls = []
            def fake_get(url,params=None,timeout=None):
                calls.append((url,params,timeout))
                item = items[len(calls)-1]
                if isinstance(item,Exception):
                    raise item
                return mock.Mock(status_code=item,content=b"data")
            return fake_get,calls

        # success, timeout passed through
        fake,calls = responses(200)
        with mock.patch("eia.base.requests.get",side_effect=fake):
            assert eia.base.download("u",timeout=7).content == b"data", "wrong content"
        assert calls == [("u",None,7)], f"unexpected calls {calls}"

        # first URL that exists is used, missing URLs are skipped
        fake,calls = responses(404,200,200)
        with mock.patch("eia.base.requests.get",side_effect=fake):
            assert eia.base.download_first(["a","b","c"]) == b"data", "wrong content"
        assert [x[0] for x in calls] == ["a","b"], f"unexpected calls {calls}"
        fake,calls = responses(404,404)
        with mock.patch("eia.base.requests.get",side_effect=fake):
            try:
                eia.base.download_first(["a","b"])
            except RuntimeError as err:
                assert "['a', 'b']" in str(err), f"URLs missing from error: {err}"
            else:
                raise AssertionError("download_first() did not raise RuntimeError")

        # transient failures are retried
        fake,calls = responses(requests.ConnectionError("x"),503,requests.Timeout("y"),200)
        with mock.patch("eia.base.requests.get",side_effect=fake):
            assert eia.base.download("u",retries=3) is not None, "retry did not succeed"
        assert len(calls) == 4, f"expected 4 attempts, got {len(calls)}"

        # retries exhausted
        fake,calls = responses(503,503)
        with mock.patch("eia.base.requests.get",side_effect=fake):
            try:
                eia.base.download("u",retries=1)
            except RuntimeError as err:
                assert "503" in str(err), f"status missing from error: {err}"
            else:
                raise AssertionError("exhausted retries did not raise RuntimeError")
        assert len(calls) == 2, f"expected 2 attempts, got {len(calls)}"

        # 404 is not retried; missing_ok returns None
        fake,calls = responses(404)
        with mock.patch("eia.base.requests.get",side_effect=fake):
            assert eia.base.download("u",missing_ok=True) is None, "missing_ok did not return None"
        assert len(calls) == 1, "404 was retried"
        fake,calls = responses(404)
        with mock.patch("eia.base.requests.get",side_effect=fake):
            try:
                eia.base.download("u")
            except RuntimeError as err:
                assert "404" in str(err), f"status missing from error: {err}"
            else:
                raise AssertionError("404 did not raise RuntimeError")

        # API keys are removed from error text and not chained
        fake,calls = responses(requests.ConnectionError("https://x/?api_key=SECRET&a=1"))
        with mock.patch("eia.base.requests.get",side_effect=fake):
            try:
                eia.base.download("u",retries=0)
            except RuntimeError as err:
                assert "SECRET" not in str(err) and err.__cause__ is None, f"API key leaked: {err}"
            else:
                raise AssertionError("connection error did not raise RuntimeError")

        # other requests errors are not retried and keys are removed too
        fake,calls = responses(requests.exceptions.InvalidURL("https://x/?api_key=SECRET&a=1"))
        with mock.patch("eia.base.requests.get",side_effect=fake):
            try:
                eia.base.download("u")
            except RuntimeError as err:
                assert "SECRET" not in str(err) and err.__cause__ is None, f"API key leaked: {err}"
            else:
                raise AssertionError("invalid URL did not raise RuntimeError")
        assert len(calls) == 1, "invalid URL was retried"

        # options and environment
        with mock.patch.dict(os.environ,{eia.base.TIMEOUT_ENV:"12",eia.base.RETRIES_ENV:"bad"}):
            eia.base._download_options.update(timeout=None,retries=None)
            options = eia.base.download_options()
            assert options["timeout"] == 12 and options["retries"] == eia.base.DEFAULT_RETRIES, \
                f"environment ignored {options}"
        for bad in [{"timeout":0},{"retries":-1},{"retries":1.5},{"backoff":"1"}]:
            try:
                eia.base.set_download_options(**bad)
            except ValueError:
                pass
            else:
                raise AssertionError(f"set_download_options({bad}) did not raise ValueError")
    except Exception as err:
        print(f"ERROR [eia.tests]: download --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("download ok.",file=sys.stderr,flush=True)
    finally:
        eia.base._download_options.update(timeout=None,retries=None,backoff=saved["backoff"])
    return errors

def test_api_key():
    """Test API key lookup (offline)"""
    import tempfile
    from unittest import mock
    errors = 0
    try:
        with tempfile.TemporaryDirectory() as home:
            env = {x:y for x,y in os.environ.items() if x not in ["EIA_API_KEY","HOME"]}
            def expanduser(path):
                return path.replace("~",home,1) if path.startswith("~") else path
            with mock.patch.dict(os.environ,env,clear=True), \
                    mock.patch("eia.form930.os.path.expanduser",side_effect=expanduser):

                # no HOME, no key: clear error, not KeyError/FileNotFoundError
                try:
                    eia.form930._api_key()
                except RuntimeError as err:
                    for text in ["EIA_API_KEY",os.path.join(home,".eia","api_key"),"register.php"]:
                        assert text in str(err), f"{text!r} missing from error: {err}"
                    assert err.__cause__ is None and err.__context__ is None, "error is chained"
                else:
                    raise AssertionError("missing key did not raise RuntimeError")

                # key file
                os.makedirs(os.path.join(home,".eia"))
                path = os.path.join(home,".eia","api_key")
                with open(path,"w",encoding="utf-8") as fh:
                    fh.write("  FILEKEY\n")
                assert eia.form930._api_key() == "FILEKEY", "key file not read"

                # environment takes precedence; empty value is ignored
                with mock.patch.dict(os.environ,{"EIA_API_KEY":" ENVKEY "}):
                    assert eia.form930._api_key() == "ENVKEY", "environment key not used"
                with mock.patch.dict(os.environ,{"EIA_API_KEY":""}):
                    assert eia.form930._api_key() == "FILEKEY", "empty environment key used"

                # empty key file
                with open(path,"w",encoding="utf-8") as fh:
                    fh.write("\n")
                try:
                    eia.form930._api_key()
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("empty key file did not raise RuntimeError")
    except Exception as err:
        print(f"ERROR [eia.tests]: api_key --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("api_key ok.",file=sys.stderr,flush=True)
    return errors

def test_published():
    """Test unpublished months are rejected without accessing EIA data"""
    from unittest import mock
    errors = 0
    try:
        now = dt.datetime.now()
        this = (now.year,now.month)
        prev = (now.year,now.month-1) if now.month > 1 else (now.year-1,12)
        assert eia.base.latest_month(0) == this, "lag 0 is not the current month"
        assert eia.base.latest_month(1) == prev, "lag 1 is not the previous month"
        assert eia.base.latest_month(13)[0] == now.year-1 - (now.month == 1), "lag 13 is wrong"
        eia.base.check_published(*prev)
        eia.base.check_published(*this,lag=0)
        with mock.patch("eia.base.requests.get",side_effect=AssertionError("network accessed")):
            for form,args in [(Form860m,this),(Form861m,this),(Form861mSales,this),(Form923,this)]:
                try:
                    form(*args)
                except ValueError as err:
                    assert "not published" in str(err), f"{form.__name__}: {err}"
                else:
                    raise AssertionError(f"{form.__name__}{args} did not raise ValueError")
            if now.month < 12:
                with mock.patch.object(Form930,"_check_respondent"):
                    try:
                        Form930(now.year,now.month+1,respondent="CISO")
                    except ValueError as err:
                        assert "not published" in str(err), f"Form930: {err}"
                    else:
                        raise AssertionError("Form930 future month did not raise ValueError")
        months = eia.form930._months(now.year,None)
        assert months == list(range(1,now.month+1)), f"Form930 whole year includes {months}"
    except Exception as err:
        print(f"ERROR [eia.tests]: unpublished months --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("unpublished months ok.",file=sys.stderr,flush=True)
    return errors

def test_form930_reference():
    """Test Form 930 reference data caching and refresh without accessing EIA data"""
    import io
    import tempfile
    from unittest import mock
    import pandas as pd
    from eia.form930 import _Form930Base
    errors = 0
    saved = eia.base._cache_dir
    def workbook(*codes):
        """Reference workbook containing the given BA codes"""
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer,engine="openpyxl") as writer:
            pd.DataFrame({"BA Code":list(codes)}).to_excel(writer,sheet_name="BAs",index=False)
            pd.DataFrame({"Region/Country Code":["CAL"]}).to_excel(writer,sheet_name="Regions",index=False)
        return buffer.getvalue()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            eia.base.set_cache_dir(tmpdir)
            _Form930Base.references.clear()
            _Form930Base._references_refreshed = False
            downloads = []
            content = {"data":workbook("CISO")}
            def fake_get(url,**_):
                downloads.append(url)
                return mock.Mock(status_code=200,content=content["data"])
            with mock.patch("eia.base.requests.get",side_effect=fake_get):
                assert _Form930Base.respondents() == ["CAL","CISO"], "wrong respondents"
                assert len(downloads) == 1, f"workbook downloaded {len(downloads)} times"

                # a new process reads the disk cache without network access
                _Form930Base.references.clear()
                _Form930Base._references_refreshed = False
                Form930._check_respondent("region","CISO")
                assert len(downloads) == 1, "cached reference data was downloaded again"

                # an unknown code refreshes the cache once
                content["data"] = workbook("CISO","NEWB")
                Form930._check_respondent("region","NEWB")
                assert len(downloads) == 2, "unknown code did not refresh reference data"
                try:
                    Form930._check_respondent("region","NOPE")
                except ValueError:
                    pass
                else:
                    raise AssertionError("invalid code did not raise ValueError")
                assert len(downloads) == 2, "invalid code refreshed reference data twice"

                # refresh always downloads
                _Form930Base.respondents(refresh=True)
                assert len(downloads) == 3, "refresh did not download reference data"
    except Exception as err:
        print(f"ERROR [eia.tests]: Form930 reference --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("Form930 reference ok.",file=sys.stderr,flush=True)
    finally:
        eia.base._cache_dir = saved
        _Form930Base.references.clear()
        _Form930Base._references_refreshed = False
    return errors

def test_form923():
    """Test Form 923 data frame by BA and by plant"""
    errors = 0
    year = dt.datetime.now().year - 2
    try:
        data = Form923(year,8)
        assert len(data) > 0, "no BA data"
        assert list(data.index.names) == ["timestamp","state","ba","fuel"], "invalid BA index"
        plants = Form923(year,8,by="plant")
        assert len(plants) > 0, "no plant data"
        assert list(plants.index.names) == ["timestamp","state","ba","plant","pm","fuel"], "invalid plant index"
        assert abs(plants["gen_mwh"].sum() - data["gen_mwh"].sum()) < 1, "plant total does not match BA total"
    except Exception as err:
        print(f"ERROR [eia.tests]: Form923({year=}) --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print(f"Form923({year=}) ok.",file=sys.stderr,flush=True)
    return errors

def test_form930():
    """Test Form 930 data frames (requires an EIA API key)"""
    try:
        eia.form930._api_key()
    except RuntimeError:
        print("Form930 skipped (no EIA API key)",file=sys.stderr,flush=True)
        return 0
    errors = 0
    try:
        for year,month in [(2018,1),(2018,7)]:
            data = Form930(year,month,respondent="CISO")
            assert len(data) == 744, f"{len(data)=} hours in {year}-{month}"
            assert data.index[0] == dt.datetime(year,month,1,tzinfo=dt.timezone.utc), "invalid first hour"
        fuel = Form930Fuel(2018,7,respondent="CISO")
        assert len(fuel) == 744, f"{len(fuel)=} hours"
        assert "sun_mw" in fuel.columns, "no solar data"
        total = fuel.sum(axis=1,min_count=1)
        error = (total - data.generation_mw).abs().median()
        assert error < 0.01*data.generation_mw.median(), f"fuel total differs from net generation by {error=}"
    except Exception as err:
        print(f"ERROR [eia.tests]: Form930 --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("Form930 ok.",file=sys.stderr,flush=True)
    return errors

def _write_conventions_fixtures(tmpdir):
    """@private Write synthetic EIA cache files for every form (no network access)"""
    import pandas as pd
    import eia.form861msales as form861msales
    base = os.path.join(tmpdir,"eia","1")

    # Form 860m: workbook placeholder and subset cache with EIA headers
    os.makedirs(os.path.join(base,"form860m"))
    with open(os.path.join(base,"form860m","2020-08.xlsx"),"wb") as fh:
        fh.write(b"placeholder")
    pd.DataFrame({
        "Entity ID":[1,1],"Entity Name":["Owner","Owner"],"Plant ID":[10,10],
        "Plant Name":["Plant","Plant"],"Plant State":["CA","CA"],"Generator ID":["G2","G1"],
        "Balancing Authority Code":["CISO","CISO"],"Nameplate Capacity (MW)":[5.0,7.5],
        "Energy Source Code":["SUN","NG"],"Prime Mover Code":["PV","GT"],"Operating Year":[2019,2001],
        }).to_csv(os.path.join(base,"form860m","2020-08-operating.csv.gz"),index=False,compression="gzip")

    # Form 861m: workbook with two months
    os.makedirs(os.path.join(base,"form861m"))
    _form861m_workbook(os.path.join(base,"form861m","2020.xlsx"),2020,[7,8])

    # Form 861m sales: in-process table
    form861msales._cache = pd.DataFrame([{"year":2020,"month":m,"state":s,"status":"Final",
        "tot_energy_mwh":1.0} for m in (7,8) for s in ("CA","WA")])

    # Form 923: raw worksheet cache with the original EIA headers
    os.makedirs(os.path.join(base,"form923"))
    months = [dt.date(2020,x,1).strftime("%B") for x in range(1,13)]
    rows = [[6099,"Hydro","CA","CISO","HY","WAT"],[286,"Gas","CA","CISO","CT","NG"]]
    columns = ["Plant Id","Plant Name","Plant State","Balancing\nAuthority Code",
        "Reported\nPrime Mover","Reported\nFuel Type Code"] \
        + [f"Quantity\n{x}" for x in months] + [f"Netgen\n{x}" for x in months]
    pd.DataFrame([x + ["1"]*12 + [str(10*(n+1))]*12 for n,x in enumerate(rows)],columns=columns) \
        .to_csv(os.path.join(base,"form923","2020-raw.csv.gz"),index=False,compression="gzip")

    # Form 930: API records cache (UTC hour-ending periods)
    hours = pd.date_range("2020-08-01 01:00","2020-09-01 00:00",freq="h")
    for route,column,codes in [("region-data","type",["D","NG","TI"]),
            ("fuel-type-data","fueltype",["NG","WAT"])]:
        os.makedirs(os.path.join(base,"form930",route))
        pd.DataFrame([{"period":x.strftime("%Y-%m-%dT%H"),"respondent":"CAL",column:c,"value":1.0}
            for x in hours for c in codes]).to_csv(
            os.path.join(base,"form930",route,"CAL-2020-08.csv.gz"),index=False,compression="gzip")

def test_conventions():
    """Test every form follows the public API convention without accessing EIA data"""
    # pylint: disable=too-many-locals,too-many-statements
    import inspect
    import tempfile
    from unittest import mock
    import pandas as pd
    import eia.form861m
    import eia.form861msales as form861msales
    from eia.form930 import _Form930Base
    errors = 0
    saved = (eia.base._cache_dir,form861msales._cache)
    forms = [Form860m,Form861m,Form861mSales,Form923,Form930,Form930Fuel]
    try:
        # signatures: year and month are the only positional arguments
        for form in forms:
            params = list(inspect.signature(form.__init__).parameters.values())[1:]
            positional = [x.name for x in params if x.kind == x.POSITIONAL_OR_KEYWORD]
            assert positional == ["year","month"], f"{form.__name__} positional arguments {positional}"
            names = [x.name for x in params]
            assert names[-2:] == ["raw","refresh"], f"{form.__name__} does not end with raw, refresh"

        with tempfile.TemporaryDirectory() as tmpdir, \
                mock.patch("eia.base.requests.get",side_effect=AssertionError("network accessed")), \
                mock.patch.object(_Form930Base,"respondents",staticmethod(lambda refresh=False:["CAL"])):
            eia.base.set_cache_dir(tmpdir)
            eia.form861m._cache.clear()
            _write_conventions_fixtures(tmpdir)
            august = pd.Timestamp("2020-08-01",tz="UTC")
            frames = {
                "Form860m": (Form860m(2020,8),["timestamp","plant","generator"],2),
                "Form861m": (Form861m(2020,8),["timestamp","state"],2),
                "Form861mSales": (Form861mSales(2020,8),["timestamp","state"],2),
                "Form923": (Form923(2020,8),["timestamp","state","ba","fuel"],2),
                "Form923 plant": (Form923(2020,8,by="plant",plants=6099),
                    ["timestamp","state","ba","plant","pm","fuel"],1),
                "Form930": (Form930(2020,8,respondent="CAL"),["timestamp"],744),
                "Form930Fuel": (Form930Fuel(2020,8,respondent="CAL",fuels="wat"),["timestamp"],744),
                }
            for name,(data,index,rows) in frames.items():
                assert list(data.index.names) == index, f"{name} index {list(data.index.names)}"
                assert len(data) == rows, f"{name} has {len(data)} rows, not {rows}"
                timestamps = data.index.get_level_values("timestamp")
                assert str(timestamps.tz) == "UTC", f"{name} timestamps are not UTC"
                assert timestamps.min() == august, f"{name} starts at {timestamps.min()}"
                bad = [x for x in data.columns if x != x.lower()]
                assert not bad, f"{name} columns are not lower case: {bad}"
                assert type(data.head()) is pd.DataFrame, f"{name}.head() is {type(data.head())}"
            assert frames["Form860m"][0].index[0][2] == "G1", "Form860m is not sorted by generator"
            assert frames["Form860m"][0]["nameplate_mw"].sum() == 12.5, "Form860m nameplate_mw"
            assert frames["Form923"][0]["gen_mwh"].sum() == 30, "Form923 gen_mwh"
            assert list(frames["Form930"][0].columns) == ["load_mw","generation_mw","interchange_mw"], \
                f"Form930 columns {list(frames['Form930'][0].columns)}"
            assert list(frames["Form930Fuel"][0].columns) == ["wat_mw"], \
                f"Form930Fuel columns {list(frames['Form930Fuel'][0].columns)}"

            # whole year
            assert len(Form861m(2020)) == 4, "Form861m month=None"
            assert len(Form923(2020)) == 24, "Form923 month=None"
            assert len(Form861mSales(2020)) == 4, "Form861mSales month=None"

            # raw data: default index, only the period selection applied
            raw = {
                "Form860m": Form860m(2020,8,raw=True),
                "Form861m": Form861m(2020,8,raw=True),
                "Form861mSales": Form861mSales(2020,8,raw=True),
                "Form923": Form923(2020,8,raw=True),
                "Form930": Form930(2020,8,respondent="CAL",raw=True),
                "Form930Fuel": Form930Fuel(2020,8,respondent="CAL",raw=True),
                }
            for name,data in raw.items():
                assert isinstance(data.index,pd.RangeIndex), f"{name} raw index is {type(data.index)}"
                assert len(data) > 0, f"{name} raw is empty"
            assert "Plant ID" in raw["Form860m"].columns, "Form860m raw renamed columns"
            assert "Netgen\nAugust" in raw["Form923"].columns, "Form923 raw is missing August"
            assert "Netgen\nJuly" not in raw["Form923"].columns, "Form923 raw includes other months"
            assert len(raw["Form930"]) == 744*3 and "period" in raw["Form930"].columns, "Form930 raw"
            assert len(raw["Form930Fuel"]) == 744*2, "Form930Fuel raw applied the fuels filter"
    except Exception as err:
        print(f"ERROR [eia.tests]: conventions --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("conventions ok.",file=sys.stderr,flush=True)
    finally:
        eia.base._cache_dir = saved[0]
        form861msales._cache = saved[1]
        eia.form861m._cache.clear()
    return errors

def test_cli_xlsx_timestamps():
    """Test CLI writes tz-aware timestamps to XLSX without accessing EIA data"""
    import tempfile
    import pandas as pd
    errors = 0
    class Stub(Form861m):
        """Frame with a tz-aware timestamp index"""
        # pylint: disable=super-init-not-called,unused-argument
        def __init__(self,year,month=None,*,raw=False,refresh=False):
            index = pd.MultiIndex.from_tuples([(pd.Timestamp("2020-08-01",tz="UTC"),"CA")],
                names=["timestamp","state"])
            pd.DataFrame.__init__(self,{"tot_mw":[1.0]},index=index)
    Stub.__init__.__annotations__.update(Form861m.__init__.__annotations__)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir,"out.xlsx")
            codes = _run_cli("distributed_generation",Stub,["-y","2020","-m","8","-o",output])
            assert codes == [cli.E_OK], f"xlsx output returned {codes=}"
            data = pd.read_excel(output)
            assert list(data.columns) == ["timestamp","state","tot_mw"], f"xlsx columns {list(data.columns)}"
            assert data["timestamp"].iloc[0] == pd.Timestamp("2020-08-01"), "xlsx timestamp"
    except Exception as err:
        print(f"ERROR [eia.tests]: cli xlsx timestamps --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("cli xlsx timestamps ok.",file=sys.stderr,flush=True)
    return errors

def test_hs861m_deprecated():
    """Test the deprecated HS861m class keeps its former interface without accessing EIA data"""
    import warnings
    import pandas as pd
    import eia.form861msales as form861msales
    from eia.hs861m import HS861m as module_hs861m
    errors = 0
    saved = form861msales._cache
    form861msales._cache = pd.DataFrame([{"year":2022,"month":m,"state":s,"status":"Final",
        "tot_energy_mwh":1.0} for m in (7,8) for s in ("CA","WA")])
    try:
        assert module_hs861m is eia.HS861m and issubclass(eia.HS861m,Form861mSales), \
            "HS861m is not the Form861mSales subclass"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            data = eia.HS861m(2022,8)
        assert any(issubclass(x.category,DeprecationWarning) and "Form861mSales" in str(x.message)
            and x.filename == __file__ for x in caught), \
            f"no DeprecationWarning at the caller ({[(str(x.message),x.filename) for x in caught]})"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore",DeprecationWarning)
            assert list(data.index.names) == ["state"] and len(data) == 2, \
                f"year+month got {data.index.names=}"
            assert data.equals(Form861mSales(2022,8).droplevel("timestamp")), "data differs"
            data = eia.HS861m(2022)
            assert list(data.index.names) == ["date","state"] and len(data) == 4, \
                f"year only got {data.index.names=}"
            raw = eia.HS861m(2022,8,False,True) # former positional refresh, raw
            assert len(raw) == 2 and "status" in raw.columns, "positional raw not accepted"
    except Exception as err:
        print(f"ERROR [eia.tests]: HS861m deprecated --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("HS861m deprecated ok.",file=sys.stderr,flush=True)
    finally:
        form861msales._cache = saved
    return errors

if __name__ == "__main__":

    tested = 0
    failed = 0
    for test in [globals()[x] for x in globals() if x.startswith("test_") and callable(globals()[x])]:
        if test() > 0:
            failed += 1
        tested += 1
    print(f"{tested=}, {failed=}")

    sys.exit(1 if failed else 0)
