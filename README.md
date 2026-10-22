[![validate](https://github.com/eudoxys/eia/actions/workflows/validate.yaml/badge.svg)](https://github.com/eudoxys/eia/actions/workflows/validate.yaml)

Access the following EIA Form data

  - Form 860m: Bulk system generation monthly capacity and production

  - Form 861m: Distributed/small scale month generation capacity and
    production

  - HS 861: Customer monthly energy consumption

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

## Claude Code skill

The file `.claude/skills/eia/SKILL.md` documents form selection, returned
data frame structure, caching, and current command-line limitations for use
with Claude Code. Claude Code loads it automatically when run from a clone of
this repository. To make it available in other projects, copy the folder:

    mkdir -p ~/.claude/skills
    cp -r .claude/skills/eia ~/.claude/skills/

## Issues

See https://github.com/eudoxys/eia/issues
