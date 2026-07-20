# 基础功能说明

`mediarchiver` 是一个用于整理照片和视频素材的 Python 命令行工具，主要解决两个问题：

- 按拍摄时间、设备信息等规则重命名媒体文件
- 按年份和季度归档媒体文件到对应目录

## 项目用途

这个项目适合用于个人媒体资料整理，例如：

- 整理手机、相机、无人机导出的照片和视频
- 统一文件命名规则，方便后续检索
- 将杂乱素材按时间归档到清晰的目录结构中

## 核心功能

### 1. 媒体文件重命名

重命名功能由 `mediarchiver/rename/` 模块提供。

程序会读取媒体文件的元数据，并尝试生成统一格式的新文件名。重命名时会综合以下信息：

- 拍摄时间
- 具体设备或素材来源
- 品牌相关标记（例如 iPhone 自拍、iPhone 截屏）
- 视频分辨率
- 视频帧率
- 视频编码信息
- 原始文件编号或内容指纹

生成后的文件名使用以下格式：

```text
YYYYMMDD-HHMMSS_DeviceOrUnit_TechTags_OriginalId.ext
```

其中通常包含：

- `20230512-114211`：格式化后的拍摄时间
- `DeviceOrUnit`：具体设备或素材来源
- `TechTags`：可选的媒体技术标签
- `OriginalId`：稳定标识，用于回链原始素材
- `.HEIC`：原始扩展名

示例：

```text
20240102-030405_iPhone15Pro-Selfie_1234.HEIC
20240102-030405_iPhone15Pro-Screenshot_1234.PNG
20240102-030405_iPhone15Pro_FHD-29.97FPS-AVC_7657.MOV
20240101-120000_MSON_4K-25FPS-AVC_0212.MP4
20240101-120000_MSON_4K-25FPS-AVC_0212M01.XML
20240102-030405_MSON_FHD-25FPS-AVC_4827.MOV
```

字段说明：

| 字段 | 含义 |
|---|---|
| `YYYYMMDD-HHMMSS` | 从媒体元数据读取的拍摄时间 |
| `DeviceOrUnit` | 设备或素材来源，例如 `iPhone15Pro`、`iPhone15Pro-Selfie`、`iPhone15Pro-Screenshot`、`MSON`、`DJI` |
| `TechTags` | 可选技术标签，例如分辨率、帧率、Log/HDR 标记、视频编码；无技术标签时会省略 |
| `OriginalId` | 稳定标识，用于判断或追踪是否来自同一份原始素材 |
| `ext` | 原始文件扩展名 |

`OriginalId` 的生成顺序：

1. 优先使用原始文件名中的 4 位编号，例如 `IMG_1234`、`C0212`、`DJI_0008`。
2. 如果文件名中没有这类编号，则根据内容指纹生成稳定的 4 位数字编号。

内容指纹用于在缺少原始编号时提供稳定标识。小文件会完整 hash；
大视频文件不会完整读取，而是结合文件大小以及文件开头和结尾的采样内容生成指纹。
文件名中会统一表现为 4 位数字；`rename-plan.json` 的字段详情会记录
`original_id_source`，用于区分编号来自原始文件名还是内容指纹。

预览阶段生成的 `rename-plan.json` 会记录每个文件的字段解析详情：

- `required`：必需字段，包括拍摄时间、设备或素材来源、稳定标识
- `optional`：可选字段，包括技术标签以及缺失的可选字段列表
- `missing_required`：缺失的必需字段；这类文件会被跳过
- sidecar 文件会额外记录 `sidecar_rule` 和 `paired_with`，用于说明它来自哪条品牌规则，以及跟随哪一个主文件

控制台的 plan 汇总也会显示可选字段缺失数量，例如：

```text
- optional missing: log=12, codec=3
```

### 2. Live Photo 关联处理

项目对部分 Live Photo 文件做了特殊处理。

- 如果识别到 `.mov` 属于 Live Photo 视频
- 会尝试查找同编号的图片文件
- 然后复用图片侧的命名信息生成视频文件名

这样可以让同一组 Live Photo 的图片和视频命名更加一致。

### 3. 媒体文件归档

归档功能由 `mediarchiver/archive/` 模块提供。

程序会读取文件中的拍摄时间，然后按“年份 / 季度”的目录结构移动文件，例如：

```text
2023/Q1/
2023/Q2/
2024/Q4/
```

如果文件时间可识别，程序会：

- 提取拍摄年份
- 根据月份计算季度
- 自动创建目标目录
- 将文件移动到对应目录中

## 元数据来源

项目主要依赖外部工具读取媒体信息：

- `exiftool`：读取图片和视频的 Exif / 元数据
- `ffprobe`：读取视频流信息，例如分辨率、帧率、编码

程序会优先从文件元数据中提取拍摄时间，例如：

- `DateTimeOriginal`
- `CreateDate`
- `CreationDate`
- `MediaCreateDate`

如果无法获取有效时间，相关文件通常会被跳过，并写入日志。

## 使用方式

### 重命名预览

默认执行重命名时，会先扫描目录并生成 `rename-plan.json`，不会直接改名：

```bash
python3 -m mediarchiver rename <source>
```

### 执行实际重命名

传入 `--apply` 后才会真正修改文件名：

```bash
python3 -m mediarchiver rename <source> --apply
```

### 重命名 dry-run

如需走完整规则但不真正改名，可传入：

```bash
python3 -m mediarchiver rename <source> --apply --dry-run
```

### 控制并发读取数

重命名和归档现在支持通过 `--workers` 控制元数据预读取并发度。

```bash
python3 -m mediarchiver rename <source> --workers 2
python3 -m mediarchiver archive <source> --to <target> --workers 2
```

说明：

- `--workers` 只影响 `exiftool` 和 `ffprobe` 的并发读取
- 实际 `rename`、`move`、日志写入仍是串行执行，用来避免冲突和顺序问题
- 默认不传时会自动选择并发度，依据 CPU 数量和待处理文件数决定
- 建议值：笔记本或机械盘先用 `2`，本地 SSD 批量处理可尝试 `3` 到 `4`
- 首次处理陌生目录时，建议优先搭配 `--dry-run --workers 2` 观察结果

### 包含已格式化文件

默认会跳过已经符合目标格式的文件名。如果希望这些文件也参与扫描，可传入：

```bash
python3 -m mediarchiver rename <source> --all
```

### 使用已有 plan 与导出 shell

默认会在源目录生成 `rename-plan.json`。如果需要，也可以基于已有 plan 执行、预演或导出 shell：

```bash
python3 -m mediarchiver rename <source> --shell
python3 -m mediarchiver rename --plan rename-plan.json
python3 -m mediarchiver rename --plan rename-plan.json --apply
python3 -m mediarchiver rename --plan rename-plan.json --dry-run
python3 -m mediarchiver rename --plan rename-plan.json --shell
```

### AI 生成批次脚本的推荐流程

对于默认规则无法很好覆盖的素材批次，推荐使用 AI 生成专用 Python 脚本，而不是继续扩展核心通用规则：

```bash
exiftool -json -G -n <sample-file> > inspect-exiftool.json
ffprobe -v error -print_format json -show_format -show_streams <sample-video> > inspect-ffprobe.json
python rename/rename_dji_pocket4p.py <source>
python rename/rename_dji_pocket4p.py <source> --apply
```

约定：

- 生成脚本默认只预览，不修改文件
- `--apply` 才允许实际重命名
- 脚本应检查目标文件是否已存在、目标名是否重复，以及必要元数据是否缺失
- 脚本输出应包含 ready / skipped / conflict / invalid 汇总

### 视频编码标签

视频命名中涉及编码标签时，当前使用以下规则：

- `H.264` / `h264` / `avc` 映射为 `AVC`
- `H.265` / `h265` / `hevc` 映射为 `HEVC`

### 归档文件

将素材按年份和季度归档：

```bash
python3 -m mediarchiver archive <source> --to <target>
```

如果不传 `--to`，则默认使用源目录作为目标目录。

### 归档 dry-run

归档支持预演模式，用于先检查目标路径和冲突：

```bash
python3 -m mediarchiver archive <source> --to <target> --dry-run
```

## 输出结果

项目会生成一些辅助文件或日志：

- `rename.log`：重命名过程日志
- `archived.log`：归档过程日志
- `rename-plan.json`：默认写入源目录的重命名计划文件
- `rename.sh`：可选导出的 shell 脚本
- `rename_operations.jsonl`：结构化重命名操作记录
- `rename_conflicts.jsonl`：重命名冲突记录
- `archive_operations.jsonl`：结构化归档操作记录
- `archive_conflicts.jsonl`：归档冲突记录

默认会依赖命名规则跳过已格式化文件；这些信息可用于排查问题和审计执行结果。

## 适用范围

当前项目更适合：

- 本地批量整理个人媒体文件
- 半自动整理已有媒体库
- 有固定命名偏好的个人工作流

当前项目不属于：

- 图形界面应用
- 云端相册系统
- 通用媒体管理平台

## 注意事项

- 运行前需要准备 Python 依赖以及系统命令 `exiftool`、`ffprobe`
- 实际改名或移动文件前，建议先在测试目录验证结果
- 对未知设备型号、异常元数据或特殊文件，程序可能会跳过处理
