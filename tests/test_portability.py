"""不安装渲染依赖，检查跨目录配置与本地文件保护。"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from runtime_config import read_runtime


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.models = self.base / "models"
        (self.models / "voices").mkdir(parents=True)
        for file in ("config.json", "kokoro-v1_1-zh.pth", "voices/zm_010.pt"):
            (self.models / file).write_text("test fixture", encoding="utf-8")
        self.runtime = self.base / "runtime.json"
        self.runtime.write_text(json.dumps(dict(
            python=sys.executable, ffmpeg=sys.executable, manim_version="0.21.0",
            font="Test Chinese Font", narration=dict(
                backend="kokoro", python=sys.executable, model_directory="models", voice="zm_010",
            ),
        )), encoding="utf-8")

    def init(self, name="portable", *extra):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/init_project.py"),
             "--runtime", str(self.runtime), "--workspace", str(self.base / "workspace"),
             "--name", name, *extra],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        )

    def test_relative_paths_use_configuration_directory(self):
        result = read_runtime(self.runtime)
        self.assertEqual(result["narration"]["model_directory"], str(self.models.resolve()))
        checked = self.init("portable", "--check")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)["narration"]["model_directory"], str(self.models.resolve()))
        self.assertFalse((self.base / "workspace").exists())

    def test_existing_project_is_preserved(self):
        first = self.init()
        self.assertEqual(first.returncode, 0, first.stderr)
        project = self.base / "workspace/outputs/portable-project"
        marker = project / "user-work.txt"
        marker.write_text("已有改动", encoding="utf-8")
        second = self.init()
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("不覆盖", second.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "已有改动")
        lesson = json.loads((project / "lesson.json").read_text(encoding="utf-8"))
        self.assertEqual(lesson["font"], "Test Chinese Font")

    def test_project_name_cannot_escape_workspace(self):
        result = self.init("../outside")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / "workspace").exists())

    def test_missing_model_is_reported_before_project_creation(self):
        (self.models / "kokoro-v1_1-zh.pth").unlink()
        result = self.init()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("模型权重", result.stderr)
        self.assertFalse((self.base / "workspace").exists())

    def test_explicit_model_directory_does_not_read_missing_config(self):
        result = subprocess.run([
            sys.executable, str(ROOT / "scripts/narrate_kokoro.py"),
            "--lesson", str(ROOT / "assets/project-template/lesson.json"),
            "--output-directory", str(self.base / "audio"),
            "--model-directory", str(self.base / "missing-model"),
            "--runtime", str(self.base / "missing-runtime.json"),
        ], capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("本地模型文件缺失", result.stderr)
        self.assertNotIn("找不到本机配置", result.stderr)
        self.assertFalse((self.base / "audio").exists())

    def test_missing_config_gives_setup_instruction(self):
        with self.assertRaisesRegex(FileNotFoundError, "configure_runtime.py"):
            read_runtime(self.base / "missing.json")

    @unittest.skipUnless(os.name == "nt", "初始化入口使用 Windows PowerShell")
    def test_setup_reuses_existing_config_without_writing_it(self):
        before = self.runtime.read_bytes()
        result = subprocess.run([
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(ROOT / "scripts/setup.ps1"), "-RuntimePath", str(self.runtime),
        ], cwd=self.base, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.runtime.read_bytes(), before)
        self.assertFalse((self.base / "workspace").exists())

    @unittest.skipUnless(os.name == "nt", "初始化入口使用 Windows PowerShell")
    def test_setup_reports_invalid_explicit_environment_before_installing(self):
        output = self.base / "new-runtime.json"
        result = subprocess.run([
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(ROOT / "scripts/setup.ps1"), "-RuntimePath", str(output),
            "-ManimPython", str(self.base / "missing-python.exe"),
            "-TtsPython", str(self.base / "missing-python.exe"),
        ], cwd=self.base, capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())
        self.assertIn("指定的 Python 不存在", result.stderr)


if __name__ == "__main__":
    unittest.main()
