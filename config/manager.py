"""Persistent, encrypted per-user configuration for VOplease."""

from __future__ import annotations

import copy
import json
import os
import shutil
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class ConfigManager:
    def __init__(self):
        appdata = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
        self.config_dir = appdata / "VOplease"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "settings.json"
        self.key_file = self.config_dir / ".key"
        self._migrate_legacy_config()
        self._init_key()

    def _migrate_legacy_config(self) -> None:
        """Move the old project-local settings to AppData once."""
        legacy_dir = Path(__file__).resolve().parent
        legacy_settings = legacy_dir / "settings.json"
        legacy_key = legacy_dir / ".key"
        if not self.config_file.exists() and legacy_settings.exists():
            shutil.copy2(legacy_settings, self.config_file)
        if not self.key_file.exists() and legacy_key.exists():
            shutil.copy2(legacy_key, self.key_file)

    def _init_key(self) -> None:
        if self.key_file.exists():
            self.key = self.key_file.read_bytes()
        else:
            self.key = Fernet.generate_key()
            self.key_file.write_bytes(self.key)
        self.cipher = Fernet(self.key)

    def _encrypt(self, value: str) -> str:
        return self.cipher.encrypt(value.encode("utf-8")).decode("ascii")

    def _decrypt(self, value: str) -> str:
        # Older builds accidentally encrypted existing entries again whenever a
        # different provider key was saved. Unwrap those layers during migration.
        result = value
        for _ in range(12):
            try:
                result = self.cipher.decrypt(result.encode("ascii")).decode("utf-8")
            except (InvalidToken, ValueError, UnicodeError):
                break
        return result

    @staticmethod
    def _defaults() -> dict:
        return {
            "providers": {},
            "last_provider": "gemini",
            "last_voice": "",
            "speed": 1.0,
            "output_format": "mp3",
            "output_directory": str(Path.home() / "Documents" / "VOplease Audio"),
            "theme": "dark",
        }

    def load(self) -> dict:
        data = self._defaults()
        if self.config_file.exists():
            try:
                loaded = json.loads(self.config_file.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data.update(loaded)
            except (OSError, json.JSONDecodeError):
                pass

        providers = data.setdefault("providers", {})
        for info in providers.values():
            encrypted = info.get("api_key", "") if isinstance(info, dict) else ""
            if encrypted:
                info["api_key"] = self._decrypt(encrypted)
        return data

    def save(self, data: dict) -> None:
        encrypted_data = copy.deepcopy(data)
        for info in encrypted_data.setdefault("providers", {}).values():
            if isinstance(info, dict) and info.get("api_key"):
                info["api_key"] = self._encrypt(info["api_key"])
        temp_file = self.config_file.with_suffix(".tmp")
        temp_file.write_text(json.dumps(encrypted_data, indent=2), encoding="utf-8")
        temp_file.replace(self.config_file)

    def get_api_key(self, provider: str) -> str:
        return self.load().get("providers", {}).get(provider, {}).get("api_key", "")

    def set_api_key(self, provider: str, api_key: str) -> None:
        data = self.load()
        data.setdefault("providers", {}).setdefault(provider, {})["api_key"] = api_key
        self.save(data)

    def get_provider_info(self, provider: str) -> dict:
        return self.load().get("providers", {}).get(provider, {}).copy()

    def update_provider_info(self, provider: str, info: dict) -> None:
        data = self.load()
        data.setdefault("providers", {}).setdefault(provider, {}).update(info)
        self.save(data)


config = ConfigManager()
