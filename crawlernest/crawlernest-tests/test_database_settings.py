from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from crawlernest.core.database.settings import DatabaseSettings


class TestDatabaseSettings(unittest.TestCase):
    def test_localhost_defaults_match_demo_database_credentials(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = DatabaseSettings.from_env()

        self.assertEqual(settings.host, "127.0.0.1")
        self.assertEqual(settings.port, 5432)
        self.assertEqual(settings.database, "clawer")
        self.assertEqual(settings.user, "test")
        self.assertEqual(settings.password, "test")

    def test_environment_password_overrides_localhost_default(self) -> None:
        with patch.dict(os.environ, {"CRAWLERNEST_PG_PASSWORD": "custom"}, clear=True):
            settings = DatabaseSettings.from_env()

        self.assertEqual(settings.password, "custom")


if __name__ == "__main__":
    unittest.main()
