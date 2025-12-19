# make documentation

PACKAGE=eia

SOURCE=$(wildcard $(PACKAGE)/*.py)
LOGO="https://github.com/eudoxys/.github/blob/main/eudoxys_banner.png?raw=true"

docs: $(SOURCE)
	pip install --upgrade pdoc
	pdoc $(SOURCE) -o $@ --logo $(LOGO) --mermaid
