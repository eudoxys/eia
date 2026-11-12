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
                    cli.main("region_hourly","--respondent","CAL","-y","2020","-m","8"),
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
