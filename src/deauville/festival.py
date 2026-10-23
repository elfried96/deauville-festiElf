"""Le festival : il garde ses collections et fait respecter les règles."""

from datetime import date, datetime, timedelta

from .errors import (
    FestivalConflictError,
    FestivalError,
    FestivalNotFoundError,
)
from .models import Artist, Performance, Venue, Workshop, performance_from_data
from .storage import Storage

# Écart minimal entre deux performances d'un même lieu ou d'un même artiste.
GAP = timedelta(minutes=30)


class Festival:
    """Gère les lieux, les artistes et les performances du festival.

    Les collections sont privées (`_venues`, `_artists`, `_performances`) :
    on les lit par des propriétés qui renvoient une copie, et on les change
    seulement par des méthodes qui vérifient les règles.
    """

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
        self._venues = list(venues)
        self._artists = list(artists)
        # Les données du fichier sont déjà valides : pas de revalidation.
        self._performances = list(performances)

        for performance in self._performances:
            self._link(performance)

    @property
    def venues(self) -> list[Venue]:
        return list(self._venues)

    @property
    def artists(self) -> list[Artist]:
        return list(self._artists)

    @property
    def performances(self) -> list[Performance]:
        return list(self._performances)

    @property
    def days(self) -> list[date]:
        if self.first_day is None or self.last_day is None:
            return sorted({p.festival_day for p in self._performances})

        result = []
        current = self.first_day

        while current <= self.last_day:
            result.append(current)
            current += timedelta(days=1)

        return result

    # --- Lecture ---------------------------------------------------------

    def find_venue(self, slug: str) -> Venue | None:
        for venue in self._venues:
            if venue.slug == slug:
                return venue
        return None

    def find_artist(self, slug: str) -> Artist | None:
        for artist in self._artists:
            if artist.slug == slug:
                return artist
        return None

    def find_performance(self, identifier: str) -> Performance | None:
        for performance in self._performances:
            if performance.id == identifier:
                return performance
        return None

    def get_venue(self, slug: str) -> Venue:
        venue = self.find_venue(slug)
        if venue is None:
            raise FestivalNotFoundError(f"No venue '{slug}'.")
        return venue

    def get_artist(self, slug: str) -> Artist:
        artist = self.find_artist(slug)
        if artist is None:
            raise FestivalNotFoundError(f"No artist '{slug}'.")
        return artist

    def get_performance(self, identifier: str) -> Performance:
        performance = self.find_performance(identifier)
        if performance is None:
            raise FestivalNotFoundError(f"No performance '{identifier}'.")
        return performance

    def performances_for_artist(self, slug: str) -> list[Performance]:
        return sorted(p for p in self._performances if p.involves(slug))

    def performances_for_venue(self, slug: str) -> list[Performance]:
        return sorted(p for p in self._performances if p.venue == slug)

    def programme(
        self,
        day: date | None = None,
        venue: str | None = None,
    ) -> list[Performance]:
        """Les performances dans l'ordre du programme, filtrées si demandé."""
        if venue is not None:
            self.get_venue(venue)

        return sorted(
            p
            for p in self._performances
            if (day is None or p.festival_day == day)
            and (venue is None or p.venue == venue)
        )

    def programme_for_day(self, day: date) -> list[Performance]:
        return self.programme(day=day)

    def workshops(self) -> list[Workshop]:
        return [p for p in sorted(self._performances) if isinstance(p, Workshop)]

    def now_playing(self, moment: datetime) -> list[Performance]:
        return sorted(p for p in self._performances if p.start <= moment < p.end)

    def up_next(self, moment: datetime, limit: int = 3) -> list[Performance]:
        upcoming = sorted(p for p in self._performances if p.start > moment)
        return upcoming[:limit]

    # --- Règles ----------------------------------------------------------

    @staticmethod
    def _conflicts(first: Performance, second: Performance) -> bool:
        return first.start < second.end + GAP and second.start < first.end + GAP

    def validate_performance(self, performance: Performance) -> None:
        venue = self.get_venue(performance.venue)

        day = performance.festival_day
        if (self.first_day is not None and day < self.first_day) or (
            self.last_day is not None and day > self.last_day
        ):
            raise FestivalConflictError(
                f"{day.isoformat()} is not a day of the festival."
            )

        for slug in performance.artist_slugs():
            if self.find_artist(slug) is None:
                raise FestivalNotFoundError(f"Unknown artist '{slug}'.")

        for existing in self._performances:
            if existing.id == performance.id:
                raise FestivalConflictError(
                    f"A performance with ID '{performance.id}' already exists."
                )

            if not self._conflicts(performance, existing):
                continue

            if existing.venue == performance.venue:
                raise FestivalConflictError(
                    f"{venue.name} is already booked for {existing.title}."
                )

            shared = set(performance.artist_slugs()) & set(existing.artist_slugs())
            if shared:
                artist = self.get_artist(sorted(shared)[0])
                raise FestivalConflictError(
                    f"{artist.name} is on stage in {existing.title}."
                )

    # --- Écriture --------------------------------------------------------

    def _link(self, performance: Performance) -> None:
        """Donne à la performance le nom du lieu et les noms des artistes."""
        venue = self.find_venue(performance.venue)

        if venue is not None:
            performance._venue_name = venue.name
            performance._venue_capacity = venue.capacity

        performance._artist_names = {a.slug: a.name for a in self._artists}

    def add_venue(self, venue: Venue) -> None:
        if self.find_venue(venue.slug) is not None:
            raise FestivalConflictError(f"A venue named '{venue.name}' already exists.")
        self._venues.append(venue)

    def add_artist(self, artist: Artist) -> None:
        if self.find_artist(artist.slug) is not None:
            raise FestivalConflictError(
                f"An artist named '{artist.name}' already exists."
            )

        self._artists.append(artist)

        # Les noms d'artistes des résumés suivent l'ajout.
        for performance in self._performances:
            self._link(performance)

    def add_performance(self, performance: Performance) -> None:
        self.validate_performance(performance)
        self._link(performance)
        self._performances.append(performance)

    def cancel_performance(self, identifier: str) -> Performance:
        performance = self.get_performance(identifier)
        self._performances.remove(performance)
        return performance

    def replace_performance(
        self,
        identifier: str,
        performance: Performance,
    ) -> Performance:
        """Remplace une performance ; si la nouvelle enfreint une règle,
        rien ne change."""
        old = self.get_performance(identifier)
        index = self._performances.index(old)
        self._performances.remove(old)

        try:
            self.add_performance(performance)
        except FestivalError:
            self._performances.insert(index, old)
            raise

        return performance

    def register_participant(self, identifier: str, name: str) -> Performance:
        performance = self.get_performance(identifier)
        performance.register(name)
        return performance

    # --- Vues pour l'API -------------------------------------------------

    def artist_refs(self, performance: Performance) -> list[dict]:
        """Les artistes sur scène, dans l'ordre d'apparition."""
        return [
            {"slug": artist.slug, "name": artist.name}
            for slug in performance.artist_slugs()
            if (artist := self.find_artist(slug)) is not None
        ]

    def performance_view(self, performance: Performance) -> dict:
        return performance.to_view(self.artist_refs(performance))

    def to_view(self) -> dict:
        return {
            "name": self.name,
            "first_day": self.first_day.isoformat() if self.first_day else None,
            "last_day": self.last_day.isoformat() if self.last_day else None,
            "days": [day.isoformat() for day in self.days],
        }

    def to_data(self) -> dict:
        return {
            "name": self.name,
            "first_day": self.first_day.isoformat() if self.first_day else None,
            "last_day": self.last_day.isoformat() if self.last_day else None,
            "venues": [venue.to_data() for venue in self._venues],
            "artists": [artist.to_data() for artist in self._artists],
            "performances": [p.to_data() for p in self._performances],
        }


def load_festival(storage: Storage) -> Festival:
    """Construit le festival à partir des données du stockage."""
    data = storage.load()

    return Festival(
        venues=[
            Venue(
                name=item["name"],
                capacity=item["capacity"],
                address=item.get("address", ""),
            )
            for item in data["venues"]
        ],
        artists=[
            Artist(
                name=item["name"],
                bio=item.get("bio", ""),
                photo_url=item.get("photo_url", ""),
            )
            for item in data["artists"]
        ],
        performances=[performance_from_data(item) for item in data["performances"]],
        name=data["name"],
        first_day=date.fromisoformat(data["first_day"]),
        last_day=date.fromisoformat(data["last_day"]),
    )


def save_festival(festival: Festival, storage: Storage) -> None:
    """Enregistre le festival dans le stockage."""
    storage.save(festival.to_data())
