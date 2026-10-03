"""检查已有环境并保存本机配置；不安装软件、不下载模型。"""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess

from runtime_config import DEFAULT_RUNTIME


def inspect_python(path, mode):
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Python 不存在：{path}")
    modules = ["manim", "av"] if mode == "manim" else ["kokoro", "misaki", "torch", "soundfile"]
    code = (
        "import importlib.util, importlib.metadata, json; "
        f"names={modules!r}; "
        "missing=[n for n in names if importlib.util.find_spec(n) is None]; "
        "assert not missing, '缺少依赖：'+', '.join(missing); "
        "print(json.dumps({n:importlib.metadata.version(n) for n in names}))"
    )
    process = subprocess.run([str(path), "-c", code], capture_output=True, text=True, encoding="utf-8")
    if process.returncode:
        raise ValueError(f"{mode} 环境检查失败：\n{process.stderr.strip()}")
    return str(path), json.loads(process.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manim-python", type=Path, required=True)
    parser.add_argument("--tts-python", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, help="省略时在 PATH 或 Manim 环境的 imageio-ffmpeg 中查找")
    parser.add_argument("--tex-bin", type=Path, help="已有 latex、dvisvgm 所在目录；省略时使用 PATH")
    parser.add_argument("--font", default="Microsoft YaHei")
    parser.add_argument("--voice", default="zm_010")
    parser.add_argument("--speed", type=float, default=0.95)
    parser.add_argument("--output", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--force", action="store_true", help="覆盖指定的本机配置")
    args = parser.parse_args()
    if not re.fullmatch(r"z[fm]_\d{3}", args.voice):
        parser.error("中文音色编号无效，例如 zm_010 或 zf_001。")
    if not 0.6 <= args.speed <= 1.4:
        parser.error("语速须在 0.6 到 1.4 之间。")
    output = args.output.expanduser().resolve()
    if output.exists() and not args.force:
        parser.error(f"配置已存在：{output}；重配时添加 --force。")
    try:
        manim_python, manim_versions = inspect_python(args.manim_python, "manim")
        tts_python, _ = inspect_python(args.tts_python, "kokoro")
        ffmpeg = args.ffmpeg or shutil.which("ffmpeg")
        if not ffmpeg:
            result = subprocess.run(
                [manim_python, "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
                check=True, capture_output=True, text=True, encoding="utf-8",
            )
            ffmpeg = result.stdout.strip()
        ffmpeg = Path(ffmpeg).expanduser().resolve()
        if not ffmpeg.is_file():
            raise ValueError(f"FFmpeg 不存在：{ffmpeg}")
        subprocess.run([str(ffmpeg), "-version"], check=True, capture_output=True)
        models = args.model_directory.expanduser().resolve()
        for relative in ("config.json", "kokoro-v1_1-zh.pth", f"voices/{args.voice}.pt"):
            if not (models / relative).is_file():
                raise ValueError(f"缺少本地模型：{models / relative}；请先运行 download_kokoro.ps1。")
        if args.tex_bin and not args.tex_bin.expanduser().resolve().is_dir():
            raise ValueError("--tex-bin 须为已有 TeX 程序所在目录。")
        if not args.font.strip():
            raise ValueError("字体名称不能为空。")
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    runtime = dict(
        python=manim_python, ffmpeg=str(ffmpeg), manim_version=manim_versions["manim"],
        font=args.font, narration=dict(
            backend="kokoro", python=tts_python, model_directory=str(models),
            voice=args.voice, speed=args.speed,
        ),
    )
    if args.tex_bin:
        runtime["tex_bin"] = str(args.tex_bin.expanduser().resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("本机配置已保存：", output)
    print("配音使用本地 CPU。请用短片检查中文字体、TeX 和读音。")


if __name__ == "__main__":
    main()
