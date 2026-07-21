---
name: mediarchiver-profile-authoring
description: 在本仓库中根据 mediarchiver rename 预览结果和用户指定素材，分析真实 exiftool/ffprobe 元数据并完善 profiles；默认只预览，不执行真实重命名。
---

# mediarchiver profile authoring 工作流

当用户要求 `mediarchiver rename` 支持某批素材、某品牌、某机型，或要求根据样本完善重命名规则时，使用此 skill。

推荐工作模式：

- `mediarchiver rename` 是产品入口，规则沉淀到 `mediarchiver/rename/profiles/`。
- AI 先用现有产品命令生成 baseline plan，再分析用户指定素材的原始 `exiftool` / `ffprobe` 元数据，最后决定更新现有 profile 或新增 profile。
- 默认只生成预览 plan，不执行真实重命名；只有用户明确要求并传入 `--apply` 才能执行。
- 批次 standalone 脚本不是默认产物；只有用户明确要求“一次性脚本”时才生成到 `rename/`。
- profiles 必须按插件边界维护：品牌、机型、sidecar、字段来源、tech tag 映射都留在 profile 包内，公共层只负责发现、调用、合并和通用安全检查。

## 插件边界

`mediarchiver/rename/profiles/` 是 rename 规则的插件目录。每个品牌目录通过自己的 `adapter.py` 暴露 `PROFILE` 或 `PROFILES`，由 `mediarchiver/rename/registry.py` 自动发现。

允许的公共层职责：

- `registry.py` 自动发现 profile，不硬编码品牌或机型 import。
- `service.py` 调用 profile、合并 plan、标记跨 profile 源文件冲突、目标冲突、未匹配文件。
- `cli.py` 负责参数、预览输出、apply 入口和日志。
- `metadata.py`、`common/` 只提供通用工具读取、文件类型、日期解析、worker、日志、文件操作能力。

不允许放进公共层的内容：

- 品牌名、机型名、厂商文件名前缀。
- 某品牌 sidecar 扩展名或配对规则。
- 某品牌元数据字段优先级。
- 某品牌 tech tag 映射、清洗、命名例外。
- 为了让某个 profile 成立而新增的全局 fallback。

新增、删除或禁用 profile 应该只触碰对应 `mediarchiver/rename/profiles/<brand>/` 包；除非是在扩展通用协议本身，否则不要编辑 registry/service 来适配单一品牌。

## 当前必需流程

0. 先建立当前产品行为 baseline。

   先确认已有 profile 和当前预览结果，不要一上来就写规则：

   ```bash
   mediarchiver rename --list-profiles
   mediarchiver rename <source> --output-plan /tmp/rename-baseline.json
   ```

   审查 baseline plan：

   - 哪些文件已经 `ready`；
   - 哪些文件是 `skipped/no_matching_profile`；
   - 哪些文件是 `invalid` 或 `conflict`；
   - 每个 ready item 的 `details.required` 字段来源是否可信；
   - sidecar 是否正确配对，或是否因为主文件未 ready 被跳过。

1. 再确认素材范围和样本选择。

   使用用户提供的目录或文件路径。先列出代表性文件，观察是否混合了多个品牌、机型、sidecar 或已格式化文件：

   ```bash
   find <source> -maxdepth 1 -type f | sort | head -80
   ```

   样本优先来自 baseline plan 中的问题项：

   - `no_matching_profile` 的主文件；
   - `profile_not_matched` 的候选文件；
   - `invalid` 的文件；
   - 与主文件同 stem、同编号或元数据有关联的 sidecar；
   - 每个已匹配 profile 至少保留 1 个代表样本，防止改坏已有规则。

2. 读取原始元数据，不要靠猜测补规则。

   在规则尚未理解前，直接检查原始工具输出。至少保留两种 exiftool 视角：

   ```bash
   exiftool -json -G -n <sample-file-1> <sample-file-2> > /tmp/inspect-exiftool-grouped.json
   exiftool -json -n <sample-file-1> <sample-file-2> > /tmp/inspect-exiftool-runtime.json
   ffprobe -v error -print_format json -show_format -show_streams <sample-video> > /tmp/inspect-ffprobe.json
   ```

   说明：

   - `-G` 输出用于理解字段来源。
   - 不带 `-G` 的输出更接近 `mediarchiver.rename.metadata.build_file_metadata_context()` 运行时看到的字段名。
   - 多个视频样本应分别写出 `ffprobe` 输出，或用 JSONL 记录并包含源文件名。
   - sidecar 例如 Sony XML、DJI LRF/SRT、GoPro LRV/THM 必须单独检查，并确认它和主文件的配对字段或命名关系。

3. 不要编造元数据。

   不要猜测拍摄时间、设备、codec、帧率、分辨率、Log/HDR 标记、自拍/截图状态或原始 ID。只能使用：

   - 原始 `inspect` 输出里的字段；
   - 文件名中可稳定解析的结构；
   - 用户明确说明的事实。

4. 决定 profile 归属。

   优先更新已有 profile：

   ```text
   mediarchiver/rename/profiles/apple/
   mediarchiver/rename/profiles/dji/
   mediarchiver/rename/profiles/sony/
   ```

   决策顺序：

   - 如果已有 profile 明显应该支持该素材，修正该 profile 的 detector / adapter / preset。
   - 如果是同品牌但不同机型或不同设备类型，新增同品牌下的新 profile。
   - 如果是新品牌，新增品牌目录，并在该目录的 `adapter.py` 暴露新 profile。
   - 如果只是用户的一次性批次需求，且用户明确要求脚本，才进入 standalone 脚本例外流程。

   只有当样本确实代表新的品牌、机型、设备类型或 sidecar 结构时，才新增 profile。profile id 使用：

   ```text
   brand:model_or_device
   ```

   示例：

   ```text
   apple:iphone
   dji:pocket4p
   sony:a7m4
   gopro:hero13
   ```

5. 保持 profile-first 分层。

   新增或更新 profile 时，优先保持以下结构：

   ```text
   mediarchiver/rename/profiles/<brand>/
     __init__.py
     adapter.py              # profile 插件入口：暴露 PROFILE 或 PROFILES
     detectors/              # 可选：复杂设备族检测
     presets/
       <model>.py            # 命名字段、tech tags、sidecar 改名规则
   ```

   规则边界：

   - `adapter.py` 负责候选文件收集、profile 匹配、sidecar 分发，并暴露 `PROFILE` 或 `PROFILES`。
   - `preset` 负责构造 `YYYYMMDD-HHMMSS_DeviceOrUnit_TechTags_OriginalId.ext`。
   - 具体品牌/机型字段来源留在对应 profile 内，不要放回全局通用规则。
   - `mediarchiver/rename/service.py` 只做薄分发、合并 plan、跨 profile 冲突检查。
   - `mediarchiver/rename/registry.py` 只做 profile 自动发现和重复 id 校验。
   - 不要编辑冻结的 `rename/rename_dji_pocket4p.py`，除非用户明确要求。

6. 实现后重新生成 plan，并和 baseline 对比。

   ```bash
   mediarchiver rename <source> --output-plan /tmp/rename-after.json
   ```

   对比重点：

   - 预期文件是否从 `no_matching_profile` 变成 `ready`；
   - 原本已经 ready 的文件是否仍然 ready；
   - 是否出现新的重复目标或错误匹配；
   - 新 profile 是否在 auto 模式中自动生效，且 plan details 中的 `profile` 可解释。

## 命名规则

默认命名格式：

```text
YYYYMMDD-HHMMSS_DeviceOrUnit_TechTags_OriginalId.ext
```

字段要求：

- `YYYYMMDD-HHMMSS` 必须来自可靠元数据、可靠文件名时间，或用户明确说明。
- `DeviceOrUnit` 必须来自 profile 固定设备名或元数据设备名；Apple 这类设备可用具体型号，例如 `iPhone14Pro`。
- `TechTags` 是可选字段，只包含元数据支持的技术信息，例如 `4K`、`25FPS`、`H264`、`HEVC`、`10Bit`、`422`、`SLog3`、`DLogM`、`HDR`、`Selfie`、`Screenshot`。
- `OriginalId` 优先来自原始文件名；不可用时必须使用稳定方案，并在 plan details 中说明来源。
- 保留原始扩展名，除非用户明确要求规范化扩展名。
- 目标已存在必须标记为 `conflict/destination_exists`，不能覆盖。
- plan 内重复目标必须标记为 `conflict/destination_duplicated_in_plan`。

## 元数据来源记录

每个 ready item 的 `details` 应记录字段来源，便于审查：

```json
{
  "required": {
    "date": "20260307-104740",
    "date_source": "metadata:CreationDateValue",
    "device_unit": "Sony-A7M4",
    "device_unit_source": "profile",
    "original_id": "0212",
    "original_id_source": "filename"
  },
  "optional": {
    "tech_tags": "4K-25FPS-H264-10Bit-422-SLog3",
    "missing": []
  },
  "profile_match": [
    "metadata=device_model_ilce_7m4"
  ]
}
```

缺少可选字段时不要阻止 ready，但应放入 `optional.missing`。缺少必需字段时标记为 `invalid` 或 `skipped`，并给出明确 reason。

## sidecar 规则

sidecar 必须在对应 profile 内处理，不放进全局兼容层。

要求：

- sidecar 只跟随同 profile 的主文件。
- 主文件不是 ready 时，sidecar 标记为 `skipped/primary_not_ready`。
- 找不到主文件时，sidecar 标记为 `skipped/missing_primary_media`。
- sidecar 目标名通常使用主文件目标 stem，并保留 sidecar 扩展名。
- plan details 记录 `sidecar_rule`、`sidecar_type`、`paired_with` 等审查信息。

## 实现检查清单

更新或新增 profile 后，必须确认：

- `mediarchiver rename --list-profiles` 能看到新增或更新后的 profile。
- `mediarchiver rename <source> --output-plan <tmp-plan>` 能生成预览 plan。
- 混合目录下，能匹配的文件进入 ready；不能匹配的可见文件显示为 `skipped/no_matching_profile`。
- `rename-plan.json` 中 ready / skipped / conflict / invalid 计数合理。
- 每个必需命名字段都有来源记录。
- 重复目标、已存在目标、sidecar 主文件未 ready 都有明确状态。
- 没有执行真实重命名，除非用户明确要求 `--apply`。

推荐验证命令：

```bash
just lint
just smoke
mediarchiver rename --list-profiles
mediarchiver rename <source> --output-plan /tmp/rename-plan.json
```

如果更新了全局二进制流程或用户正在使用全局命令，完成后提醒：

```bash
just install-local
```

## 测试策略

当前项目倾向于基于真实元信息 fixture 建测试，而不是大量 mock 内部函数。

后续补测试时优先使用：

```text
tests/fixtures/metadata/<profile-id>/*.exiftool.json
tests/fixtures/metadata/<profile-id>/*.ffprobe.json
```

测试从真实 fixture 构造 `FileMetadataContext`，验证：

- profile match；
- 文件名输出；
- tech tags；
- sidecar 配对；
- conflict / skipped / invalid reason；
- plan details 的字段来源。

## 安全要求

实现和验证过程中必须：

- 默认只预览，不执行真实重命名。
- 绝不覆盖已有文件。
- 不使用 `rm`、`git reset --hard`、`git checkout --` 等破坏性命令，除非用户明确要求。
- 不把某个品牌/机型的特殊字段提升为全局规则。
- 不为了某个品牌在 registry/service/common 中增加定制分支。
- 不为了让样本通过而降低 profile 匹配精度。
- 不静默吞掉可见文件；无法匹配 profile 的文件应在 plan 里展示为 skipped。

## standalone 脚本例外

只有当用户明确要求生成一次性批次脚本时，才创建：

```text
rename/rename_<batch_or_device>.py
```

此类脚本仍必须：

- 默认只预览；
- 至少支持 `--apply`、`--output-plan`；
- 使用真实元数据来源；
- 不覆盖文件；
- 最终回复明确说明是否执行过真实重命名。
