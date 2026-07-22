<p align="center">
  <img src="logo.png" alt="mediarchiver logo" width="160">
</p>

<h1 align="center">mediarchiver</h1>

<p align="center">
  面向常规相机、手机素材和同名 sidecar 文件的归档与重命名命令行工具。
</p>

<p align="center">
  <a href="README.md">English</a> | <strong>中文</strong>
</p>

## 适用人群

- 经常从手机、相机、运动相机导入混合素材的创作者、摄影师和视频剪辑师。
- 希望在剪辑、备份、交付或长期归档前，把素材文件名整理成可读规范的人。
- 需要保留 XML、SRT、LRF、XMP 等伴随文件，并希望它们跟随主素材一起处理的人。
- 希望批量改名或归档前先看到清晰预览，确认无误后再真正执行的人。

## 解决痛点

- 不同品牌和设备生成的文件名不统一，后期检索困难。
- 图片、视频和 sidecar 文件手动整理时容易被拆散。
- 大文件夹按年、季度、月份归档前，很难快速确认素材范围。
- 批量文件操作风险高，需要默认预览和显式执行来降低误操作。

## 安装

推荐通过 release wheel 使用 `uv tool install` 安装。它会创建隔离的工具环境，并暴露
`mediarchiver` 命令：

```bash
uv tool install https://github.com/heminwon/mediarchiver/releases/download/v0.1.2/mediarchiver-0.1.2-py3-none-any.whl
```

本地开发产物可以这样安装：

```bash
uv build
uv tool install --reinstall dist/mediarchiver-*.whl
```

GitHub Releases 也会继续发布独立二进制，适合不想使用 Python 工具安装器的用户：

```text
https://github.com/heminwon/mediarchiver/releases
```

根据平台选择对应文件：

```text
mediarchiver-darwin-arm64.tar.gz
mediarchiver-linux-x86_64.tar.gz
```

解压后，把 `mediarchiver` 放到 `PATH` 中即可全局使用。

## 系统依赖

`mediarchiver` 通过外部工具读取媒体元数据：

```bash
# macOS
brew install exiftool ffmpeg

# Ubuntu / Debian
sudo apt install libimage-exiftool-perl ffmpeg
```

## 使用方式

查看已安装版本：

```bash
mediarchiver --version
```

### Rename

预览重命名结果：

```bash
mediarchiver rename <source>
```

执行可处理的重命名：

```bash
mediarchiver rename <source> --apply
```

查看支持的重命名规则：

```bash
mediarchiver rename --list-rules
```

把重命名 plan 写到指定目录：

```bash
mediarchiver rename <source> --output <dir>
```

### Archive

预览归档分组：

```bash
mediarchiver archive <source>
```

归档到另一个目录：

```bash
mediarchiver archive <source> --to <target>
```

选择时间分组：

```bash
mediarchiver archive <source> --by quarter
mediarchiver archive <source> --by month
mediarchiver archive <source> --by year
```

执行归档移动：

```bash
mediarchiver archive <source> --apply
```

## 注意事项

- 命令默认都是预览模式，只有传入 `--apply` 才会修改文件。
- Archive 会忽略 `.DS_Store` 等系统噪声文件。
- Archive 会尽量把可识别的 sidecar 文件跟随对应主素材一起移动。

## 维护文档

开发和维护说明见 [docs/development.md](docs/development.md)。
