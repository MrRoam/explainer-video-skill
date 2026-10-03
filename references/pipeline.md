# 字段、同步与本地配音

## 项目字段

`lesson.json` 包含 title、scene_class、font、voice、speech_rate、fps、width、height，以及 beats 数组。默认 scene_class 为 ExplainerScene。每个 beat 有 id、text（口语旁白）、caption（画面短句）、min_seconds。id 使用小写字母开头的字母、数字和下划线，不能重复。

`tools.json` 由初始化脚本生成，包含 python、ffmpeg、workspace、project_id、output_stem、manim_version，以及 narration 配音配置。tex_bin 可选。绝对路径只存在各自的本机配置和生成项目中，不应提交到公开仓库。

`runtime.local.json` 中的工具路径也可以写成相对于该配置文件的路径；不能假设它们相对于当前工作目录。运行脚本使用指定的环境，不依赖当前窗口是否已激活 venv。

## 时间同步

先生成旁白，再按真实音频长度计算时间线。每段长度不少于 min_seconds，按整帧量化；开头留 6 帧，结尾至少留 9 帧。渲染时 EXPLAINER_TIMELINE 指向 timeline.json，每段有 start、end、voice_start、voice_end。

模板按 `show_` 加 beat id 调用分镜，每个 id 必须有对应方法。say() 把动画补足到该段结束；动作超时则报错。缩短动作或增加 min_seconds，不能截掉语音凑时长。也可改用自己的调度结构，但必须保持旁白与画面的时间线一致。

在项目目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 -AudioOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 -Draft
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run.ps1
```

以 concept-video 初始化时，输出为 outputs/concept-video.mp4、concept-video.srt、concept-video-script.md、concept-video-report.json。预览产物带 -preview 后缀。

macOS / Linux 可使用 tools.json 指定的 Manim Python 执行 `run.py --draft` 或 `run.py`，并在本机配置中指定可用中文字体。该路径尚未经过完整验证。

## 本地中文配音

Kokoro 使用明确的本地权重、配置与音色路径，离线推理。输入先改写为中文，不初始化英文 pipeline，不下载英文模型。即便依赖包含英文分词功能，也不需要下载对应的语言模型才能运行这条中文路径。

脚本支持按段缓存，检查非静音、非有限值和削波；长音素序列拆分而不截断。数学变量、公式和英文术语改写为中文读法。字幕可以保留数学符号，但 text 应以可朗读的中文为主。

配音配置为 tools.json 的 narration：backend、python、script、model_directory、voice、speed。修改 voice 后重新运行。默认两个音色为 zm_010（男声）与 zf_001（女声）；添加其他音色需先取得相应的本地文件。

只生成两段试听：

```powershell
& "配音环境\Scripts\python.exe" "SKILL_DIR\scripts\narrate_kokoro.py" `
  --lesson .\lesson.json --output-directory .\audition `
  --model-directory "本地模型目录" --voice zf_001 `
  --max-beats 2 --sample-file .\audition\preview.wav
```

指定 `--model-directory` 时无需读取本机配置。模型缺失会报错，不会自动下载。音色的自然度和多音字读音需要实际试听。

## 外部旁白接入

按 beat 输出 24 kHz、单声道、16-bit PCM WAV。其他格式先用 FFmpeg 转换。narration.json 为数组：

```json
[
  {"id": "intro", "path": "intro.wav", "voice": "实际后端与音色"},
  {"id": "curve", "path": "curve.wav", "voice": "实际后端与音色"}
]
```

清单中的 id 必须与 lesson.beats 全部逐段对应，上面仅示范结构。path 可为绝对路径或相对于清单文件的路径。将 lesson.voice 改为实际模型与音色名称，避免报告误标。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 -AudioManifest "完整路径\narration.json"
```

更换旁白后按真实时长重新渲染动画。

## 常见故障

| 现象 | 处理 |
| --- | --- |
| 找不到 runtime.local.json | 在 skill 目录运行 configure_runtime.py，或用 --runtime 指定配置 |
| 移动工具或模型后路径失效 | 重新配置；已有项目也需更新 tools.json |
| 中文缺字 | 换用本机已安装中文字体，配置 --font；检查预览画面 |
| latex / dvisvgm 不存在 | 复用已有 TeX 并配置 PATH / --tex-bin，或改写公式画法 |
| 配音拒绝英文或 LaTeX | 将 beat.text 改写成中文读法 |
| 动画超过一段时长 | 缩短动作，或增加对应 min_seconds |
| 下载证书或代理错误 | 修复系统信任和代理；不要关闭 TLS 校验 |

上游说明：[Kokoro 中文模型](https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh)、[Kokoro](https://github.com/hexgrad/kokoro)、[Misaki](https://github.com/hexgrad/misaki)、[Manim](https://docs.manim.community/en/stable/)。
