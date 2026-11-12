"""Monthly net generation by balancing authority and by plant from EIA Form 923"""

import pandas as pd
from eia import Form923

pd.options.display.width = None
pd.options.display.max_columns = None

print(Form923(2020,8,fuels=["NG","WAT"],bas="CISO"))
print(Form923(2020,8,states="CA",fuels="WAT",by="plant"))
