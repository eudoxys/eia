[![validate](https://github.com/eudoxys/eia/actions/workflows/validate.yaml/badge.svg)](https://github.com/eudoxys/eia/actions/workflows/validate.yaml)

Access the following EIA Form data

  - Form 860m: Bulk system generation monthly capacity and production

  - Form 861m: Distributed/small scale month generation capacity and
    production

  - HS 861: Customer monthly energy consumption

  - Form 923: Monthly net generation by state, balancing authority, and fuel,
    or by plant, prime mover, and fuel

  - Form 930: Hourly load, net generation, and interchange by balancing
    authority or region, and hourly net generation by energy source

## Documentation

See https://www.eudoxys.com/eia

## Installation

    pip install git+https://github.com/eudoxys/eia

## Examples

### Command line

    eia distributed_generation --year 2020 --month 8

### Python code

    from eia import Form861m
    Form861m(year=2020,month=8)

Monthly net generation from natural gas and hydro in the CAISO balancing
authority for August 2020 (Form 923)

    from eia import Form923
    Form923(2020,8,fuels=["NG","WAT"],bas="CISO")

Plant-level monthly net generation from hydro plants in California for August
2020 (Form 923)

    from eia import Form923
    Form923(2020,8,states="CA",fuels="WAT",by="plant")

Hourly load, net generation, and interchange for California in August 2020
(Form 930)

    from eia import Form930
    Form930("CAL",2020,8)

Hourly net generation by energy source for the Bonneville Power Administration
in August 2020 (Form 930)

    from eia import Form930Fuel
    Form930Fuel("BPAT",2020,8)

Form 923 and Form 930 data are currently available from Python only; the
command line tool does not yet support them.

## Notes

- **Form 923** covers 2008 onward. Recent years are preliminary until EIA
  finalizes them. Net generation can be negative (e.g., pumped storage and
  batteries). Rows for plant `99999` are EIA's state-fuel level increment
  estimates; exclude them with `increments=False`.

- **Form 930** requires an EIA Open Data API key. Register at
  https://www.eia.gov/opendata/register.php, then store the key in the
  environment variable `EIA_API_KEY` or in the file `~/.eia/api_key`.
  Valid respondent codes are listed by `Form930.respondents()`.

- **Form 930 time convention:** timestamps are UTC and mark the *beginning*
  of the hour, so the value at `2020-08-01 00:00:00+00:00` covers 00:00 to
  01:00 UTC. Load, generation, and interchange data start in July 2015; data
  by energy source start in July 2018.

- Downloaded data are cached locally; pass `refresh=True` (or `--refresh` on
  the command line) to download again.

## Claude Code skill

The file `.claude/skills/eia/SKILL.md` documents form selection, returned
data frame structure, caching, and current command-line limitations for use
with Claude Code. Claude Code loads it automatically when run from a clone of
this repository. To make it available in other projects, copy the folder:

    mkdir -p ~/.claude/skills
    cp -r .claude/skills/eia ~/.claude/skills/

## Issues

See https://github.com/eudoxys/eia/issues
