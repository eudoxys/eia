"""Form 861m sales and revenue tests (including the deprecated HS861m)"""
import os
import datetime as dt
import pandas as pd
import pytest
import eia
from eia.form861msales import Form861mSales
from eia.hs861m import HS861m
import samples

def test_workbook(fake_get,cache_dir):
    """The downloaded workbook is parsed, renamed, and cached"""
    content = samples.form861msales_workbook([
        (2022,8,"CA","Final",100.0,1000.0,10,10.004),
        (2022,8,"WA","Final",50.0,None,5,8.0),
        ])
    calls = fake_get(lambda url,params: (200,content))
    data = Form861mSales(2022,8)
    assert [x[0] for x in calls] == [Form861mSales.SOURCE]
    assert list(data.index.names) == ["timestamp","state"]
    assert list(data.columns) == ["res_revenue_kusd","res_energy_mwh","res_customers_qty",
        "res_price_cpkwh"]
    assert data.loc[(pd.Timestamp("2022-08-01",tz="UTC"),"CA")].tolist() == [100,1000,10,10.0]
    assert data.loc[(pd.Timestamp("2022-08-01",tz="UTC"),"WA"),"res_energy_mwh"] == 0, \
        "missing value is not 0"
    assert os.path.exists(os.path.join(cache_dir,"eia","0","hs861m.csv")), "table not cached"

def test_period_selection(sales):
    """year and month (int, str, or name) select the period"""
    sales(samples.sales_table())
    data = Form861mSales("2022","8")
    assert list(data.index.names) == ["timestamp","state"] and len(data) == 2
    assert Form861mSales(2022,"Aug").equals(data)
    data = Form861mSales(2022)
    assert len(data) == 24
    assert set(data.index.get_level_values("timestamp").year) == {2022}
    assert len(Form861mSales()) == 48, "year=None did not return all years"
    assert len(Form861mSales(month=3)) == 4, "month only did not select that month in every year"

def test_raw(sales):
    """raw=True applies the period selection and keeps the EIA columns"""
    sales(samples.sales_table())
    raw = Form861mSales(2022,8,raw=True)
    assert len(raw) == 2 and set(raw["month"]) == {8}
    assert list(raw.columns[:4]) == ["year","month","state","status"]

@pytest.mark.parametrize("year,month",[("abc",1),(2022,13),(2022,"Foo"),(1800,1),(2019,1)])
def test_invalid_period(sales,year,month):
    """Invalid or unavailable periods raise ValueError"""
    sales(samples.sales_table())
    with pytest.raises(ValueError):
        Form861mSales(year,month)

def test_cache_dir(cache_dir,no_network): # pylint: disable=unused-argument
    """The table is read from the eia cache folder, not the cache package default"""
    from cache import Cache # pylint: disable=import-outside-toplevel
    default = Cache.CACHEDIR
    pathname = os.path.join(cache_dir,"eia","0","hs861m.csv")
    os.makedirs(os.path.dirname(pathname))
    samples.sales_table(years=[2022],months=[8],states=["CA"]).to_csv(pathname,index=False)
    assert len(Form861mSales(2022,8)) == 1
    assert Cache.CACHEDIR == default, "default Cache.CACHEDIR was changed"

def test_hs861m_deprecated(sales):
    """HS861m keeps its former interface and warns at the caller"""
    sales(samples.sales_table(years=[2022],months=[7,8]))
    assert HS861m is eia.HS861m and issubclass(HS861m,Form861mSales)
    with pytest.warns(DeprecationWarning,match="Form861mSales") as caught:
        data = HS861m(2022,8)
    assert any(x.filename == __file__ for x in caught), "warning not reported at the caller"
    assert list(data.index.names) == ["state"] and len(data) == 2
    assert data.equals(Form861mSales(2022,8).droplevel("timestamp"))
    with pytest.warns(DeprecationWarning):
        data = HS861m(2022)
        raw = HS861m(2022,8,False,True) # former positional refresh, raw
    assert list(data.index.names) == ["date","state"] and len(data) == 4
    assert len(raw) == 2 and "status" in raw.columns

@pytest.mark.network
@pytest.mark.parametrize("month",range(1,13))
def test_live(month):
    """Form 861m sales data from EIA"""
    year = dt.datetime.now().year - 2
    raw = Form861mSales(year,month,raw=True)
    assert len(raw) > 0 and set(raw["month"]) == {month}
    data = Form861mSales(year,month)
    assert list(data.index.names) == ["timestamp","state"]
    assert {"res_energy_mwh","com_energy_mwh","ind_energy_mwh","tot_energy_mwh",
        "res_customers_qty","res_price_cpkwh","tot_revenue_kusd"} <= set(data.columns)
    assert {"CA","TX"} <= set(data.index.get_level_values("state"))
    assert (data["tot_energy_mwh"] > 0).all()
