"""Sector shares of Washington small-scale solar output from EIA Form 861m

Plots with matplotlib when it is installed, otherwise prints the data.
"""

import pandas as pd
from eia import Form861m

pd.options.display.width = None
pd.options.display.max_columns = None
pd.options.display.max_rows = None

SECTORS = ["res","com","ind"]

result = pd.concat([Form861m(year) for year in range(2018,2023)]).xs("WA",level="state")
for sector in SECTORS:
    result[f"{sector}_share"] = result[f"{sector}_mwh"] / result["tot_mwh"]
shares = result[[f"{x}_share" for x in SECTORS]]

try:
    import matplotlib.pyplot as plt
except ModuleNotFoundError:
    print(shares)
else:
    shares.plot(kind="area")
    plt.ylabel("Share of output")
    plt.title("Washington small-scale solar output by sector")
    plt.show()
