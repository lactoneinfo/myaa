import yaml
from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache


@dataclass
class Character:
    id: str
    name: str
    description: str


@lru_cache(maxsize=None)
def load_character(id: str, config_dir: Path = Path("config/characters")) -> Character:
    path = config_dir / f"{id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Character config not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Character config must be a YAML mapping (dict): {path}")
    except yaml.YAMLError as e:
        raise ValueError(f"YAML parse error in {path}:\n{e}") from e

    return Character(
        id=id,
        name=data.get("name", id),
        description=data.get("description", ""),
    )


def available_characters(config_dir: Path = Path("config/characters")) -> list[str]:
    return [
        path.stem for path in config_dir.glob("*.yaml") if not path.name.startswith("_")
    ]


def get_display_name(char_id: str, config_dir=Path("config/characters")) -> str:
    try:
        char = load_character(char_id, config_dir)
        return char.name
    except Exception:
        return char_id
