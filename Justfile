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
    uv run --no-sync ruff check mediarchiver

check: lint

smoke:
    uv run --no-sync python -m mediarchiver --help
    uv run --no-sync python -m mediarchiver rename --list-rules
    uv run --no-sync python -m mediarchiver archive --help

build:
    UV_CACHE_DIR="${TMPDIR:-/tmp}/mediarchiver-uv-cache" uv build

install-wheel: build
    uv tool install --reinstall --force dist/mediarchiver-*.whl

uninstall-wheel:
    uv tool uninstall mediarchiver

binary:
    rm -rf build/pyinstaller dist/bin
    uv run --extra dev pyinstaller --clean --noconfirm --onefile --name mediarchiver --hidden-import zlib --exclude-module multiprocessing --collect-submodules mediarchiver.rename.rules --distpath dist/bin --workpath build/pyinstaller --specpath build/pyinstaller mediarchiver/__main__.py

smoke-binary: binary
    ./dist/bin/mediarchiver --help
    ./dist/bin/mediarchiver rename --list-rules

install-binary: binary
    local_bin="${LOCAL_BIN:-$HOME/.local/bin}"; \
    mkdir -p "$local_bin"; \
    install -m 755 dist/bin/mediarchiver "$local_bin/mediarchiver"; \
    "$local_bin/mediarchiver" --help >/dev/null; \
    echo "Installed: $local_bin/mediarchiver"; \
    case ":$PATH:" in *":$local_bin:"*) ;; *) echo "Add to PATH: export PATH=\"$local_bin:$PATH\"";; esac

uninstall-binary:
    local_bin="${LOCAL_BIN:-$HOME/.local/bin}"; \
    rm -f "$local_bin/mediarchiver"; \
    echo "Removed: $local_bin/mediarchiver"

clean:
    rm -rf build dist *.egg-info .pytest_cache .ruff_cache .uv-cache
    find . -path ./.venv -prune -o -type d -name __pycache__ -prune -exec rm -rf {} +
    find . -path ./.venv -prune -o -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
