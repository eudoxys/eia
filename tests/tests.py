"""Test EIA package modules"""
import sys
import datetime as dt
from eia.form860m import Form860m
from eia.form861m import Form861m

def test_form860m():
    """Test Form 860m data frame"""
    errors = 0
    for year in range(2015,dt.datetime.now().year):
        for month in range(1 if year > 2015 else 7,13):
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
    for year in range(2017,dt.datetime.now().year):
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


if __name__ == "__main__":

    tested = 0
    failed = 0
    for test in [globals()[x] for x in globals() if x.startswith("test_") and callable(globals()[x])]:
        if test() > 0:
            failed += 1
        tested += 1
    print(f"{tested=}, {failed=}")

    sys.exit(1 if failed else 0)
