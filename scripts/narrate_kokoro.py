"""使用本地 Kokoro 中文权重生成按段旁白；推理时不联网。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time

from runtime_config import read_runtime

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

REPO = "hexgrad/Kokoro-82M-v1.1-zh"
RATE = 24000
LETTERS = {"x": "艾克斯", "y": "歪", "h": "艾尺", "f": "艾弗", "P": "皮", "Q": "丘"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def spoken_text(text):
    text = re.sub(r"(?<![A-Za-z])[xyhfPQ](?![A-Za-z])", lambda m: LETTERS[m[0]], text)
    if re.search(r"[A-Za-z\\]", text):
        raise ValueError("本地中文配音请将英文术语、变量或 LaTeX 改写为中文读法，避免漏读。")
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path)
    parser.add_argument("--runtime", type=Path, help="省略模型目录时从此配置读取")
    parser.add_argument("--voice", default="zm_010")
    parser.add_argument("--speed", type=float, default=0.95)
    parser.add_argument("--max-beats", type=int)
    parser.add_argument("--sample-file", type=Path, help="将前两段合成供用户试听的 WAV")
    args = parser.parse_args()
    if not re.fullmatch(r"z[fm]_\d{3}", args.voice):
        parser.error("音色编号无效，例如 zm_010 或 zf_001。")
    if not 0.6 <= args.speed <= 1.4:
        parser.error("语速须在 0.6 到 1.4 之间。")
    model_dir = (args.model_directory or Path(read_runtime(args.runtime)["narration"]["model_directory"])).expanduser().resolve()
    weights = model_dir / "kokoro-v1_1-zh.pth"
    config = model_dir / "config.json"
    voice_path = model_dir / "voices" / f"{args.voice}.pt"
    for path in (weights, config, voice_path):
        if not path.is_file():
            raise FileNotFoundError(f"本地模型文件缺失：{path}；推理不会自动下载。")
    output = args.output_directory.resolve()
    output.mkdir(parents=True, exist_ok=True)
    lesson = read_json(args.lesson)
    if args.max_beats is not None and args.max_beats < 1:
        parser.error("max-beats 须大于零。")
    beats = lesson["beats"][:args.max_beats] if args.max_beats else lesson["beats"]
    if not beats or len({beat["id"] for beat in beats}) != len(beats):
        parser.error("旁白段落不能为空，id 不能重复。")
    started = time.perf_counter()
    import numpy as np
    import soundfile as sf
    import torch
    from kokoro import KModel, KPipeline

    torch.set_num_threads(6)
    torch.manual_seed(0)
    model = KModel(repo_id=REPO, config=str(config), model=str(weights)).to("cpu").eval()
    # 所有输入先改写为中文，不初始化会另下载英文模型的英文 pipeline。
    pipeline = KPipeline(lang_code="z", repo_id=REPO, model=model)
    rows, details = [], []
    model_key = hashlib.sha256(config.read_bytes() + voice_path.read_bytes()).hexdigest()

    def segments(text):
        for sentence in re.split(r"(?<=[。！？；])", text):
            sentence = sentence.strip()
            if not sentence:
                continue
            phonemes, _ = pipeline.g2p(sentence)
            if "❓" in phonemes:
                raise ValueError(f"出现未识别的发音：{sentence}")
            if len(phonemes) > 510:
                middle = len(sentence) // 2
                yield from segments(sentence[:middle])
                yield from segments(sentence[middle:])
            elif phonemes:
                yield sentence, phonemes
            else:
                raise ValueError(f"没有得到有效发音：{sentence}")

    for beat in beats:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", beat["id"]):
            raise ValueError("段落 id 无效。")
        readable = spoken_text(beat["text"])
        fingerprint = hashlib.sha256(
            f"{REPO}|v1.1|{model_key}|{args.voice}|{args.speed}|{readable}|pause=0.16".encode()
        ).hexdigest()[:16]
        path = output / f"{beat['id']}-{fingerprint}.wav"
        cache = path.is_file()
        chunk_details = []
        if not cache:
            chunks = []
            with torch.inference_mode():
                for sentence, phonemes in segments(readable):
                    # 依据官方中文样例，长发音串适当放慢，减少尾段赶读。
                    speed = args.speed * max(0.8, 1 - max(0, len(phonemes) - 83) / 500)
                    result = next(pipeline.generate_from_tokens(phonemes, voice=str(voice_path), speed=speed))
                    audio = result.audio.detach().cpu().numpy().reshape(-1)
                    if not np.isfinite(audio).all() or audio.size < RATE // 5:
                        raise ValueError(f"无效旁白：{beat['id']}")
                    if chunks:
                        chunks.append(np.zeros(round(0.16 * RATE), dtype=np.float32))
                    chunks.append(audio)
                    chunk_details.append(dict(text=sentence, phonemes=phonemes, speed=round(speed, 3)))
            audio = np.concatenate(chunks)
            raw_peak = float(np.abs(audio).max())
            if raw_peak > 0.98:
                audio = audio * (0.94 / raw_peak)
            sf.write(path, audio, RATE, subtype="PCM_16")
        audio, rate = sf.read(path, dtype="float32")
        if rate != RATE or audio.ndim != 1 or not np.isfinite(audio).all():
            raise ValueError("旁白格式不符合视频管线要求。")
        peak = float(np.abs(audio).max())
        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < 0.001 or peak >= 0.999:
            raise ValueError(f"旁白静音或削波：{beat['id']}")
        rows.append(dict(id=beat["id"], path=str(path), voice=f"Kokoro v1.1-zh / {args.voice}"))
        details.append(dict(id=beat["id"], text=beat["text"], spoken_text=readable,
                            duration=len(audio)/RATE, peak=peak, rms=rms,
                            cache=cache, chunks=chunk_details))
        print(f"旁白 {beat['id']}：{len(audio)/RATE:.2f} 秒，{args.voice}", flush=True)
    (output / "narration.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    report = dict(model=REPO, voice=args.voice, device="cpu", sample_rate=RATE,
                  elapsed_seconds=round(time.perf_counter()-started, 2), segments=details,
                  subjective_listening_confirmed=False)
    (output / "narration-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.sample_file:
        parts = []
        for row in rows[:2]:
            if parts:
                parts.append(np.zeros(round(RATE * 0.25), dtype=np.float32))
            parts.append(sf.read(row["path"], dtype="float32")[0])
        args.sample_file.parent.mkdir(parents=True, exist_ok=True)
        sf.write(args.sample_file, np.concatenate(parts), RATE, subtype="PCM_16")
        print("试听文件：", args.sample_file.resolve(), flush=True)
    print(f"CPU 配音完成，耗时 {report['elapsed_seconds']} 秒。", flush=True)


if __name__ == "__main__":
    main()
