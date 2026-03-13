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

重命名功能由 `src/rename/rename.py` 提供。

程序会读取媒体文件的元数据，并尝试生成统一格式的新文件名。重命名时会综合以下信息：

- 拍摄时间
- 设备品牌或型号
- 镜头信息（部分图片）
- 截图标记（部分图片）
- 视频分辨率
- 视频帧率
- 视频编码信息
- 文件编号或基于 MD5 生成的编号

生成后的文件名大致类似：

```text
20230512-114211_MiPh-FHD-30FPS_2348.HEIC
```

其中通常包含：

- `20230512-114211`：格式化后的拍摄时间
- `MiPh-FHD-30FPS`：设备和媒体标签
- `2348`：四位编号
- `.HEIC`：原始扩展名

### 2. Live Photo 关联处理

项目对部分 Live Photo 文件做了特殊处理。

- 如果识别到 `.mov` 属于 Live Photo 视频
- 会尝试查找同编号的图片文件
- 然后复用图片侧的命名信息生成视频文件名

这样可以让同一组 Live Photo 的图片和视频命名更加一致。

### 3. 媒体文件归档

归档功能由 `src/archive/archive.py` 提供。

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

默认执行重命名脚本时，主要是扫描并记录，不会直接改名：

```bash
python3 -m mediarchiver rename <source>
```

### 执行实际重命名

传入 `--rename` 后才会真正修改文件名：

```bash
python3 -m mediarchiver rename <source> --rename
```

### 重命名 dry-run

如需走完整规则但不真正改名，可传入：

```bash
python3 -m mediarchiver rename <source> --rename --dry-run
```

### 控制并发读取数

重命名和归档现在支持通过 `--workers` 控制元数据预读取并发度。

```bash
python3 -m mediarchiver rename <source> --workers 2
python3 -m mediarchiver archive <source> --destination <target> --workers 2
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
python3 -m mediarchiver rename <source> --include-formatted
```

### 构建 plan 与导出 shell

长期工作流建议先生成 `plan.json`，再决定执行或导出 shell：

```bash
python3 -m mediarchiver rename <source> --build-plan rename-plan.json
python3 -m mediarchiver rename --build-plan rename-plan.json --export-shell rename.sh
python3 -m mediarchiver rename --apply-plan rename-plan.json
```

### 视频编码标签

视频命名中涉及编码标签时，当前使用以下规则：

- `H.264` / `h264` / `avc` 映射为 `AVC`
- `H.265` / `h265` / `hevc` 映射为 `HEVC`

### 归档文件

将素材按年份和季度归档：

```bash
python3 -m mediarchiver archive <source> --destination <target>
```

如果不传 `--destination`，则默认使用源目录作为目标目录。

### 归档 dry-run

归档支持预演模式，用于先检查目标路径和冲突：

```bash
python3 -m mediarchiver archive <source> --destination <target> --dry-run
```

## 输出结果

项目会生成一些辅助文件或日志：

- `rename.log`：重命名过程日志
- `archived.log`：归档过程日志
- `rename_info.txt`：记录已处理文件的 MD5、目标文件名和原文件名
- `rename_operations.jsonl`：结构化重命名操作记录
- `rename_conflicts.jsonl`：重命名冲突记录
- `archive_operations.jsonl`：结构化归档操作记录
- `archive_conflicts.jsonl`：归档冲突记录

这些信息可用于排查问题或避免重复处理。

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
