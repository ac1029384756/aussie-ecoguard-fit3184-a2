"""Configuration defaults must work in both the source and packaged layouts."""

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from app import settings as settings_module


class SettingsLayoutTests(unittest.TestCase):
    def test_source_defaults_find_repository_configuration(self):
        config = Path(__file__).resolve().parents[3] / "config"
        with patch.dict(os.environ, {}, clear=True):
            settings = settings_module.Settings.from_env()
        self.assertEqual(Path(settings.manifest_path), config / "model.example.json")
        self.assertEqual(Path(settings.taxonomy_path), config / "taxonomy.json")

    def test_container_defaults_do_not_require_source_tree_depth(self):
        with patch.object(settings_module, "__file__", "/app/app/settings.py"), \
                patch.dict(os.environ, {}, clear=True):
            settings = settings_module.Settings.from_env()
        self.assertEqual(Path(settings.manifest_path), Path("/config/model.example.json"))
        self.assertEqual(Path(settings.taxonomy_path), Path("/config/taxonomy.json"))

    def test_container_environment_paths_override_defaults(self):
        overrides = {
            "MODEL_MANIFEST_PATH": "/release/locked.json",
            "TAXONOMY_PATH": "/release/taxonomy.json",
            "MODEL_MANIFEST_SHA256": "a" * 64,
        }
        with patch.object(settings_module, "__file__", "/app/app/settings.py"), \
                patch.dict(os.environ, overrides, clear=True):
            settings = settings_module.Settings.from_env()
        self.assertEqual(settings.manifest_path, overrides["MODEL_MANIFEST_PATH"])
        self.assertEqual(settings.taxonomy_path, overrides["TAXONOMY_PATH"])
        self.assertEqual(settings.manifest_sha256, overrides["MODEL_MANIFEST_SHA256"])


if __name__ == "__main__":
    unittest.main()
