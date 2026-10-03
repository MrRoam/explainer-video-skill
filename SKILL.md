---
name: explainer-video
description: 制作中文讲解视频、科普视频、原理动画或 3b1b 风格的视频讲解。用 Codex 编写讲稿和分镜，复用本地 Manim、Kokoro 配音与 FFmpeg，导出 MP4 和字幕。适用于“做一个视频讲解 X”；仅需文字解释、静态图或普通视频剪辑时不启用。
---

# 中文讲解视频

交付可播放的定制视频。Codex 负责内容与动画代码，本地工具负责配音、渲染和合成。默认中文、面向初学者、约一分钟、720p、30 fps；用户当次要求优先。

默认借鉴 3Blue1Brown 的图形推理方法：深色背景、少量有固定含义的强调色、连续图形变化、局部放大，以及公式与图形之间的对应变换。先建立直觉，再给出公式。为当前主题编写原创讲稿和画面。

## 复用工具

本机配置为 skill 根目录的 `runtime.local.json`，也可通过 `EXPLAINER_RUNTIME` 或 `--runtime` 指定。先检查配置中的 Python、FFmpeg、配音模型与可用中文字体。配置缺失时，按 [README.md](README.md) 配置已有环境或安装缺少的依赖。不要为试玩搭建常驻服务或重复安装可复用的环境。

```powershell
python "SKILL_DIR\scripts\init_project.py" --workspace "WORKSPACE" --name concept-video
```

SKILL_DIR 为当前 skill 目录，WORKSPACE 为本次工作区的绝对路径。脚本只复制小型模板，不下载依赖。源码在 `outputs/concept-video-project`，缓存在 `work/explainer/concept-video`。多个视频使用不同 name；工具被移动后重新配置路径。

## 编写与制作

同时修改项目中的 `lesson.json` 与 `scene.py`。模板为导数示例；只改标题不会变成新主题。字段、分镜同步和执行命令见 [references/pipeline.md](references/pipeline.md)。

选一个具体问题，从例子走到原理。每段旁白对应可观察的变化，例如点移动、曲线改变、变量更新或关系逐步显现。数学结论写清成立条件，字幕、公式和数字与讲稿一致。字体取自本机配置；模板中的 MathTex 需要 TeX，缺少 TeX 时可改用 Text 与几何对象。

默认使用本地 Kokoro 中文版、CPU 和已下载音色，无需额外大模型或语音 API。旁白中的数学符号、LaTeX 和英文术语要改写为中文读法。先做短段试听，再生成整片；不要自动下载全部音色或无提示更换配音后端。其他音频可按 [references/pipeline.md](references/pipeline.md) 接入。

## 检查与交付

先出低分辨率预览，检查中文、公式、遮挡和边界，再导出最终视频。检查旁白非静音、每段完整、结尾不截断。渲染脚本会检查尺寸和时间同步，视觉与读音仍需实际检查。

交付 MP4、SRT、中文讲稿与可重做源码。交付文件放工作区 `outputs`，中间文件放 `work`。说明实际配音后端和未解决限制；不要把脚本成功描述为用户已满意音质。
