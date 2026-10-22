
import sys
import json
from datetime import date, datetime

from models import (
    Festival,
    Performance,
    load_festival,
    save_festival,
)


def show_summary(festival: Festival) -> None:
    print(festival.name)
    print(f"From {festival.first_day} to {festival.last_day}")
    print(
        f"{len(festival.venues)} venues, "
        f"{len(festival.artists)} artists, "
        f"{len(festival.performances)} performances"
    )


def show_venues(festival: Festival) -> None:
    total_seats = 0

    for venue in festival.venues:
        print(f"{venue.slug}: {venue.name}, {venue.capacity} seats")
        total_seats += venue.capacity

    print(f"Total: {total_seats} seats")


def show_programme(festival: Festival, day_text: str) -> None:
    try:
        day = date.fromisoformat(day_text)
    except ValueError:
        print(f"Invalid date '{day_text}'. Use YYYY-MM-DD.")
        return

    performances = festival.programme_for_day(day)

    if not performances:
        days = ", ".join(d.isoformat() for d in festival.days)
        print(f"No performance on '{day_text}'. Days: {days}")
        return

    print(f"Programme for {day:%A %d %B}:")
    for performance in performances:
        print(performance)


def show_artist(festival: Festival, slug: str) -> None:
    artist = festival.find_artist(slug)

    if artist is None:
        print(f"No artist '{slug}'.")
        return

    print(artist.name)

    for performance in festival.performances_for_artist(slug):
        role = performance.role_of(slug)

        if role is None:
            continue

        print(
            f"{performance.festival_day:%a %d} "
            f"{performance.start:%H:%M}-{performance.end:%H:%M} | "
            f"{performance._venue_name} | "
            f"{performance.title} ({role})"
        )


def show_now(festival: Festival, moment_text: str) -> None:
    try:
        moment = datetime.fromisoformat(moment_text)
    except ValueError:
        print("Invalid moment. Use YYYY-MM-DDTHH:MM.")
        return

    print(f"On stage at {moment:%Y-%m-%d %H:%M}:")

    ongoing = festival.now_playing(moment)
    if ongoing:
        for performance in ongoing:
            print(
                f"- {performance.title} at {performance._venue_name}, "
                f"until {performance.end:%H:%M}"
            )
    else:
        print("- Nothing is on stage.")

    print("Up next:")
    for performance in festival.up_next(moment, limit=3):
        print(performance)


def show_stats(festival: Festival) -> None:
    kinds = {}

    for performance in festival.performances:
        kinds[performance.kind] = kinds.get(performance.kind, 0) + 1

    print("Performances by kind:")
    for kind, count in kinds.items():
        print(f"{kind}: {count}")

    print("\nAt Le Kiosque:")
    for performance in festival.performances_for_venue("le-kiosque"):
        print(
            f"- {performance.start.isoformat(timespec='minutes')} "
            f"{performance.venue}"
        )

    if festival.performances:
        longest = max(
            festival.performances,
            key=lambda p: p.duration_minutes,
        )
        print(
            f"\nLongest: {longest.title} "
            f"({longest.duration_minutes}min)"
        )

    for performance in festival.performances:
        if performance.kind == "workshop":
            registered = len(performance.participants)
            capacity = performance.max_participants
            print(
                f"{performance.title} on {performance.festival_day}: "
                f"{registered}/{capacity} registered"
            )

    artists_count = {}
    for performance in festival.performances:
        if performance.kind == "solo" and performance.artist:
            slug = performance.artist
            artists_count[slug] = artists_count.get(slug, 0) + 1
        elif performance.kind == "lineup":
            for slug in performance.acts:
                artists_count[slug] = artists_count.get(slug, 0) + 1

    frequent = [
        slug for slug, count in artists_count.items() if count >= 4
    ]
    print(f"\nOn stage 4 times: {', '.join(frequent)}")


def add_performance(festival: Festival) -> None:
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

    identifier = f"{venue}-{start:%Y-%m-%d-%H%M}"

    performance = Performance(
        identifier=identifier,
        kind="solo",
        title=title,
        venue=venue,
        start=start,
        duration_minutes=duration,
        artist=artist,
    )

    festival.add_performance(performance)
    save_festival(festival)
    print(f"Added: {performance.id}")


def cancel_performance(festival: Festival, identifier: str) -> None:
    performance = festival.cancel_performance(identifier)
    save_festival(festival)
    print(f"Cancelled: {performance.title}")


def main() -> None:
    args = sys.argv[1:]

    try:
        festival = load_festival()

        if not args:
            show_summary(festival)
        elif args == ["venues"]:
            show_venues(festival)
        elif len(args) == 2 and args[0] == "programme":
            show_programme(festival, args[1])
        elif len(args) == 2 and args[0] == "artist":
            show_artist(festival, args[1])
        elif len(args) == 2 and args[0] == "now":
            show_now(festival, args[1])
        elif args == ["stats"]:
            show_stats(festival)
        elif args == ["add"]:
            add_performance(festival)
        elif len(args) == 2 and args[0] == "cancel":
            cancel_performance(festival, args[1])
        else:
            print("Usage:")
            print("  uv run main.py")
            print("  uv run main.py venues")
            print("  uv run main.py programme YYYY-MM-DD")
            print("  uv run main.py artist ARTIST-SLUG")
            print("  uv run main.py now YYYY-MM-DDTHH:MM")
            print("  uv run main.py add")
            print("  uv run main.py cancel PERFORMANCE-ID")
            print("  uv run main.py stats")

    except json.JSONDecodeError:
        print("Error: the festival JSON file is damaged.")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: data/festival.json was not found.")
        sys.exit(1)
    except ValueError as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
