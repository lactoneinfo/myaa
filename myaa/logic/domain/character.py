import yaml
from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache
from typing import Dict


@dataclass
class Character:
    name: str
    description: str


@lru_cache(maxsize=None)
def load_character(
    name: str, config_dir: Path = Path("config/characters")
) -> Character:
    path = config_dir / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Character config not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Character config must be a YAML mapping (dict): {path}")
    except yaml.YAMLError as e:
        raise ValueError(f"YAML parse error in {path}:\n{e}") from e

    return Character(
        name=data.get("name", name),
        description=data.get("description", ""),
    )
