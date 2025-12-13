[![validate](https://github.com/eudoxys/eia/actions/workflows/validate.yaml/badge.svg)](https://github.com/eudoxys/eia/actions/workflows/validate.yaml)

Access the following EIA Form data

  - Form 861: Distribution/small scale solar generation capacity and
    production by year and state

## Documentation

See https://www.eudoxys.com/eia

## Installation

    pip install git+https://github.com/eudoxys/eia

## Examples

### Command line

    eia --years 2020,2021 --states CA,WA -o f861.csv

### Python code

    from eia.form861 import Form861
    print(Form861(years=[2020,2021]))

## Issues

See https://github.com/eudoxys/eia/issues
