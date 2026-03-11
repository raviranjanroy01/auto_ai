"""
Desktop G-Board — Configuration
=================================
Centralized configuration for all subsystems.
"""

import os
import yaml
import logging

logger = logging.getLogger(__name__)

# ─── Default Configuration ───────────────────────────────────────
DEFAULTS = {
    "general": {
        "app_name": "Desktop G-Board",
        "version": "0.2.0",
        "log_level": "INFO",
        "hook_mode": "fallback",        # "native" (C++ service) or "fallback" (pynput)
    },
    "autocorrect": {
        "enabled": True,
        "max_edit_distance": 2,
        "min_word_length": 2,
    },
    "prediction": {
        "enabled": True,
        "ngram_order": 3,
        "top_k": 5,
    },
    "inference": {
        "offline_only": False,
        "local": {
            "llm_model_path": "",       # Path to .gguf model for llama.cpp
            "onnx_model_path": "",      # Path to .onnx model
        },
        "cloud": {
            "primary_provider": "anthropic",    # "anthropic" or "openai"
            "anthropic_api_key": "",            # Or set ANTHROPIC_API_KEY env var
            "openai_api_key": "",               # Or set OPENAI_API_KEY env var
            "anthropic_model": "claude-sonnet-4-20250514",
            "openai_model": "gpt-4",
        },
    },
    "context": {
        "max_context_length": 2048,
        "max_global_context": 4096,
        "max_tracked_windows": 32,
    },
    "ui": {
        "overlay_enabled": True,
        "overlay_opacity": 0.95,
        "overlay_width": 280,
        "follow_caret": True,
        "caret_poll_interval_ms": 50,
    },
    "user_model": {
        "learning_enabled": True,
        "save_interval": 300,           # seconds
        "data_directory": "data/user_data",
    },
    "hotkeys": {
        "code_assist": "ctrl+j",
        "elaborate": "ctrl+e",
        "dismiss": "escape",
    },
}


class Config:
    """Application configuration manager."""

    def __init__(self, config_path: str = None):
        self._config = self._deep_copy(DEFAULTS)

        # Try loading from file
        if config_path and os.path.exists(config_path):
            self._load_from_file(config_path)
        else:
            # Try default locations
            for path in ["config.yaml", "config/settings.yaml", "config.yml"]:
                if os.path.exists(path):
                    self._load_from_file(path)
                    break

    def _load_from_file(self, path: str):
        """Load config from YAML, merging with defaults."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}

            self._deep_merge(self._config, user_config)
            logger.info("Loaded config from: %s", path)
        except Exception as e:
            logger.warning("Failed to load config from %s: %s", path, e)

    def get(self, section: str, key: str = None, default=None):
        """Get a config value. If key is None, returns the whole section."""
        section_data = self._config.get(section, {})
        if key is None:
            return section_data
        if isinstance(section_data, dict):
            return section_data.get(key, default)
        return default

    def get_section(self, section: str) -> dict:
        """Get an entire config section as a dict."""
        return self._config.get(section, {})

    def set(self, section: str, key: str, value):
        """Set a config value."""
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = value

    def save(self, path: str = "config.yaml"):
        """Save current configuration to YAML."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)
        logger.info("Config saved to: %s", path)

    def as_dict(self) -> dict:
        """Return the full config as a dictionary."""
        return self._deep_copy(self._config)

    @staticmethod
    def _deep_merge(base: dict, override: dict):
        """Recursively merge override into base."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                Config._deep_merge(base[key], value)
            else:
                base[key] = value

    @staticmethod
    def _deep_copy(d: dict) -> dict:
        """Simple deep copy for nested dicts."""
        import copy
        return copy.deepcopy(d)

    def __repr__(self):
        return f"Config(sections={list(self._config.keys())})"
