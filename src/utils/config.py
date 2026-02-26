"""
Configuration Management

Centralized configuration for the AutoAI typing assistant.
"""

import os
import yaml


# Default configuration values
DEFAULTS = {
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
    "user_model": {
        "learning_enabled": True,
        "save_interval": 300,  # seconds
        "data_directory": "data/user_data",
    },
}


class Config:
    """Application configuration manager."""

    def __init__(self, config_path: str = None):
        """
        Initialize configuration.

        Args:
            config_path: Optional path to a YAML config file.
        """
        self._config = dict(DEFAULTS)

        if config_path and os.path.exists(config_path):
            self._load_from_file(config_path)

    def _load_from_file(self, path: str):
        """Load config from a YAML file, merging with defaults."""
        with open(path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}

        # Deep merge user config over defaults
        for section, values in user_config.items():
            if section in self._config and isinstance(values, dict):
                self._config[section].update(values)
            else:
                self._config[section] = values

    def get(self, section: str, key: str, default=None):
        """Get a config value."""
        return self._config.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value):
        """Set a config value."""
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = value

    def save(self, path: str):
        """Save current configuration to a YAML file."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self._config, f, default_flow_style=False)

    def __repr__(self):
        return f"Config(sections={list(self._config.keys())})"
