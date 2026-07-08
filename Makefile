.PHONY: build build-app build-deb clean install-dev

build:
	pyinstaller --onefile --name sysmon --strip --clean --noconfirm run.py

build-app: build
	bash scripts/build-app.sh

build-deb: build
	bash scripts/build-deb.sh

clean:
	rm -rf build dist sysmon.egg-info

install-dev:
	pip install -e ".[dev]"
