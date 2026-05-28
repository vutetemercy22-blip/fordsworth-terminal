from pathlib import Path
import yaml


BASE_DIR = Path(__file__).resolve().parent.parent


def load_yaml_file(relative_path: str) -> dict:
    """
    Safely load a YAML file relative to the project root.
    """
    file_path = BASE_DIR / relative_path

    if not file_path.exists():
        raise FileNotFoundError(f"YAML file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_settings() -> dict:
    return load_yaml_file("config/settings.yaml")


def load_schedules() -> dict:
    return load_yaml_file("config/schedules.yaml")


def load_model_config() -> dict:
    return load_yaml_file("config/model_config.yaml")