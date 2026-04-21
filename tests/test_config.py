from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vampire_storyteller.config import AppConfig, load_config


class ConfigTests(unittest.TestCase):
    def test_load_config_defaults_without_files_or_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "app_config.json"
            local_config_path = Path(temp_dir) / "app_config.local.json"
            dotenv_path = Path(temp_dir) / ".env"
            with patch.dict(os.environ, {}, clear=True):
                config = load_config(
                    config_path=config_path,
                    local_config_path=local_config_path,
                    dotenv_path=dotenv_path,
                )

        self.assertIsInstance(config, AppConfig)
        self.assertIsNone(config.openai_api_key)
        self.assertEqual(config.openai_model, "gpt-4.1-mini")

    def test_load_config_reads_openai_model_and_dotenv_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "app_config.json"
            local_config_path = temp_path / "app_config.local.json"
            dotenv_path = temp_path / ".env"
            config_path.write_text(json.dumps({"openai_model": "gpt-4.1"}), encoding="utf-8")
            dotenv_path.write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                config = load_config(
                    config_path=config_path,
                    local_config_path=local_config_path,
                    dotenv_path=dotenv_path,
                )

        self.assertEqual(config.openai_api_key, "test-key")
        self.assertEqual(config.openai_model, "gpt-4.1")

    def test_environment_secret_overrides_dotenv_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "app_config.json"
            dotenv_path = temp_path / ".env"
            config_path.write_text(json.dumps({"openai_model": "gpt-4.1-mini"}), encoding="utf-8")
            dotenv_path.write_text("OPENAI_API_KEY=file-key\n", encoding="utf-8")

            with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}, clear=True):
                config = load_config(config_path=config_path, dotenv_path=dotenv_path)

        self.assertEqual(config.openai_api_key, "env-key")
        self.assertEqual(config.openai_model, "gpt-4.1-mini")


if __name__ == "__main__":
    unittest.main()
