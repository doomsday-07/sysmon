.PHONY: build clean install-dev

build:
	pyinstaller --noconfirm sysmon.spec

clean:
	rm -rf build dist sysmon.egg-info

install-dev:
	pip install -e ".[dev]"
