
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import unicodedata
import json
from pathlib import Path
from abc import ABC, abstractmethod



class FestivalError(Exception):
    """Erreur métier de base du festival."""


class FestivalNotFoundError(FestivalError, ValueError):
    """Une ressource demandée n'existe pas."""


class FestivalConflictError(FestivalError, ValueError):
    """Une règle du festival empêche l'opération."""


class FestivalValidationError(FestivalError, ValueError):
    """Une valeur fournie est invalide."""


class FestivalStorageError(FestivalError):
    """Le fichier de données ne peut pas être lu ou écrit."""



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
    name: str
    capacity: int
    address: str

    @property
    def slug(self) -> str:
        return slugify(self.name)


@dataclass(eq=False)
class Artist:
    name: str
    bio: str
    photo_url: str

    @property
    def slug(self) -> str:
        return slugify(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Artist):
            return NotImplemented
        return self.slug == other.slug


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
        if not 1 <= duration_minutes <= 360:
            raise FestivalValidationError(
                "Duration must be between 1 and 360 minutes."
            )

        self.id = identifier
        self.title = title
        self.venue = venue
        self.start = start
        self.duration_minutes = duration_minutes
        self.description = description

        # Informations reliées par la classe Festival.
        self._venue_name = venue
        self._venue_capacity = None
        self._artist_names = {}

    @abstractmethod
    def summary(self) -> str:
        """Retourne le résumé propre à chaque type de performance."""
        raise NotImplementedError

    def artist_slugs(self) -> set[str]:
        """Retourne les identifiants des artistes impliqués."""
        raise NotImplementedError

    def involves(self, artist_slug: str) -> bool:
        return artist_slug in self.artist_slugs()

    def role_of(self, artist_slug: str) -> str | None:
        """Retourne le rôle de l'artiste dans cette performance."""
        return None

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.duration_minutes)

    @property
    def festival_day(self) -> date:
        return (self.start - timedelta(hours=6)).date()

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

    def to_view(
        self,
        venue_name: str,
        artists: list[dict],
    ) -> dict:
        """Retourne les champs communs utilisés par l'interface."""
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue,
            "venue_name": venue_name,
            "start": self.start.isoformat(timespec="minutes"),
            "end": self.end.isoformat(timespec="minutes"),
            "duration_minutes": self.duration_minutes,
            "festival_day": self.festival_day.isoformat(),
            "description": self.description,
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
    kind = "solo"

    def __init__(
        self,
        *args,
        artist: str,
        min_age: int | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        if min_age is not None and not 0 <= min_age <= 18:
            raise FestivalValidationError(
                 "Minimum age must be between 0 and 18."
            )

        self.artist = artist
        self.min_age = min_age

    def artist_slugs(self) -> set[str]:
        return {self.artist}

    def summary(self) -> str:
        return self._artist_names.get(self.artist, self.artist)

    def to_view(
        self,
        venue_name: str,
        artists: list[dict],
    ) -> dict:
        view = super().to_view(venue_name, artists)
        view.update({
            "artist": self.artist,
            "min_age": self.min_age,
        })
        return view

    def role_of(self, artist_slug: str) -> str | None:
        if self.artist == artist_slug:
            return "solo"
        return None

    def to_data(self) -> dict:
        data = super().to_data()
        data.update({
            "artist": self.artist,
            "min_age": self.min_age,
        })
        return data


class Lineup(Performance):
    kind = "lineup"

    def __init__(
        self,
        *args,
        host: str,
        acts: list[str],
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        if len(acts) < 2:
            raise FestivalValidationError(
                "A lineup must have at least two acts."
            )

        if len(acts) != len(set(acts)):
            raise FestivalValidationError(
                "Each act must appear only once."
            )

        if host in acts:
            raise FestivalValidationError(
                "The host cannot also be an act."
            )

        minimum_duration = (
            10 * len(acts) + 3 * (len(acts) - 1)
        )

        if self.duration_minutes < minimum_duration:
            raise FestivalValidationError(
                f"A lineup with {len(acts)} acts needs at least "
                f"{minimum_duration} minutes."
            )

        self.host = host
        self.acts = list(acts)

    def artist_slugs(self) -> set[str]:
        return {self.host, *self.acts}

    def summary(self) -> str:
        host_name = self._artist_names.get(
            self.host,
            self.host,
        )
        act_names = [
            self._artist_names.get(act, act)
            for act in self.acts
        ]

        return (
            f"hosted by {host_name}, "
            f"with {', '.join(act_names)}"
        )

    #####
    def role_of(self, artist_slug: str) -> str | None:
        if self.host == artist_slug:
            return "host"
        if artist_slug in self.acts:
            return "act"
        return None

    def to_view(
        self,
        venue_name: str,
        artists: list[dict],
    ) -> dict:
        view = super().to_view(venue_name, artists)
        view.update({
            "host": self.host,
            "acts": self.acts,
        })
        return view

    def to_data(self) -> dict:
        data = super().to_data()
        data.update({
            "host": self.host,
            "acts": self.acts,
        })
        return data


class Workshop(Performance):
    kind = "workshop"

    def __init__(
        self,
        *args,
        teacher: str,
        max_participants: int,
        participants: list[str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        if max_participants < 1:
            raise FestivalValidationError(
                "A workshop must have at least one place."
            )

        self.teacher = teacher
        self.max_participants = max_participants
        self.participants = list(participants or [])

    @property
    def places(self) -> int:
        if self._venue_capacity is None:
            return self.max_participants

        return min(
            self.max_participants,
            self._venue_capacity,
        )

    @property
    def places_left(self) -> int:
        return self.places - len(self.participants)

    def artist_slugs(self) -> set[str]:
        return {self.teacher}

    def summary(self) -> str:
        teacher_name = self._artist_names.get(
            self.teacher,
            self.teacher,
        )

        return (
            f"with {teacher_name}, "
            f"{len(self.participants)}/{self.places} places taken"
        )

    #####
    def role_of(self, artist_slug: str) -> str | None:
        if self.teacher == artist_slug:
            return "teacher"
        return None

    def to_view(
        self,
        venue_name: str,
        artists: list[dict],
    ) -> dict:
        view = super().to_view(venue_name, artists)
        view.update({
            "teacher": self.teacher,
            "max_participants": self.max_participants,
            "participants": self.participants,
            "places_left": self.places_left,
        })
        return view

    def to_data(self) -> dict:
        data = super().to_data()
        data.update({
            "teacher": self.teacher,
            "max_participants": self.max_participants,
            "participants": self.participants,
        })
        return data


# Conversion du type de performance en classe Python.
PERFORMANCE_CLASSES = {
    "solo": SoloShow,
    "lineup": Lineup,
    "workshop": Workshop,
}

DATA_FILE = Path(__file__).parent / "data" / "festival.json"


def load_festival_objects(data: dict | None = None):
    """Charge le JSON et construit les objets du festival."""
    if data is None:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

    venues = [
        Venue(
            name=item["name"],
            capacity=item["capacity"],
            address=item["address"],
        )
        for item in data["venues"]
    ]

    artists = [
        Artist(
            name=item["name"],
            bio=item.get("bio", ""),
            photo_url=item.get("photo_url", ""),
        )
        for item in data["artists"]
    ]

    performance_fields = {
        "solo": lambda item: {
            "artist": item["artist"],
            "min_age": item.get("min_age"),
        },
        "lineup": lambda item: {
            "host": item["host"],
            "acts": item.get("acts", []),
        },
        "workshop": lambda item: {
            "teacher": item["teacher"],
            "max_participants": item["max_participants"],
            "participants": item.get("participants", []),
        },
    }

    performances = []

    for item in data["performances"]:
        start = datetime.fromisoformat(item["start"])

        identifier = item.get("id") or (
            f'{item["venue"]}-{start:%Y-%m-%d-%H%M}'
        )

        common = {
            "identifier": identifier,
            "title": item["title"],
            "venue": item["venue"],
            "start": start,
            "duration_minutes": item["duration_minutes"],
            "description": item.get("description", ""),
        }

        kind = item["kind"]

        if kind not in PERFORMANCE_CLASSES:
            raise ValueError(
                f"Unknown performance kind: {kind}"
            )

        performance_class = PERFORMANCE_CLASSES[kind]
        extra_fields = performance_fields[kind](item)

        performance = performance_class(
            **common,
            **extra_fields,
        )
        performances.append(performance)

    return venues, artists, performances


class Festival:
    """Gère les lieux, les artistes et les performances du festival."""

    def __init__(
        self,
        venues: list[Venue],
        artists: list[Artist],
        performances: list[Performance],
        name: str = "",
        first_day: date | None = None,
        last_day: date | None = None,
    ) -> None:
        self.name = name
        self.first_day = first_day
        self.last_day = last_day
        self.venues = venues
        self.artists = artists
        self._performances = list(performances)

        artist_names = {
            artist.slug: artist.name
            for artist in self.artists
        }

        for performance in self._performances:
            venue = self.find_venue(performance.venue)

            if venue is not None:
                performance._venue_name = venue.name
                performance._venue_capacity = venue.capacity

            performance._artist_names = artist_names

    
    @property
    def performances(self) -> list[Performance]:
        """Retourne une copie de la liste des performances."""
        return self._performances.copy()


    @property
    def days(self) -> list[date]:
        if self.first_day is None or self.last_day is None:
            return sorted({
                performance.festival_day
                for performance in self._performances
            })

        result = []
        current = self.first_day

        while current <= self.last_day:
            result.append(current)
            current += timedelta(days=1)

        return result

    def find_venue(self, slug: str) -> Venue | None:
        for venue in self.venues:
            if venue.slug == slug:
                return venue
        return None

    def find_artist(self, slug: str) -> Artist | None:
        for artist in self.artists:
            if artist.slug == slug:
                return artist
        return None

    def find_performance(
        self,
        identifier: str,
    ) -> Performance | None:
        for performance in self._performances:
            if performance.id == identifier:
                return performance
        return None

    def performances_for_artist(
        self,
        slug: str,
    ) -> list[Performance]:
        return sorted([
            performance
            for performance in self._performances
            if performance.involves(slug)
        ])

    def performances_for_venue(
        self,
        slug: str,
    ) -> list[Performance]:
        return sorted([
            performance
            for performance in self._performances
            if performance.venue == slug
        ])

    @staticmethod
    def _artist_slugs(
        performance: Performance,
    ) -> set[str]:
        return performance.artist_slugs()

    @staticmethod
    def _conflicts(
        first: Performance,
        second: Performance,
    ) -> bool:
        gap = timedelta(minutes=30)

        return (
            first.start < second.end + gap
            and second.start < first.end + gap
        )

    
    def validate_performance(
        self,
        performance: Performance,
    ) -> None:
        if self.find_venue(performance.venue) is None:
            raise FestivalNotFoundError(
                f"Unknown venue '{performance.venue}'."
            )

        if not 1 <= performance.duration_minutes <= 360:
            raise FestivalValidationError(
                "Duration must be between 1 and 360 minutes."
            )

        day = performance.festival_day

        if (
            self.first_day is not None
            and day < self.first_day
        ) or (
            self.last_day is not None
            and day > self.last_day
        ):
            raise FestivalConflictError(
                f"{day.isoformat()} is not a day of the festival."
            )


        for slug in self._artist_slugs(performance):
            if self.find_artist(slug) is None:
                raise FestivalNotFoundError(
                    f"Unknown artist '{slug}'."
                )

        for existing in self._performances:
            if existing.id == performance.id:
                raise FestivalConflictError(
                    f"A performance with ID '{performance.id}' "
                    "already exists."
                )

            if (
                existing.venue == performance.venue
                and self._conflicts(performance, existing)
            ):
                venue = self.find_venue(existing.venue)
                venue_name = (
                    venue.name if venue else existing.venue
                )

                raise FestivalConflictError(
                    f"{venue_name} is already booked "
                    f"for {existing.title}."
                )

            shared = (
                self._artist_slugs(performance)
                & self._artist_slugs(existing)
            )

            if shared and self._conflicts(performance, existing):
                slug = sorted(shared)[0]
                artist = self.find_artist(slug)
                artist_name = artist.name if artist else slug

                raise FestivalConflictError(
                    f"{artist_name} is on stage "
                    f"in {existing.title}."
                )

    def add_performance(
        self,
        performance: Performance,
    ) -> None:
        self.validate_performance(performance)

        venue = self.find_venue(performance.venue)

        if venue is not None:
            performance._venue_name = venue.name
            performance._venue_capacity = venue.capacity

        performance._artist_names = {
            artist.slug: artist.name
            for artist in self.artists
        }

        self._performances.append(performance)

    

    def cancel_performance(
        self,
        identifier: str,
    ) -> Performance:
        performance = self.find_performance(identifier)

        if performance is None:
            raise FestivalNotFoundError(
                f"No performance '{identifier}'."
            )

        self._performances.remove(performance)
        return performance

    def programme_for_day(
        self,
        day: date,
    ) -> list[Performance]:
        return sorted([
            performance
            for performance in self._performances
            if performance.festival_day == day
        ])

    def now_playing(
        self,
        moment: datetime,
    ) -> list[Performance]:
        return sorted([
            performance
            for performance in self._performances
            if performance.start <= moment < performance.end
        ])

    def up_next(
        self,
        moment: datetime,
        limit: int = 3,
    ) -> list[Performance]:
        upcoming = sorted([
            performance
            for performance in self._performances
            if performance.start > moment
        ])

        return upcoming[:limit]



def load_festival() -> Festival:
    """Charge le festival depuis le fichier JSON."""
    with DATA_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    venues, artists, performances = load_festival_objects(data)

    return Festival(
        venues=venues,
        artists=artists,
        performances=performances,
        name=data["name"],
        first_day=date.fromisoformat(data["first_day"]),
        last_day=date.fromisoformat(data["last_day"]),
    )


def save_festival(festival: Festival) -> None:
    """Sauvegarde les données du festival dans le fichier JSON."""

    data = {
        "name": festival.name,
        "first_day": (
            festival.first_day.isoformat()
            if festival.first_day is not None
            else None
        ),
        "last_day": (
            festival.last_day.isoformat()
            if festival.last_day is not None
            else None
        ),
        "venues": [
            {
                "name": venue.name,
                "capacity": venue.capacity,
                "address": venue.address,
            }
            for venue in festival.venues
        ],
        "artists": [
            {
                "name": artist.name,
                "bio": artist.bio,
                "photo_url": artist.photo_url,
            }
            for artist in festival.artists
        ],
        "performances": [
            performance.to_data()
            for performance in festival.performances
        ],
    }

    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
