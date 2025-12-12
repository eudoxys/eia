# eia

Access the following EIA Form data

  - Form 861: Distribution/small scale solar generation capacity and
    production by year and state

## Installation

    pip install git+https://github.com/eudoxys/eia

## Examples

    from eia.form861 import Form861
    print(Form861(years=[2020]))