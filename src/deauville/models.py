"""Les objets du festival : lieux, artistes et la famille des performances."""

import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from .errors import (
    FestivalConflictError,
    FestivalValidationError,
)


def slugify(text: str) -> str:
    """Transforme un nom en identifiant simple, sans accents."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()

    slug = []
    for character in text:
        if character.isalnum():
            slug.append(character)
        elif slug and slug[-1] != "-":
            slug.append("-")

    return "".join(slug).strip("-")


@dataclass
class Venue:
    """Un lieu du festival ; son slug vient de son nom."""

    name: str
    capacity: int
    address: str

    @property
    def slug(self) -> str:
        return slugify(self.name)

    def to_view(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "capacity": self.capacity,
            "address": self.address,
        }

    def to_data(self) -> dict:
        return {
            "name": self.name,
            "capacity": self.capacity,
            "address": self.address,
        }


@dataclass(eq=False)
class Artist:
    """Un artiste ; deux artistes au même slug sont le même artiste."""

    name: str
    bio: str = ""
    photo_url: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.slug:
            raise FestivalValidationError("Artist name must not be empty.")
        self.name = self.name.strip()

    @property
    def slug(self) -> str:
        return slugify(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Artist):
            return NotImplemented
        return self.slug == other.slug

    def __hash__(self) -> int:
        return hash(self.slug)

    def to_view(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "bio": self.bio,
            "photo_url": self.photo_url,
        }

    def to_data(self) -> dict:
        return {
            "name": self.name,
            "bio": self.bio,
            "photo_url": self.photo_url,
        }


def performance_id(venue: str, start: datetime) -> str:
    """L'identifiant d'une performance : le lieu et l'heure de début."""
    return f"{venue}-{start:%Y-%m-%d-%H%M}"


class Performance(ABC):
    """Classe de base abstraite pour toutes les performances."""

    kind = ""

    def __init__(
        self,
        identifier: str,
        title: str,
        venue: str,
        start: datetime,
        duration_minutes: int,
        description: str = "",
    ) -> None:
        if not title.strip():
            raise FestivalValidationError("Performance title must not be empty.")

        if not 1 <= duration_minutes <= 360:
            raise FestivalValidationError("Duration must be between 1 and 360 minutes.")

        self.id = identifier
        self.title = title.strip()
        self.venue = venue
        self.start = start
        self.duration_minutes = duration_minutes
        self.description = description

        # Informations reliées par la classe Festival.
        self._venue_name = venue
        self._venue_capacity: int | None = None
        self._artist_names: dict[str, str] = {}

    @classmethod
    @abstractmethod
    def kind_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Lit dans `data` les champs propres à ce type de performance."""

    @abstractmethod
    def artist_slugs(self) -> list[str]:
        """Les artistes impliqués, dans l'ordre d'apparition."""

    @abstractmethod
    def role_of(self, artist_slug: str) -> str | None:
        """Le rôle de l'artiste dans cette performance, ou None."""

    @abstractmethod
    def summary(self) -> str:
        """Le résumé en une ligne, propre à chaque type de performance."""

    def involves(self, artist_slug: str) -> bool:
        return artist_slug in self.artist_slugs()

    def register(self, name: str) -> None:
        """Inscrit un participant : seul un atelier l'accepte."""
        raise FestivalValidationError(f"'{self.title}' is not a workshop.")

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.duration_minutes)

    @property
    def festival_day(self) -> date:
        # Une journée du festival se termine à 06:00.
        return (self.start - timedelta(hours=6)).date()

    @property
    def venue_name(self) -> str:
        return self._venue_name

    @property
    def capacity(self) -> int | None:
        """Les places : celles du lieu, sauf pour un atelier."""
        return self._venue_capacity

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Performance):
            return NotImplemented

        return (self.start, self._venue_name) < (
            other.start,
            other._venue_name,
        )

    def __str__(self) -> str:
        return (
            f"{self.start:%H:%M}-{self.end:%H:%M} | "
            f"{self._venue_name} | {self.title} ({self.kind})"
        )

    def to_view(self, artists: list[dict]) -> dict:
        """Retourne les champs communs utilisés par l'interface."""
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue,
            "venue_name": self._venue_name,
            "start": self.start.isoformat(timespec="minutes"),
            "end": self.end.isoformat(timespec="minutes"),
            "duration_minutes": self.duration_minutes,
            "festival_day": self.festival_day.isoformat(),
            "description": self.description,
            "summary": self.summary(),
            "capacity": self.capacity,
            "artists": artists,
        }

    def to_data(self) -> dict:
        """Retourne les données communes pour le fichier JSON."""
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue,
            "start": self.start.isoformat(timespec="minutes"),
            "duration_minutes": self.duration_minutes,
            "description": self.description,
        }


class SoloShow(Performance):
    """Un seul artiste sur scène, avec un âge minimum facultatif."""

    kind = "solo"

    def __init__(
        self,
        *args: Any,
        artist: str,
        min_age: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        if min_age is not None and not 0 <= min_age <= 18:
            raise FestivalValidationError("Minimum age must be between 0 and 18.")

        self.artist = artist
        self.min_age = min_age

    @classmethod
    def kind_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "artist": data["artist"],
            "min_age": data.get("min_age"),
        }

    def artist_slugs(self) -> list[str]:
        return [self.artist]

    def role_of(self, artist_slug: str) -> str | None:
        return "solo" if self.artist == artist_slug else None

    def summary(self) -> str:
        return self._artist_names.get(self.artist, self.artist)

    def to_view(self, artists: list[dict]) -> dict:
        view = super().to_view(artists)
        view.update(
            {
                "artist": self.artist,
                "min_age": self.min_age,
            }
        )
        return view

    def to_data(self) -> dict:
        data = super().to_data()
        data.update(
            {
                "artist": self.artist,
                "min_age": self.min_age,
            }
        )
        return data


class Lineup(Performance):
    """Un plateau : un animateur et au moins deux numéros."""

    kind = "lineup"

    def __init__(
        self,
        *args: Any,
        host: str,
        acts: list[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        if len(acts) < 2:
            raise FestivalValidationError("A lineup must have at least two acts.")

        if len(acts) != len(set(acts)):
            raise FestivalValidationError("Each act must appear only once.")

        if host in acts:
            raise FestivalValidationError("The host cannot also be an act.")

        # Chaque numéro dure 10 minutes, avec 3 minutes entre deux numéros.
        minimum_duration = 10 * len(acts) + 3 * (len(acts) - 1)

        if self.duration_minutes < minimum_duration:
            raise FestivalValidationError(
                f"A lineup with {len(acts)} acts needs at least "
                f"{minimum_duration} minutes."
            )

        self.host = host
        self._acts = list(acts)

    @classmethod
    def kind_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "host": data["host"],
            "acts": data["acts"],
        }

    @property
    def acts(self) -> list[str]:
        """Une copie : la liste des numéros ne change pas de l'extérieur."""
        return list(self._acts)

    def artist_slugs(self) -> list[str]:
        return [self.host, *self._acts]

    def role_of(self, artist_slug: str) -> str | None:
        if self.host == artist_slug:
            return "host"
        if artist_slug in self._acts:
            return "act"
        return None

    def summary(self) -> str:
        host_name = self._artist_names.get(self.host, self.host)
        act_names = [self._artist_names.get(act, act) for act in self._acts]

        return f"hosted by {host_name}, with {', '.join(act_names)}"

    def to_view(self, artists: list[dict]) -> dict:
        view = super().to_view(artists)
        view.update(
            {
                "host": self.host,
                "acts": self.acts,
            }
        )
        return view

    def to_data(self) -> dict:
        data = super().to_data()
        data.update(
            {
                "host": self.host,
                "acts": self.acts,
            }
        )
        return data


class Workshop(Performance):
    """Un atelier : un professeur et des participants inscrits."""

    kind = "workshop"

    def __init__(
        self,
        *args: Any,
        teacher: str,
        max_participants: int,
        participants: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        if max_participants < 1:
            raise FestivalValidationError("A workshop must have at least one place.")

        participants = list(participants or [])
        if len(participants) > max_participants:
            raise FestivalValidationError(
                f"{len(participants)} participants are registered: "
                f"max_participants cannot be lower."
            )

        self.teacher = teacher
        self.max_participants = max_participants
        self._participants = participants

    @classmethod
    def kind_fields(cls, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "teacher": data["teacher"],
            "max_participants": data["max_participants"],
            "participants": data.get("participants", []),
        }

    @property
    def participants(self) -> list[str]:
        """Une copie : on s'inscrit seulement par `register`."""
        return list(self._participants)

    @property
    def places(self) -> int:
        if self._venue_capacity is None:
            return self.max_participants

        return min(self.max_participants, self._venue_capacity)

    @property
    def capacity(self) -> int:
        return self.places

    @property
    def places_left(self) -> int:
        return self.places - len(self._participants)

    def register(self, name: str) -> None:
        name = name.strip()

        if not name:
            raise FestivalValidationError("Participant name must not be empty.")

        if name in self._participants:
            raise FestivalConflictError(
                f"{name} is already registered for {self.title}."
            )

        if self.places_left <= 0:
            raise FestivalConflictError(f"{self.title} is full.")

        self._participants.append(name)

    def artist_slugs(self) -> list[str]:
        return [self.teacher]

    def role_of(self, artist_slug: str) -> str | None:
        return "teacher" if self.teacher == artist_slug else None

    def summary(self) -> str:
        teacher_name = self._artist_names.get(self.teacher, self.teacher)

        return (
            f"with {teacher_name}, {len(self._participants)}/{self.places} places taken"
        )

    def to_view(self, artists: list[dict]) -> dict:
        view = super().to_view(artists)
        view.update(
            {
                "teacher": self.teacher,
                "max_participants": self.max_participants,
                "participants": self.participants,
                "places_left": self.places_left,
            }
        )
        return view

    def to_data(self) -> dict:
        data = super().to_data()
        data.update(
            {
                "teacher": self.teacher,
                "max_participants": self.max_participants,
                "participants": self.participants,
            }
        )
        return data


# Conversion du type de performance en classe Python.
PERFORMANCE_CLASSES: dict[str, type[Performance]] = {
    cls.kind: cls for cls in (SoloShow, Lineup, Workshop)
}


def performance_from_data(data: dict[str, Any]) -> Performance:
    """Construit la bonne performance à partir d'un dictionnaire.

    Sert au fichier JSON, à l'API et à la ligne de commande : l'id est
    toujours calculé à partir du lieu et de l'heure de début.
    """
    kind = data.get("kind")
    performance_class = PERFORMANCE_CLASSES.get(kind)

    if performance_class is None:
        raise FestivalValidationError("Kind must be solo, lineup or workshop.")

    try:
        start = data["start"]
        if isinstance(start, str):
            start = datetime.fromisoformat(start)

        return performance_class(
            identifier=performance_id(data["venue"], start),
            title=data["title"],
            venue=data["venue"],
            start=start,
            duration_minutes=data["duration_minutes"],
            description=data.get("description", ""),
            **performance_class.kind_fields(data),
        )
    except KeyError as error:
        raise FestivalValidationError(
            f"A {kind} needs the field '{error.args[0]}'."
        ) from None
    except ValueError:
        raise FestivalValidationError(
            f"'{data['start']}' is not a valid date and time."
        ) from None
