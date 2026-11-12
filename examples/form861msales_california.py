"""California retail electricity sales by sector from EIA Form 861m

Plots with matplotlib when it is installed, otherwise prints the data.
"""

import pandas as pd
from eia import Form861mSales

pd.options.display.width = None
pd.options.display.max_columns = None
pd.options.display.max_rows = None

result = pd.concat([Form861mSales(year) for year in range(2018,2023)])
values = result.xs("CA",level="state")[[f"{x}_energy_mwh" for x in ["ind","res","com"]]] / 1e6

try:
    import matplotlib.pyplot as plt
except ModuleNotFoundError:
    print(values)
else:
    values.plot(kind="area",figsize=(20,10))
    plt.grid()
    plt.xlabel("Month")
    plt.ylabel("Energy (TWh)")
    plt.title("California Electricity Consumption")
    plt.show()
