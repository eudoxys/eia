"""Planned generators from EIA Form 860m"""

import pandas as pd
from eia import Form860m

pd.options.display.width = None
pd.options.display.max_columns = None
pd.options.display.max_rows = None

print(Form860m(2025,9,subset="Planned"))
