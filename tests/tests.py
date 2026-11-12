"""Test EIA package modules"""
import os
import sys
import datetime as dt
from eia.form860m import Form860m
from eia.form923 import Form923
from eia.form930 import Form930, Form930Fuel
from eia.form861m import Form861m
from eia.hs861m import HS861m
from eia import cli
from eia.base import month_number

def test_cli_forms():
    """Test CLI subcommands map to the correct form class"""
    errors = 0
    expected = {
        "bulk_generation": Form860m,
        "customer_demand": HS861m,
        "distributed_generation": Form861m,
        "region_hourly": Form930,
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

def test_makeargs():
    """Test every form accepts command line options through makeargs"""
    errors = 0
    options = {"form":"region_hourly","year":"2020","month":"8","region":"CAL",
        "subset":None,"refresh":False,"raw":False,"output":None}
    try:
        for form in [Form860m,Form861m,HS861m,Form923,Form930,Form930Fuel]:
            assert hasattr(form,"makeargs"), f"{form.__name__} has no makeargs"
        args = Form930.makeargs(**options)
        assert args == {"region":"CAL","year":2020,"month":8,"refresh":False}, f"Form930 got {args=}"
        args = HS861m.makeargs(**options)
        assert args == {"year":2020,"month":8,"refresh":False,"raw":False}, f"HS861m got {args=}"
        args = Form860m.makeargs(**options)
        assert args["year"] == 2020 and args["month"] == 8, f"Form860m got {args=}"
        assert Form930.makeargs(month=None)["month"] is None, "month=None was not kept"
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
    """Test region_hourly passes region, year, and month to Form930 without accessing EIA data"""
    errors = 0
    saved = cli._FORMS["region_hourly"]
    called = {}
    class Stub(Form930):
        """Record constructor arguments"""
        # pylint: disable=super-init-not-called
        def __init__(self,region,year,month=None,*,refresh=False):
            called.update(region=region,year=year,month=month,refresh=refresh)
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
        assert called == {"region":"CAL","year":2020,"month":8,"refresh":False}, \
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
    saved = Form860m.CACHEDIR
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            Form860m.CACHEDIR = tmpdir
            cachefile = os.path.join(tmpdir,"form860_2020_08.xlsx")
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
        Form860m.CACHEDIR = saved
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

def test_hs861m():
    """Test HS 861m data frame"""
    errors = 0
    year = dt.datetime.now().year - 2
    for month in range(1,13):
        try:
            raw = HS861m(year,month,raw=True)
            data = HS861m(year,month,raw=False)
            assert len(data) > 0, f"no data"
        except Exception as err:
            print(f"ERROR [eia.tests]: HS861m({year=},{month=}) --> {err}",file=sys.stderr,flush=True)
            errors += 1
            raise
        else:
            print(f"HS861m({year=},{month=}) ok.",file=sys.stderr,flush=True)
    return errors

def test_hs861m_args():
    """Test HS 861m year/month coercion and selection without accessing EIA data"""
    import pandas as pd
    import eia.hs861m as hs861m
    errors = 0
    saved = hs861m._cache
    rows = [{"year":y,"month":m,"state":s,"status":"Final","tot_energy_mwh":1.0}
        for y in (2021,2022) for m in range(1,13) for s in ("CA","WA")]
    hs861m._cache = pd.DataFrame(rows)
    try:
        data = HS861m("2022","8")
        assert list(data.index.names) == ["state"] and len(data) == 2, f"year+month got {data.index.names=}, {len(data)=}"
        assert HS861m(2022,"Aug").equals(data), "month name not accepted"
        data = HS861m(2022)
        assert len(data) == 24, f"year only got {len(data)=}"
        assert set(data.index.get_level_values("date").year) == {2022}, "year filter not applied"
        assert len(HS861m()) == 48, "year=None did not return all years"
        assert len(HS861m(month=3)) == 4, "month only did not select that month in every year"
        assert cli.main("customer_demand","-y","2022","-m","8") == cli.E_OK, "CLI failed"
        for year,month in [("abc",1),(2022,13),(2022,"Foo"),(1800,1),(2019,1)]:
            try:
                HS861m(year,month)
            except ValueError:
                pass
            else:
                raise AssertionError(f"HS861m({year=},{month=}) did not raise ValueError")
    except Exception as err:
        print(f"ERROR [eia.tests]: HS861m arguments --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("HS861m arguments ok.",file=sys.stderr,flush=True)
    finally:
        hs861m._cache = saved
    return errors

def test_hs861m_cachedir():
    """Test HS 861m honours CACHEDIR without accessing EIA data"""
    import tempfile
    import pandas as pd
    import eia.hs861m as hs861m
    from cache import Cache
    errors = 0
    saved = (hs861m._cache,HS861m.CACHEDIR,Cache.CACHEDIR)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            pathname = os.path.join(tmpdir,"eia","0","hs861m.csv")
            os.makedirs(os.path.dirname(pathname))
            pd.DataFrame([{"year":2022,"month":8,"state":"CA","status":"Final",
                "tot_energy_mwh":1.0}]).to_csv(pathname,index=False)
            hs861m._cache = None
            HS861m.CACHEDIR = tmpdir
            data = HS861m(2022,8)
            assert len(data) == 1, f"cache file in CACHEDIR not used ({len(data)=})"
            assert Cache.CACHEDIR == saved[2], "default Cache.CACHEDIR was changed"
    except Exception as err:
        print(f"ERROR [eia.tests]: HS861m CACHEDIR --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("HS861m CACHEDIR ok.",file=sys.stderr,flush=True)
    finally:
        hs861m._cache,HS861m.CACHEDIR,Cache.CACHEDIR = saved
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
    if "EIA_API_KEY" not in os.environ and not os.path.exists(os.path.join(os.environ["HOME"],".eia","api_key")):
        print("Form930 skipped (no EIA API key)",file=sys.stderr,flush=True)
        return 0
    errors = 0
    try:
        for year,month in [(2018,1),(2018,7)]:
            data = Form930("CISO",year,month)
            assert len(data) == 744, f"{len(data)=} hours in {year}-{month}"
            assert data.timestamp.iloc[0] == dt.datetime(year,month,1,tzinfo=dt.timezone.utc), "invalid first hour"
        fuel = Form930Fuel("CISO",2018,7)
        assert len(fuel) == 744, f"{len(fuel)=} hours"
        assert "SUN_MW" in fuel.columns, "no solar data"
        total = fuel.drop("timestamp",axis=1).sum(axis=1,min_count=1)
        error = (total - data.generation_MW).abs().median()
        assert error < 0.01*data.generation_MW.median(), f"fuel total differs from net generation by {error=}"
    except Exception as err:
        print(f"ERROR [eia.tests]: Form930 --> {err}",file=sys.stderr,flush=True)
        errors += 1
        raise
    else:
        print("Form930 ok.",file=sys.stderr,flush=True)
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
