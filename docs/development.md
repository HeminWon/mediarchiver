# 开发说明

## Python

项目固定使用 Python 3.14：

```text
.python-version
pyproject.toml
uv.lock
```

使用 `uv` 创建和管理本地开发环境：

```bash
uv sync --extra dev
uv run --no-sync python -V
uv run --no-sync python -m mediarchiver --version
```

## 常用命令

```bash
just setup
just check
just smoke
just install-wheel
just uninstall-wheel
just binary
just install-binary
just uninstall-binary
```

`just check` 目前只运行 lint；仓库暂时没有配置测试套件。

## 构建

构建 Python 分发产物：

```bash
just build
```

构建 wheel，并以隔离的 `uv tool` 形式安装：

```bash
just install-wheel
mediarchiver --version
```

该 recipe 使用 `uv tool install --reinstall --force`，方便本地开发时干净替换项目的命令行脚本。

卸载 `uv tool`：

```bash
just uninstall-wheel
```

构建本地单文件可执行程序：

```bash
just binary
./dist/bin/mediarchiver --help
```

安装本地二进制：

```bash
just install-binary
mediarchiver --version
```

默认安装到：

```text
~/.local/bin/mediarchiver
```

需要时可以覆盖安装目标：

```bash
LOCAL_BIN=/usr/local/bin just install-binary
```

除非你正在刻意测试 `PATH` 优先级，否则不建议长期同时保留 `uv tool` 和复制安装的二进制。`which mediarchiver` 可以查看实际优先运行的是哪一个。

## 包索引

`just` recipes 默认使用仓库本地的 uv cache 和 PyPI 镜像：

```text
UV_CACHE_DIR=.uv-cache
UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
```

`just build` 会在源码树外使用临时 uv cache，避免 wheel 和 sdist 构建时提示 cache 文件位于分发根目录内。

需要时可以覆盖包索引：

```bash
UV_DEFAULT_INDEX=https://pypi.org/simple just binary
```

## GitHub Actions

CI 在 Linux 和 macOS 上使用 Python 3.14：

```text
.github/workflows/ci.yml
```

发布构建配置：

```text
.github/workflows/release.yml
```

发布 workflow 会构建：

- wheel 和 sdist
- Linux 单文件二进制
- macOS 单文件二进制

推荐的安装产物是 wheel：

```bash
just install-wheel
```

PyInstaller 二进制只是补充分发产物，适合偏好下载后直接运行的用户。

二进制构建使用 PyInstaller，并包含：

```bash
--exclude-module multiprocessing
```

除非明确重新引入 multiprocessing，否则保留这个参数。它可以避免 PyInstaller onefile 运行时与临时 `_MEI...` 目录相关的错误。

## 重命名规则

Rename 是基于规则的。当前规则位于：

```text
mediarchiver/rename/rules/
```

预览时，公开命令会自动应用所有已注册规则：

```bash
mediarchiver rename <source>
```

查看当前支持的规则：

```bash
mediarchiver rename --list-rules
```

新增规则时，把设备相关逻辑保留在对应 rule package 内。不要把品牌或机型行为塞进通用的 rename service。

规则粒度应该按“处理行为差异”划分，而不是单纯按设备分类机械拆分。当设备需要不同的匹配逻辑、元数据提取方式、命名规则、技术标签或 sidecar 配对方式时，应该拆成不同 rule；如果行为一致，并且设备名可以从 metadata 中获得，则保持一个更宽的 rule。比如 `apple:iphone` 可以覆盖多个 iPhone 型号，因为命名行为共享；而 `dji:pocket4p` 和 `sony:a7m4` 适合保持机型级 rule，因为它们的 metadata 字段、技术标签和 sidecar 约定不同。

## 归档

Archive 逻辑位于：

```text
mediarchiver/archive/
```

Sidecar 匹配规则位于：

```text
mediarchiver/archive/sidecars.py
```

Archive 应保持保守：

- 忽略 `.DS_Store` 等系统文件
- 只直接归档支持的媒体文件
- 只有当 sidecar 能与支持的媒体文件配对时才归档 sidecar
- 默认只预览；只有传入 `--apply` 时才移动文件

## 验证

发布或交付改动前运行：

```bash
just check
just smoke
just binary
./dist/bin/mediarchiver --version
./dist/bin/mediarchiver rename --list-rules
./dist/bin/mediarchiver archive --help
```
