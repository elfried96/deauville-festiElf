
import json
from pathlib import Path
import sys
import unicodedata
from datetime import date, datetime, timedelta

DATA_FILE = Path(__file__).parent / "data" / "festival.json"


def load_data():
    """Charge les données du festival depuis le fichier JSON."""
    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


# ==================================================
# 1. FONCTIONS UTILITAIRES
# ==================================================

def slugify(text: str) -> str:
    """Transforme un nom en slug sans accents."""
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


def start_of(performance: dict) -> datetime:
    """Retourne la date et l'heure de début."""
    return datetime.fromisoformat(performance["start"])


def end_of(performance: dict) -> datetime:
    """Calcule la date et l'heure de fin."""
    return start_of(performance) + timedelta(
        minutes=performance["duration_minutes"]
    )


def festival_day(performance: dict) -> date:
    """Une journée du festival commence à 06:00."""
    return (start_of(performance) - timedelta(hours=6)).date()


def find_venue(playlist: dict, slug: str):
    """Recherche un lieu par son slug."""
    for venue in playlist["venues"]:
        venue_slug = venue.get("slug") or slugify(venue["name"])

        if venue_slug == slug:
            return venue

    return None


def find_artist(playlist: dict, slug: str):
    """Recherche un artiste par son slug."""
    for artist in playlist["artists"]:
        if isinstance(artist, dict):
            artist_slug = artist.get("slug")

            if artist_slug is None and "name" in artist:
                artist_slug = slugify(artist["name"])

            if artist_slug == slug:
                return artist

        elif artist == slug:
            return artist

    return None


def artist_name(artist) -> str:
    """Retourne le nom lisible d'un artiste."""
    if isinstance(artist, dict):
        return artist.get("name", artist.get("slug", "Unknown artist"))

    return artist


def venue_name(playlist: dict, slug: str) -> str:
    """Retourne le nom d'un lieu."""
    venue = find_venue(playlist, slug)

    if venue is None:
        return slug

    return venue["name"]


# ==================================================
# 2. COMMANDES D'AFFICHAGE
# ==================================================

def show_summary(playlist: dict) -> None:
    """Résumé du festival."""
    print(playlist["name"])
    print(f"From {playlist['first_day']} to {playlist['last_day']}")
    print(
        f"{len(playlist['venues'])} venues, "
        f"{len(playlist['artists'])} artists, "
        f"{len(playlist['performances'])} performances"
    )


def show_venues(playlist: dict) -> None:
    """Affiche les lieux et leurs capacités."""
    total_seats = 0

    for venue in playlist["venues"]:
        slug = slugify(venue["name"])
        capacity = venue["capacity"]

        print(f"{slug}: {venue['name']}, {capacity} seats")
        total_seats += capacity

    print(f"Total: {total_seats} seats")


def show_programme(playlist: dict, day_text: str) -> None:
    """Affiche les représentations d'une journée du festival."""
    try:
        day = date.fromisoformat(day_text)
    except ValueError:
        print(f"Invalid date '{day_text}'. Use YYYY-MM-DD.")
        return

    performances = [
        performance
        for performance in playlist["performances"]
        if festival_day(performance) == day
    ]

    if not performances:
        days = sorted({
            festival_day(performance).isoformat()
            for performance in playlist["performances"]
        })
        print(f"No performance on '{day_text}'. Days: {', '.join(days)}")
        return

    print(f"Programme for {day:%A %d %B}:")

    for performance in sorted(performances, key=start_of):
        start = start_of(performance)
        end = end_of(performance)
        place = venue_name(playlist, performance["venue"])

        print(
            f"{start:%H:%M}-{end:%H:%M} | {place} | "
            f"{performance['title']} ({performance['kind']})"
        )


def show_artist(playlist: dict, slug: str) -> None:
    """Affiche les performances et le rôle d'un artiste."""
    artist = find_artist(playlist, slug)

    if artist is None:
        print(f"No artist '{slug}'.")
        return

    print(artist_name(artist))

    for performance in sorted(
        playlist["performances"],
        key=start_of
    ):
        role = None

        if (
            performance["kind"] == "solo"
            and performance.get("artist") == slug
        ):
            role = "solo"

        elif (
            performance["kind"] == "lineup"
            and performance.get("host") == slug
        ):
            role = "host"

        elif (
            performance["kind"] == "lineup"
            and slug in performance.get("acts", [])
        ):
            role = "act"

        elif (
            performance["kind"] == "workshop"
            and performance.get("teacher") == slug
        ):
            role = "teacher"

        if role is not None:
            start = start_of(performance)
            end = end_of(performance)
            day = festival_day(performance)
            place = venue_name(playlist, performance["venue"])

            print(
                f"{day:%a %d} {start:%H:%M}-{end:%H:%M} | "
                f"{place} | {performance['title']} ({role})"
            )


def show_now(playlist: dict, moment_text: str) -> None:
    """Affiche les représentations en cours et les trois suivantes."""
    try:
        moment = datetime.fromisoformat(moment_text)
    except ValueError:
        print("Invalid moment. Use YYYY-MM-DDTHH:MM.")
        return

    performances = sorted(
        playlist["performances"],
        key=start_of
    )

    ongoing = [
        performance
        for performance in performances
        if start_of(performance) <= moment < end_of(performance)
    ]

    upcoming = [
        performance
        for performance in performances
        if start_of(performance) > moment
    ]

    print(f"On stage at {moment:%Y-%m-%d %H:%M}:")

    if ongoing:
        for performance in ongoing:
            place = venue_name(playlist, performance["venue"])
            print(
                f"- {performance['title']} at {place}, "
                f"until {end_of(performance):%H:%M}"
            )
    else:
        print("- Nothing is on stage.")

    print("Up next:")

    for performance in upcoming[:3]:
        start = start_of(performance)
        end = end_of(performance)
        place = venue_name(playlist, performance["venue"])

        print(
            f"- {start:%H:%M}-{end:%H:%M} | {place} | "
            f"{performance['title']} ({performance['kind']})"
        )


# ==================================================
# 3. STATISTIQUES DES ÉTAPES PRÉCÉDENTES
# ==================================================

def show_stats(playlist: dict) -> None:
    """Conserve les statistiques précédentes."""

    kinds = {}

    for performance in playlist["performances"]:
        kind = performance["kind"]
        kinds[kind] = kinds.get(kind, 0) + 1

    print("Performances by kind:")

    for kind, count in kinds.items():
        print(f"{kind}: {count}")

    print("\nAt Le Kiosque:")

    for performance in playlist["performances"]:
        if performance["venue"] == "le-kiosque":
            print(f"- {performance['start']} {performance['venue']}")

    longest = max(
        playlist["performances"],
        key=lambda performance: performance["duration_minutes"]
    )

    print(
        f"\nLongest: {longest['title']} "
        f"({longest['duration_minutes']}min)"
    )

    for performance in playlist["performances"]:
        if performance["kind"] == "workshop":
            day = festival_day(performance)
            registered = len(performance["participants"])
            capacity = performance["max_participants"]

            print(
                f"{performance['title']} on {day}: "
                f"{registered}/{capacity} registered"
            )

    artists_count = {}

    for performance in playlist["performances"]:
        if performance["kind"] == "solo":
            artist = performance["artist"]
            artists_count[artist] = artists_count.get(artist, 0) + 1

        elif performance["kind"] == "lineup":
            for artist in performance["acts"]:
                artists_count[artist] = artists_count.get(artist, 0) + 1

    artists = [
        artist
        for artist, count in artists_count.items()
        if count >= 4
    ]

    print(f"\nOn stage 4 times: {', '.join(artists)}")



def save_data(playlist: dict) -> None:
    """Enregistre les données du festival dans le fichier JSON."""
    with open("data/festival.json", "w", encoding="utf-8") as file:
        json.dump(playlist, file, ensure_ascii=False, indent=2)


def artists_in(performance: dict) -> list[str]:
    """Retourne tous les artistes impliqués dans une performance."""
    kind = performance["kind"]

    if kind == "solo":
        return [performance["artist"]]

    if kind == "lineup":
        return (
            [performance["host"]]
            + performance.get("acts", [])
        )

    if kind == "workshop":
        return [performance["teacher"]]

    return []


def performance_id(performance: dict) -> str:
    """Construit l'identifiant d'une performance."""
    start = start_of(performance)
    return (
        f"{performance['venue']}-"
        f"{start:%Y-%m-%d-%H%M}"
    )


def validate_performance(
    playlist: dict,
    performance: dict
) -> None:
    """Vérifie les règles avant l'ajout d'une performance."""

    venue = find_venue(playlist, performance["venue"])

    if venue is None:
        raise ValueError(
            f"Unknown venue '{performance['venue']}'."
        )

    artist_slugs = {
        slugify(artist["name"]) if isinstance(artist, dict)
        and "name" in artist else
        artist.get("slug") if isinstance(artist, dict)
        else slugify(artist)
        for artist in playlist["artists"]
    }

    for artist in artists_in(performance):
        if artist not in artist_slugs:
            raise ValueError(f"Unknown artist '{artist}'.")

    duration = performance["duration_minutes"]

    if not 1 <= duration <= 360:
        raise ValueError("Duration must be between 1 and 360 minutes.")

    start = start_of(performance)
    end = end_of(performance)
    day = festival_day(performance)

    first_day = date.fromisoformat(playlist["first_day"])
    last_day = date.fromisoformat(playlist["last_day"])

    if not first_day <= day <= last_day:
        raise ValueError(
            f"{day} is not a day of the festival."
        )

    gap = timedelta(minutes=30)

    for existing in playlist["performances"]:
        existing_start = start_of(existing)
        existing_end = end_of(existing)

        # Deux représentations ne peuvent pas occuper
        # le même lieu avec moins de 30 minutes d'intervalle.
        if existing["venue"] == performance["venue"]:
            if (
                start < existing_end + gap
                and existing_start < end + gap
            ):
                name = venue["name"]
                raise ValueError(
                    f"{name} is busy with {existing['title']} "
                    f"({existing_start:%Y-%m-%d %H:%M}-"
                    f"{existing_end:%H:%M})."
                )

        # Vérifier les conflits pour chaque artiste,
        # quel que soit son rôle dans la représentation.
        existing_artists = artists_in(existing)

        for artist in artists_in(performance):
            if artist in existing_artists:
                if (
                    start < existing_end + gap
                    and existing_start < end + gap
                ):
                    raise ValueError(
                        f"{artist.replace('-', ' ').title()} "
                        f"is on stage in {existing['title']}."
                    )


def add_performance(playlist: dict) -> None:
    """Demande les informations, valide et ajoute un solo."""

    title = input("Title: ").strip()
    artist = input("Artist (slug): ").strip()
    venue = input("Venue (slug): ").strip()
    start_text = input("Start (YYYY-MM-DDTHH:MM): ").strip()

    duration_text = input("Duration (minutes): ").strip()

    try:
        duration = int(duration_text)
    except ValueError:
        raise ValueError(
            f"'{duration_text}' is not a number of minutes."
        ) from None

    try:
        start = datetime.fromisoformat(start_text)
    except ValueError:
        raise ValueError(
            f"'{start_text}' is not a valid date and time."
        ) from None

    performance = {
        "kind": "solo",
        "title": title,
        "artist": artist,
        "venue": venue,
        "start": start.isoformat(timespec="minutes"),
        "duration_minutes": duration,
    }

    validate_performance(playlist, performance)

    playlist["performances"].append(performance)
    save_data(playlist)

    print(f"Added: {performance_id(performance)}")


def cancel_performance(playlist: dict, identifier: str) -> None:
    """Annule une performance à partir de son identifiant."""

    for performance in playlist["performances"]:
        if performance_id(performance) == identifier:
            playlist["performances"].remove(performance)
            save_data(playlist)
            print(f"Cancelled: {performance['title']}")
            return

    raise ValueError(f"No performance '{identifier}'.")

