"""Test EIA package modules"""
import os
import sys
import datetime as dt
from eia.form860m import Form860m
from eia.form923 import Form923
from eia.form930 import Form930, Form930Fuel
from eia.form861m import Form861m
from eia.hs861m import HS861m

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
