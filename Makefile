# make documentation (requires pdoc: pip install pdoc)

PACKAGE=eia

SOURCE=$(wildcard $(PACKAGE)/*.py)
LOGO="https://github.com/eudoxys/.github/blob/main/eudoxys_banner.png?raw=true"
LINK="https://www.eudoxys.com/"

docs: $(SOURCE)
	pdoc $(SOURCE) -o $@ --logo $(LOGO) --mermaid --logo-link $(LINK)
