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

    eia distributed_generation --years 2020 --month 8

### Python code

    from eia import Form861m
    Form861m(year=2020,month=8)

## Issues

See https://github.com/eudoxys/eia/issues
