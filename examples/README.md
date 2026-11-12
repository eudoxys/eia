# Examples

Short scripts showing how to use `eia`. They download data from EIA on first
run (Form 930 examples need an EIA API key; see the package documentation).

Some examples plot with [matplotlib](https://matplotlib.org/), which is not
a dependency of `eia`; install it with `pip install matplotlib`. Without it,
those examples print the data instead.

| Script | Shows |
| ------ | ----- |
| `form860m_planned.py` | Planned generators from Form 860m |
| `form861m_solar_share.py` | Sector shares of Washington small-scale solar output (Form 861m) |
| `form861msales_california.py` | California retail electricity sales by sector (Form 861m sales) |
| `form923_generation.py` | Monthly net generation by BA and by plant (Form 923) |
| `form930_hourly.py` | Hourly BA data and fuel mix (Form 930) |
