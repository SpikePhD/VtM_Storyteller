from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


class EntrypointHygieneTests(unittest.TestCase):
    def test_cli_module_runs_without_runtime_warning(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [sys.executable, "-W", "default", "-m", "vampire_storyteller.cli"],
            input="quit\n",
            text=True,
            capture_output=True,
            cwd=repo_root,
            timeout=30,
        )

        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertNotIn("RuntimeWarning", proc.stderr)
        self.assertNotIn("already in sys.modules", proc.stderr)

    def test_gui_module_runs_without_runtime_warning(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [sys.executable, "-W", "default", "-m", "vampire_storyteller.gui_app"],
            text=True,
            capture_output=True,
            cwd=repo_root,
            timeout=30,
        )

        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertNotIn("RuntimeWarning", proc.stderr)
        self.assertNotIn("already in sys.modules", proc.stderr)


if __name__ == "__main__":
    unittest.main()
