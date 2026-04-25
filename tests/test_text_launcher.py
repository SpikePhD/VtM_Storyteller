from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


class TextLauncherTests(unittest.TestCase):
    def test_launcher_files_exist(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        self.assertTrue((repo_root / "run_text_adventure.py").exists())
        self.assertTrue((repo_root / "run_text_adventure.bat").exists())

    def test_batch_launcher_prefers_local_venv_python(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        bat_text = (repo_root / "run_text_adventure.bat").read_text(encoding="utf-8")

        self.assertIn('%~dp0.venv\\Scripts\\python.exe', bat_text)
        self.assertIn('where python', bat_text)
        self.assertIn('python "%~dp0run_text_adventure.py" %*', bat_text)

    def test_python_launcher_imports_cli_entrypoint_directly(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        py_text = (repo_root / "run_text_adventure.py").read_text(encoding="utf-8")

        self.assertIn("from vampire_storyteller.cli import run_cli", py_text)

    def test_root_text_launcher_is_runnable(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        launcher = repo_root / "run_text_adventure.py"
        proc = subprocess.run(
            [sys.executable, str(launcher)],
            input="/quit\n",
            text=True,
            capture_output=True,
            cwd=repo_root,
            timeout=30,
        )

        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("Vampire: The Masquerade storyteller prototype", proc.stdout)
        self.assertIn("Goodbye.", proc.stdout)
        self.assertNotIn("RuntimeWarning", proc.stderr)


if __name__ == "__main__":
    unittest.main()
