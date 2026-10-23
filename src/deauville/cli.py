"""La ligne de commande : `uv run deauville ...`."""

import sys
from datetime import date, datetime

from .errors import FestivalError
from .festival import Festival, load_festival, save_festival
from .models import performance_from_data
from .storage import DEFAULT_DATA_FILE, JSONStorage, Storage

USAGE = """\
Usage:
  uv run deauville
  uv run deauville venues
  uv run deauville programme YYYY-MM-DD
  uv run deauville artist ARTIST-SLUG
  uv run deauville now YYYY-MM-DDTHH:MM
  uv run deauville stats
  uv run deauville add
  uv run deauville cancel PERFORMANCE-ID
  uv run deauville serve [--port PORT]
Every command accepts --data FILE to use another data file."""


def show_summary(festival: Festival) -> None:
    print(festival.name)
    print(f"From {festival.first_day} to {festival.last_day}")
    print(
        f"{len(festival.venues)} venues, "
        f"{len(festival.artists)} artists, "
        f"{len(festival.performances)} performances"
    )


def show_venues(festival: Festival) -> None:
    for venue in festival.venues:
        print(f"{venue.slug}: {venue.name}, {venue.capacity} seats")

    total_seats = sum(venue.capacity for venue in festival.venues)
    print(f"Total: {total_seats} seats")


def show_programme(festival: Festival, day_text: str) -> None:
    try:
        day = date.fromisoformat(day_text)
    except ValueError:
        print(f"Invalid date '{day_text}'. Use YYYY-MM-DD.")
        return

    performances = festival.programme(day=day)

    if not performances:
        days = ", ".join(d.isoformat() for d in festival.days)
        print(f"No performance on '{day_text}'. Days: {days}")
        return

    print(f"Programme for {day:%A %d %B}:")
    for performance in performances:
        print(performance)


def show_artist(festival: Festival, slug: str) -> None:
    artist = festival.get_artist(slug)
    print(artist.name)

    for performance in festival.performances_for_artist(slug):
        print(
            f"{performance.festival_day:%a %d} "
            f"{performance.start:%H:%M}-{performance.end:%H:%M} | "
            f"{performance.venue_name} | "
            f"{performance.title} ({performance.role_of(slug)})"
        )


def show_now(festival: Festival, moment_text: str) -> None:
    try:
        moment = datetime.fromisoformat(moment_text)
    except ValueError:
        print("Invalid moment. Use YYYY-MM-DDTHH:MM.")
        return

    print(f"On stage at {moment:%Y-%m-%d %H:%M}:")

    ongoing = festival.now_playing(moment)
    for performance in ongoing:
        print(
            f"- {performance.title} at {performance.venue_name}, "
            f"until {performance.end:%H:%M}"
        )
    if not ongoing:
        print("- Nothing is on stage.")

    print("Up next:")
    for performance in festival.up_next(moment, limit=3):
        print(performance)


def show_stats(festival: Festival) -> None:
    performances = festival.performances

    kinds: dict[str, int] = {}
    for performance in performances:
        kinds[performance.kind] = kinds.get(performance.kind, 0) + 1

    print("Performances by kind:")
    for kind, count in sorted(kinds.items()):
        print(f"{kind}: {count}")

    print("\nAt Le Kiosque:")
    for performance in festival.performances_for_venue("le-kiosque"):
        print(
            f"- {performance.start.isoformat(timespec='minutes')} {performance.title}"
        )

    if performances:
        longest = max(performances, key=lambda p: p.duration_minutes)
        print(f"\nLongest: {longest.title} ({longest.duration_minutes} min)")

    print()
    for workshop in festival.workshops():
        print(
            f"{workshop.title} on {workshop.festival_day}: "
            f"{len(workshop.participants)}/{workshop.places} registered"
        )

    # Chaque artiste compte une fois par performance, quel que soit son rôle.
    appearances: dict[str, int] = {}
    for performance in performances:
        for slug in performance.artist_slugs():
            appearances[slug] = appearances.get(slug, 0) + 1

    frequent = [slug for slug, count in appearances.items() if count >= 4]
    print(f"\nOn stage 4 times: {', '.join(frequent)}")


def add_performance(festival: Festival, storage: Storage) -> None:
    title = input("Title: ").strip()
    artist = input("Artist (slug): ").strip()
    venue = input("Venue (slug): ").strip()
    start_text = input("Start (YYYY-MM-DDTHH:MM): ").strip()
    duration_text = input("Duration (minutes): ").strip()

    try:
        duration = int(duration_text)
    except ValueError:
        print(f"Error: '{duration_text}' is not a number of minutes.")
        sys.exit(1)

    performance = performance_from_data(
        {
            "kind": "solo",
            "title": title,
            "artist": artist,
            "venue": venue,
            "start": start_text,
            "duration_minutes": duration,
        }
    )

    festival.add_performance(performance)
    save_festival(festival, storage)
    print(f"Added: {performance.id}")


def cancel_performance(festival: Festival, storage: Storage, identifier: str) -> None:
    performance = festival.cancel_performance(identifier)
    save_festival(festival, storage)
    print(f"Cancelled: {performance.title}")


def serve(storage: Storage, port: int = 8000) -> None:
    import uvicorn

    from .api import create_app

    print(f"Website: http://127.0.0.1:{port}/  Admin: http://127.0.0.1:{port}/admin/")
    uvicorn.run(create_app(storage), host="127.0.0.1", port=port)


def take_option(args: list[str], name: str) -> str | None:
    """Retire `name VALUE` de `args` et renvoie VALUE (None si absent)."""
    if name not in args:
        return None

    index = args.index(name)
    if index + 1 >= len(args):
        print(f"Error: the option {name} needs a value.")
        sys.exit(2)

    value = args[index + 1]
    del args[index : index + 2]
    return value


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)

    data_file = take_option(args, "--data")
    port_text = take_option(args, "--port") or "8000"
    if not port_text.isdigit():
        print(f"Error: '{port_text}' is not a port number.")
        sys.exit(2)
    storage = JSONStorage(data_file or DEFAULT_DATA_FILE)

    try:
        if args == ["serve"]:
            serve(storage, int(port_text))
            return

        festival = load_festival(storage)

        match args:
            case []:
                show_summary(festival)
            case ["venues"]:
                show_venues(festival)
            case ["programme", day]:
                show_programme(festival, day)
            case ["artist", slug]:
                show_artist(festival, slug)
            case ["now", moment]:
                show_now(festival, moment)
            case ["stats"]:
                show_stats(festival)
            case ["add"]:
                add_performance(festival, storage)
            case ["cancel", identifier]:
                cancel_performance(festival, storage, identifier)
            case _:
                print(USAGE)
                sys.exit(2)

    except FestivalError as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
