set dotenv-load := false
export UV_CACHE_DIR := env_var_or_default("UV_CACHE_DIR", ".uv-cache")
export UV_DEFAULT_INDEX := env_var_or_default("UV_DEFAULT_INDEX", "https://pypi.tuna.tsinghua.edu.cn/simple")
export PYINSTALLER_CONFIG_DIR := env_var_or_default("PYINSTALLER_CONFIG_DIR", "build/pyinstaller-cache")

default:
    @just --list

setup:
    uv sync --extra dev

lock:
    uv lock

lint:
    uv run --no-sync ruff check mediarchiver rename

test:
    if [ -d tests ]; then uv run --no-sync pytest; else echo "No tests directory; skipping pytest."; fi

check: lint test

smoke:
    uv run --no-sync python -m mediarchiver --help
    uv run --no-sync python -m mediarchiver rename --list-rules

build:
    uv build

binary:
    uv run --extra dev pyinstaller --clean --noconfirm --onefile --name mediarchiver --hidden-import zlib --collect-submodules mediarchiver.rename.rules --distpath dist/bin --workpath build/pyinstaller --specpath build/pyinstaller mediarchiver/__main__.py

smoke-binary: binary
    ./dist/bin/mediarchiver --help
    ./dist/bin/mediarchiver rename --list-rules

install-local: binary
    local_bin="${LOCAL_BIN:-$HOME/.local/bin}"; \
    mkdir -p "$local_bin"; \
    install -m 755 dist/bin/mediarchiver "$local_bin/mediarchiver"; \
    "$local_bin/mediarchiver" --help >/dev/null; \
    echo "Installed: $local_bin/mediarchiver"; \
    case ":$PATH:" in *":$local_bin:"*) ;; *) echo "Add to PATH: export PATH=\"$local_bin:$PATH\"";; esac

uninstall-local:
    local_bin="${LOCAL_BIN:-$HOME/.local/bin}"; \
    rm -f "$local_bin/mediarchiver"; \
    echo "Removed: $local_bin/mediarchiver"

clean:
    rm -rf build dist *.egg-info .pytest_cache .ruff_cache .uv-cache htmlcov .coverage
