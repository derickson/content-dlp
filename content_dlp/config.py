from pathlib import Path
import yaml

DEFAULTS = {
    "download_dir": "~/content-dlp-data",
    "youtube": {
        "ytdlp_path": None,
    },
    "podcast": {
        "user_agent": "content-dlp/0.1",
    },
}

SETTINGS_PATH = Path(__file__).parent.parent / "settings.yaml"


def load_config() -> dict:
    config = dict(DEFAULTS)
    if SETTINGS_PATH.exists():
        with open(SETTINGS_PATH) as f:
            user = yaml.safe_load(f) or {}
        for key, val in user.items():
            if isinstance(val, dict) and isinstance(config.get(key), dict):
                config[key] = {**config[key], **val}
            else:
                config[key] = val
    else:
        with open(SETTINGS_PATH, "w") as f:
            yaml.dump(DEFAULTS, f, default_flow_style=False)
    config["download_dir"] = str(Path(config["download_dir"]).expanduser())
    return config
