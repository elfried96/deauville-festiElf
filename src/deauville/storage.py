
from abc import ABC, abstractmethod
import json
from pathlib import Path
from typing import Any


class Storage(ABC):
    """Interface abstraite pour le stockage des données."""

    @abstractmethod
    def load(self) -> dict[str, Any]:
        """Charge les données et les retourne."""
        raise NotImplementedError

    @abstractmethod
    def save(self, data: dict[str, Any]) -> None:
        """Enregistre les données."""
        raise NotImplementedError


class JSONStorage(Storage):
    """Stockage des données dans un fichier JSON."""

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)

    def load(self) -> dict[str, Any]:
        with self.file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Le fichier JSON doit contenir un objet.")

        return data

    def save(self, data: dict[str, Any]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        with self.file_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
