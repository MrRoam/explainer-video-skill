"""用本地配音和 Manim 制作讲解视频；不调用外部 API。"""

import argparse
import json
import math
import os
import re
from pathlib import Path
import subprocess
import sys
import time
import wave

PROJECT = Path(__file__).resolve().parent
SETTINGS = json.loads((PROJECT / "tools.json").read_text(encoding="utf-8-sig"))
WORKSPACE = Path(SETTINGS["workspace"])
WORK = WORKSPACE / "work" / "explainer" / SETTINGS["project_id"]
OUTPUTS = WORKSPACE / "outputs"
OUTPUT_STEM = SETTINGS["output_stem"]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def execute(args, **kwargs):
    print("Running:", Path(args[0]).name, flush=True)
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def srt_time(seconds):
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    seconds, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def assemble_audio(lesson, rows):
    fps = lesson["fps"]
    sample_rate = 24000
    if sample_rate % fps:
        raise ValueError("音频采样率必须可被视频帧率整除。")
    samples_per_frame = sample_rate // fps
    by_id = {row["id"]: row for row in rows}
    cues, subtitles = [], []
    cursor = 0
    master_path = WORK / "narration.wav"
    with wave.open(str(master_path), "wb") as master:
        master.setparams((1, 2, sample_rate, 0, "NONE", "not compressed"))
        for index, beat in enumerate(lesson["beats"], 1):
            with wave.open(by_id[beat["id"]]["path"], "rb") as audio:
                if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, sample_rate):
                    raise ValueError("旁白格式不一致。")
                frames = audio.getnframes()
                payload = audio.readframes(frames)
            lead_frames, tail_frames = 6, 9
            beat_frames = max(
                math.ceil(beat["min_seconds"] * fps),
                math.ceil(frames / samples_per_frame) + lead_frames + tail_frames,
            )
            lead_samples = lead_frames * samples_per_frame
            tail_samples = beat_frames * samples_per_frame - lead_samples - frames
            master.writeframes(b"\0" * lead_samples * 2)
            master.writeframes(payload)
            master.writeframes(b"\0" * tail_samples * 2)
            start = cursor / fps
            end = (cursor + beat_frames) / fps
            voice_start = start + lead_frames / fps
            voice_end = voice_start + frames / sample_rate
            cues.append(dict(beat, start=start, end=end, voice_start=voice_start, voice_end=voice_end))
            subtitles.append(f"{index}\n{srt_time(voice_start)} --> {srt_time(voice_end)}\n{beat['text']}\n")
            cursor += beat_frames
    timeline = dict(lesson, beats=cues, duration=cursor / fps)
    (WORK / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUTS / f"{OUTPUT_STEM}.srt").write_text("\n".join(subtitles), encoding="utf-8-sig")
    script = "# 讲解稿：" + lesson["title"] + "\n\n"
    script += "\n\n".join(f"{i}. {beat['text']}" for i, beat in enumerate(lesson["beats"], 1))
    (OUTPUTS / f"{OUTPUT_STEM}-script.md").write_text(script, encoding="utf-8")
    return timeline, master_path


def inspect_video(path):
    import av

    with av.open(str(path)) as container:
        video = container.streams.video[0]
        audio = container.streams.audio[0]
        result = {
            "width": video.width,
            "height": video.height,
            "fps": float(video.average_rate),
            "video_codec": video.codec_context.name,
            "audio_codec": audio.codec_context.name,
            "video_duration": float(video.duration * video.time_base),
            "audio_duration": float(audio.duration * audio.time_base),
            "size_mb": round(path.stat().st_size / 1024**2, 2),
        }
    return result


def main():
    global OUTPUT_STEM
    parser = argparse.ArgumentParser(description="本地制作中文 Manim 讲解视频")
    parser.add_argument("--draft", action="store_true", help="用 854×480 制作快速预览")
    parser.add_argument("--audio-only", action="store_true", help="仅生成并检查旁白")
    parser.add_argument("--audio-manifest", type=Path, help="使用外部按段生成的本地旁白")
    args = parser.parse_args()
    for key in ("project_id", "output_stem"):
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", SETTINGS[key]):
            raise ValueError("项目标识无效，请使用初始化脚本配置。")
    if args.draft:
        OUTPUT_STEM += "-preview"
    started = time.perf_counter()
    WORK.mkdir(parents=True, exist_ok=True)
    lesson = read_json(PROJECT / "lesson.json")
    if args.draft:
        lesson["width"], lesson["height"] = 854, 480
    tools = read_json(PROJECT / "tools.json")
    ffmpeg = Path(tools["ffmpeg"])
    if not ffmpeg.is_file():
        raise FileNotFoundError("FFmpeg 路径已变化，请更新 tools.json。")
    audio_directory = WORK / "audio"
    if args.audio_manifest:
        manifest = args.audio_manifest.resolve()
        rows = read_json(manifest)
        expected = [beat["id"] for beat in lesson["beats"]]
        actual = [row["id"] for row in rows]
        if len(set(actual)) != len(actual) or set(actual) != set(expected):
            raise ValueError("外部音频清单的段落与讲稿不一致。")
        for row in rows:
            audio_path = Path(row["path"])
            if not audio_path.is_absolute():
                audio_path = manifest.parent / audio_path
            row["path"] = str(audio_path.resolve())
    elif tools.get("narration", {}).get("backend") == "kokoro":
        narrator = tools["narration"]
        lesson["voice"] = f"Kokoro v1.1-zh / {narrator['voice']}"
        execute([
            narrator["python"], narrator["script"], "--lesson", PROJECT / "lesson.json",
            "--output-directory", audio_directory, "--model-directory", narrator["model_directory"],
            "--voice", narrator["voice"], "--speed", str(narrator.get("speed", 0.95)),
        ])
        rows = read_json(audio_directory / "narration.json")
    elif tools.get("narration", {}).get("backend") == "windows-sapi":
        if os.name != "nt":
            raise RuntimeError("Windows SAPI 只能用于 Windows。请配置 Kokoro 或传入外部旁白。")
        execute([
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            PROJECT / "narrate.ps1", "-LessonPath", PROJECT / "lesson.json",
            "-OutputDirectory", audio_directory,
        ])
        rows = read_json(audio_directory / "narration.json")
    else:
        raise ValueError("未配置旁白后端；请配置 Kokoro 或传入 --audio-manifest。")
    timeline, master = assemble_audio(lesson, rows)
    print(f"Narration/timeline: {timeline['duration']:.2f} seconds", flush=True)
    if args.audio_only:
        return
    environment = os.environ.copy()
    environment["EXPLAINER_TIMELINE"] = str(WORK / "timeline.json")
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["EXPLAINER_FONT"] = lesson.get("font", "Microsoft YaHei")
    if tools.get("tex_bin"):
        environment["PATH"] = tools["tex_bin"] + os.pathsep + environment.get("PATH", "")
    execute([
        sys.executable, "-m", "manim", "--renderer", "cairo", "--format", "mp4",
        "--resolution", f"{lesson['width']},{lesson['height']}", "--fps", str(lesson["fps"]),
        "--verbosity", "WARNING", "--progress_bar", "none", "--media_dir", WORK / "media",
        "--output_file", f"silent_{OUTPUT_STEM}", PROJECT / "scene.py", lesson["scene_class"],
    ], env=environment, cwd=WORK)
    candidates = list((WORK / "media").rglob(f"silent_{OUTPUT_STEM}.mp4"))
    silent = max(candidates, key=lambda path: path.stat().st_mtime)
    output = OUTPUTS / f"{OUTPUT_STEM}.mp4"
    execute([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", silent, "-i", master,
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
        "-b:a", "128k", "-movflags", "+faststart", "-shortest", output,
    ])
    report = inspect_video(output)
    report.update({"planned_duration": timeline["duration"], "voice": lesson["voice"],
                   "manim_version": tools["manim_version"], "elapsed_seconds": round(time.perf_counter()-started, 1)})
    if report["width"] != lesson["width"] or report["height"] != lesson["height"]:
        raise RuntimeError("导出分辨率与配置不符。")
    if abs(report["video_duration"] - timeline["duration"]) > 2 / lesson["fps"]:
        raise RuntimeError("画面与旁白时间线不一致，请检查场景时长。")
    if report["audio_duration"] + 0.1 < timeline["beats"][-1]["voice_end"]:
        raise RuntimeError("最后一段旁白被截断。")
    report_path = OUTPUTS / f"{OUTPUT_STEM}-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    print("Video ready:", output, flush=True)


if __name__ == "__main__":
    main()
