---
name: mediarchiver-batch-rename
description: 在本仓库中生成、审查或修订批次专用媒体重命名脚本时使用；先检查原始 exiftool/ffprobe 元数据，脚本默认只预览。
---

# mediarchiver 批次重命名脚本

当用户要求生成、审查或修订批次专用媒体重命名脚本时，使用此 skill。

推荐工作模式：

- `mediarchiver` 提供稳定的元数据检查能力和安全的重命名基础能力。
- AI 只针对一个具体素材批次进行探索，并为该批次编写一个具体的 Python 脚本。
- 生成的脚本就是用户实际运行的命令；脚本必须默认只预览，不修改文件。

## 必需流程

1. 设计脚本前，先检查源批次。

   直接使用原始 `exiftool` 和 `ffprobe` 输出。在批次规则尚未理解前，不要先引入 `mediarchiver` 抽象层。

   先列出代表性文件；除非目录明显混杂，否则检查 1-3 个样本：

   ```bash
   find <source> -maxdepth 1 -type f | sort | head -50
   exiftool -json -G -n <sample-file-1> <sample-file-2> > inspect-exiftool.json
   ffprobe -v error -print_format json -show_format -show_streams <sample-video> > inspect-ffprobe.json
   ```

   如果需要检查多个视频样本，为每个文件分别写出一份 `ffprobe` 输出，或用 JSONL 合并记录并包含源文件名。

2. 不要编造元数据。

   不要猜测拍摄时间、设备、codec、帧率、分辨率或原始 ID。只能使用 `inspect` 发现的元数据、文件名解析结果，或用户明确提供的信息。

3. 脚本默认必须只预览。

   实际重命名文件必须要求显式传入 `--apply` 标志，并获得用户授权。

4. 脚本应保持批次专用。

   除非用户明确要求将规则产品化，否则不要把 DJI、GoPro、iPhone、Sony 或其他设备专用假设强行加入 `mediarchiver` 核心通用规则。

5. 代码标识符使用英文。

   生成 Python 代码时，函数名、变量名、类名、参数名、CLI flag 和状态值应使用英文；解释性注释可以使用中文。

## 脚本文件命名

生成的脚本应放在：

```text
rename/
```

生成的脚本应命名为：

```text
rename/rename_<batch_or_device>.py
```

示例：

```text
rename/rename_dji_pocket4p.py
rename/rename_iphone_trip_202607.py
rename/rename_gopro_skiing.py
rename/rename_scanned_family_album.py
```

使用 lowercase snake_case。名称应足够明确，能够识别批次或来源规则。

如果脚本包含 shebang 且具有可执行权限，可以直接运行：

```bash
./rename/rename_dji_pocket4p.py <source>
./rename/rename_dji_pocket4p.py <source> --apply
```

也必须支持通过 Python 运行：

```bash
python rename/rename_dji_pocket4p.py <source>
python rename/rename_dji_pocket4p.py <source> --apply
```

## 必需脚本命令

每个生成脚本都必须支持：

```bash
python rename/rename_xxx.py <source>
python rename/rename_xxx.py <source> --apply
python rename/rename_xxx.py <source> --output-plan rename-plan.json
```

推荐的可选参数：

```bash
--workers N
--include-formatted
--verbose
```

行为要求：

- 未传入 `--apply`：只打印预览，不执行重命名。
- 传入 `--apply`：完成冲突检查后执行计划中的重命名。
- 传入 `--output-plan`：将计划操作写入 JSON 文件，便于审查或复用。

## 安全要求

生成脚本必须：

- 绝不覆盖已有文件。
- 将重复目标路径标记为 `conflict`。
- 将缺失必需元数据的文件标记为 `skipped` 或 `invalid`。
- 保留原始扩展名，除非用户明确要求规范化扩展名。
- 将操作限制在用户提供的源目录内，除非用户明确要求其他行为。
- 避免在重命名脚本中使用 `rm`、`cp`、`rsync --remove-source-files`，或任何归档/移动行为。
- 避免基于通配符的破坏性操作。
- 避免隐藏式重命名逻辑，例如只在不透明 shell 循环内部计算目标文件名。

如果生成 shell artifact，只能使用已审查的显式操作，并包含：

```bash
#!/usr/bin/env bash
set -euo pipefail
```

路径必须进行 shell quote，并使用 `mv -n` 或等价的 no-overwrite 行为。

## 输出要求

预览输出必须清楚展示源文件和目标文件：

```text
DJI_20260718182801_0023_D.MP4
  -> 20260718-182801_MDJI_4K-29.97FPS-HEVC_0023.MP4
```

每次运行都必须包含汇总：

```text
ready: 42
skipped: 3
conflict: 1
invalid: 0
```

最终回复必须明确说明是否已经执行实际重命名。

## 文件名规则

用户请求的命名规则优先。

如果用户没有指定完整规则，推荐使用以下结构：

```text
YYYYMMDD-HHMMSS_DeviceOrUnit_TechTags_OriginalId.ext
```

规则：

- `YYYYMMDD-HHMMSS` 必须来自可靠元数据或用户明确说明。
- `DeviceOrUnit` 必须来自元数据、现有项目约定或用户明确说明。
- `TechTags` 只应包含元数据支持的字段，例如分辨率、FPS、codec、HDR/Log 标记。
- `OriginalId` 优先来自原始文件名；如果不可用，使用稳定生成的 ID，并说明派生方式。
- 不要生成重复目标文件名。
- 已存在的目标文件必须视为冲突，而不是覆盖目标。

## 验证清单

在将生成脚本交付为可用前，先验证或要求用户验证：

```bash
python rename/rename_xxx.py <source>
python rename/rename_xxx.py <source> --output-plan rename-plan.json
```

如果生成了 shell script：

```bash
bash -n rename.sh
```

如果生成了 mediarchiver rename plan：

```bash
mediarchiver rename --plan rename-plan.json --dry-run
```

审查重点：

- ready / skipped / conflict / invalid 计数
- 重复目标路径检测
- 已存在目标路径检测
- 每个必需文件名字段的元数据来源
- 是否执行过任何真实重命名

除非 `--apply` 命令确实运行过且结果已被观察到，否则不要声称批次已经被重命名。
