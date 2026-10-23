"""Où vivent les données du festival.

Le reste du programme ne connaît que l'interface `Storage` :
le fichier JSON est une implémentation, la mémoire en est une autre
(pratique pour les tests).
"""

import copy
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .errors import FestivalStorageError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_FILE = PROJECT_ROOT / "data" / "festival.json"


class Storage(ABC):
    """Interface abstraite pour le stockage des données."""

    @abstractmethod
    def load(self) -> dict[str, Any]:
        """Charge les données et les retourne."""

    @abstractmethod
    def save(self, data: dict[str, Any]) -> None:
        """Enregistre les données."""


class JSONStorage(Storage):
    """Stockage des données dans un fichier JSON."""

    def __init__(self, file_path: str | Path = DEFAULT_DATA_FILE) -> None:
        self.file_path = Path(file_path)

    def load(self) -> dict[str, Any]:
        try:
            with self.file_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            raise FestivalStorageError(
                f"The data file '{self.file_path}' was not found."
            ) from None
        except json.JSONDecodeError:
            raise FestivalStorageError(
                f"The data file '{self.file_path}' is damaged."
            ) from None

        if not isinstance(data, dict):
            raise FestivalStorageError(
                f"The data file '{self.file_path}' must hold a JSON object."
            )

        return data

    def save(self, data: dict[str, Any]) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            with self.file_path.open("w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.write("\n")
        except OSError as error:
            raise FestivalStorageError(
                f"The data file '{self.file_path}' cannot be written."
            ) from error


class MemoryStorage(Storage):
    """Rien sur le disque : les données restent en mémoire."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = copy.deepcopy(data)

    def load(self) -> dict[str, Any]:
        # Une copie : modifier le résultat ne change pas le stockage.
        return copy.deepcopy(self._data)

    def save(self, data: dict[str, Any]) -> None:
        self._data = copy.deepcopy(data)
