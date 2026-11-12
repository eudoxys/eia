"""Hourly balancing authority data and fuel mix from EIA Form 930

Requires an EIA API key (see the package documentation).
"""

import pandas as pd
from eia import Form930, Form930Fuel

pd.options.display.width = None
pd.options.display.max_columns = None

print(Form930(2020,8,respondent="CAL"))
print(Form930Fuel(2020,8,respondent="BPAT"))
