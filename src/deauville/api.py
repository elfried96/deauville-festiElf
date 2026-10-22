
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    Artist,
    FestivalConflictError,
    FestivalError,
    FestivalNotFoundError,
    FestivalStorageError,
    FestivalValidationError,
    Performance,
    load_festival,
    save_festival,
    slugify,
    Lineup,
    SoloShow,
    Workshop,
)


from .storage import JSONStorage

app = FastAPI(title="Deauville Festival du Rire API")

@app.exception_handler(FestivalError)
async def festival_exception_handler(
    request: Request,
    exc: FestivalError,
) -> JSONResponse:
    if isinstance(exc, FestivalNotFoundError):
        status_code = 404
    elif isinstance(exc, FestivalConflictError):
        status_code = 409
    elif isinstance(exc, FestivalValidationError):
        status_code = 422
    elif isinstance(exc, FestivalStorageError):
        status_code = 500
    else:
        status_code = 500

    return JSONResponse(
        status_code=status_code,
        content={"detail": str(exc)},
    )


@app.get("/api/festival")
def get_festival() -> dict:
    data = JSONStorage(Path(__file__).resolve().parents[2] / "data" / "festival.json").load()

    first_day = date.fromisoformat(data["first_day"])
    last_day = date.fromisoformat(data["last_day"])

    days = []
    current_day = first_day

    while current_day <= last_day:
        days.append(current_day.isoformat())
        current_day += timedelta(days=1)

    return {
        "name": data["name"],
        "first_day": data["first_day"],
        "last_day": data["last_day"],
        "days": days,
    }



@app.get("/api/venues")
def list_venues() -> list[dict]:
    festival = load_festival(storage=storage)

    return [
        {
            "slug": venue.slug,
            "name": venue.name,
            "capacity": venue.capacity,
            "address": venue.address,
        }
        for venue in festival.venues
    ]



@app.get("/api/artists")
def list_artists() -> list[dict]:
    festival = load_festival(storage=storage)

    artists = [
        {
            "slug": artist.slug,
            "name": artist.name,
        }
        for artist in festival.artists
    ]

    return sorted(artists, key=lambda artist: artist["slug"])


@app.post("/api/artists", status_code=201)
def create_artist(payload: dict) -> dict:
    festival = load_festival(storage=storage)

    name = payload.get("name")

    if not isinstance(name, str) or not name.strip():
        raise FestivalValidationError(
            "Artist name must not be empty."
        )

    name = name.strip()
    new_slug = slugify(name)

    if any(artist.slug == new_slug for artist in festival.artists):
        raise FestivalConflictError(
            f"An artist named '{name}' already exists."
        )

    artist = Artist(
        name=name,
        bio=payload.get("bio", ""),
        photo_url=payload.get("photo_url", ""),
    )

    festival.artists.append(artist)
    save_festival(festival, storage=storage)

    return {
        "slug": artist.slug,
        "name": artist.name,
        "bio": artist.bio,
        "photo_url": artist.photo_url,
    }


@app.post("/api/performances", status_code=201)
def create_performance(payload: dict) -> dict:
    festival = load_festival(storage=storage)

    # VÃ©rifier les champs communs.
    required_fields = [
        "kind",
        "title",
        "venue",
        "start",
        "duration_minutes",
    ]

    for field in required_fields:
        if field not in payload:
            raise FestivalValidationError(
                f"Missing required field: {field}."
            )

    kind = payload["kind"]
    title = payload["title"]
    venue = payload["venue"]

    if not isinstance(title, str) or not title.strip():
        raise FestivalValidationError(
            "Performance title must not be empty."
        )

    if not isinstance(venue, str) or not venue.strip():
        raise FestivalValidationError(
            "Venue must not be empty."
        )

    try:
        start = datetime.fromisoformat(payload["start"])
    except (TypeError, ValueError):
        raise FestivalValidationError(
            "Start must be a valid date and time."
        )

    duration = payload["duration_minutes"]

    if isinstance(duration, bool) or not isinstance(duration, int):
        raise FestivalValidationError(
            "Duration must be an integer."
        )

    identifier = (
        f"{venue}-{start:%Y-%m-%d-%H%M}"
    )

    common = {
        "identifier": identifier,
        "title": title.strip(),
        "venue": venue,
        "start": start,
        "duration_minutes": duration,
        "description": payload.get("description", ""),
    }

    # Construire l'objet selon son type.
    if kind == "solo":
        if "artist" not in payload:
            raise FestivalValidationError(
                "A solo show requires an artist."
            )

        performance = SoloShow(
            **common,
            artist=payload["artist"],
            min_age=payload.get("min_age"),
        )

    elif kind == "lineup":
        if "host" not in payload or "acts" not in payload:
            raise FestivalValidationError(
                "A lineup requires a host and acts."
            )

        performance = Lineup(
            **common,
            host=payload["host"],
            acts=payload["acts"],
        )

    elif kind == "workshop":
        if (
            "teacher" not in payload
            or "max_participants" not in payload
        ):
            raise FestivalValidationError(
                "A workshop requires a teacher and max_participants."
            )

        performance = Workshop(
            **common,
            teacher=payload["teacher"],
            max_participants=payload["max_participants"],
            participants=payload.get("participants", []),
        )

    else:
        raise FestivalValidationError(
            "Kind must be solo, lineup or workshop."
        )

    # VÃ©rifier les rÃ¨gles mÃ©tier avant de sauvegarder.
    festival.add_performance(performance)

    save_festival(festival, storage=storage)

    # Retourner la reprÃ©sentation dans le format de l'API.
    venue_object = festival.find_venue(performance.venue)

    artists = []
    for slug in sorted(performance.artist_slugs()):
        artist = festival.find_artist(slug)
        if artist is not None:
            artists.append({
                "slug": artist.slug,
                "name": artist.name,
            })

    return performance.to_view(
        venue_name=venue_object.name,
        artists=artists,
    )
##########

@app.put("/api/performances/{performance_id}")
def update_performance(performance_id: str, payload: dict) -> dict:
    festival = load_festival(storage=storage)

    # 1. VÃ©rifier que le spectacle existe.
    old_performance = festival.find_performance(performance_id)

    # 2. VÃ©rifier les champs obligatoires.
    required_fields = [
        "kind",
        "title",
        "venue",
        "start",
        "duration_minutes",
    ]

    for field in required_fields:
        if field not in payload:
            raise FestivalValidationError(
                f"Missing required field: {field}."
            )

    kind = payload["kind"]
    title = payload["title"]
    venue = payload["venue"]

    if not isinstance(title, str) or not title.strip():
        raise FestivalValidationError(
            "Performance title must not be empty."
        )

    if not isinstance(venue, str) or not venue.strip():
        raise FestivalValidationError("Venue must not be empty.")

    try:
        start = datetime.fromisoformat(payload["start"])
    except (TypeError, ValueError):
        raise FestivalValidationError(
            "Start must be a valid date and time."
        )

    duration = payload["duration_minutes"]

    if isinstance(duration, bool) or not isinstance(duration, int):
        raise FestivalValidationError("Duration must be an integer.")

    # 3. Construire la nouvelle version du spectacle.
    identifier = f"{venue.strip()}-{start:%Y-%m-%d-%H%M}"

    common = {
        "identifier": identifier,
        "title": title.strip(),
        "venue": venue.strip(),
        "start": start,
        "duration_minutes": duration,
        "description": payload.get("description", ""),
    }

    if kind == "solo":
        if "artist" not in payload:
            raise FestivalValidationError(
                "A solo show requires an artist."
            )

        performance = SoloShow(
            **common,
            artist=payload["artist"],
            min_age=payload.get("min_age"),
        )

    elif kind == "lineup":
        if "host" not in payload or "acts" not in payload:
            raise FestivalValidationError(
                "A lineup requires a host and acts."
            )

        performance = Lineup(
            **common,
            host=payload["host"],
            acts=payload["acts"],
        )

    elif kind == "workshop":
        if (
            "teacher" not in payload
            or "max_participants" not in payload
        ):
            raise FestivalValidationError(
                "A workshop requires a teacher and max_participants."
            )

        performance = Workshop(
            **common,
            teacher=payload["teacher"],
            max_participants=payload["max_participants"],
            participants=payload.get("participants", []),
        )

    else:
        raise FestivalValidationError(
            "Kind must be solo, lineup or workshop."
        )

    
    # 4. Retirer temporairement l'ancien spectacle.
    festival.cancel_performance(performance_id)

    try:
        festival.add_performance(performance)
    except Exception:
        # Restaurer l'ancien spectacle en mÃ©moire sans le revalider.
        festival._performances.append(old_performance)
        raise

    # 5. Enregistrer uniquement aprÃ¨s validation.
    save_festival(festival, storage=storage)


    venue_object = festival.find_venue(performance.venue)

    artists = []
    for slug in sorted(performance.artist_slugs()):
        artist = festival.find_artist(slug)
        if artist is not None:
            artists.append({
                "slug": artist.slug,
                "name": artist.name,
            })

    return performance.to_view(
        venue_name=venue_object.name,
        artists=artists,
    )


@app.get("/api/programme")
def get_programme(
    day: date | None = None,
    venue: str | None = None,
) -> list[dict]:
    festival = load_festival(storage=storage)

    # VÃ©rifier que le lieu demandÃ© existe.
    if venue is not None and festival.find_venue(venue) is None:
        raise HTTPException(
            status_code=404,
            detail=f"No venue '{venue}'.",
        )

    performances = festival.performances

    # Filtrer par journÃ©e du festival.
    if day is not None:
        performances = [
            performance
            for performance in performances
            if performance.festival_day == day
        ]

    # Filtrer par lieu.
    if venue is not None:
        performances = [
            performance
            for performance in performances
            if performance.venue == venue
        ]

    # PrÃ©parer les donnÃ©es pour l'API.
    result = []

    for performance in performances:
        venue_object = festival.find_venue(performance.venue)

        if venue_object is None:
            continue

        
        artist_slugs = []

        artist = getattr(performance, "artist", None)
        if artist is not None:
            artist_slugs.append(artist)

        host = getattr(performance, "host", None)
        if host is not None:
            artist_slugs.append(host)

        teacher = getattr(performance, "teacher", None)
        if teacher is not None:
            artist_slugs.append(teacher)

        acts = getattr(performance, "acts", [])
        artist_slugs.extend(acts)


        artists = []

        for slug in artist_slugs:
            artist_object = festival.find_artist(slug)

            if artist_object is not None:
                artists.append({
                    "slug": artist_object.slug,
                    "name": artist_object.name,
                })

        result.append(
            performance.to_view(
                venue_name=venue_object.name,
                artists=artists,
            )
        )

    return sorted(result, key=lambda item: item["start"])


@app.get("/api/performances/{id}")
def get_performance(id: str) -> dict:
    festival = load_festival(storage=storage)

    performance = festival.find_performance(id)

    if performance is None:
        raise HTTPException(
            status_code=404,
            detail=f"No performance '{id}'.",
        )

    venue_object = festival.find_venue(performance.venue)

    if venue_object is None:
        raise HTTPException(
            status_code=404,
            detail=f"No venue '{performance.venue}'.",
        )

    artist_slugs = []

    if performance.artist is not None:
        artist_slugs.append(performance.artist)

    if performance.host is not None:
        artist_slugs.append(performance.host)

    if performance.teacher is not None:
        artist_slugs.append(performance.teacher)

    artist_slugs.extend(performance.acts)

    artists = []

    for slug in artist_slugs:
        artist_object = festival.find_artist(slug)

        if artist_object is not None:
            artists.append({
                "slug": artist_object.slug,
                "name": artist_object.name,
            })

    return performance.to_view(
        venue_name=venue_object.name,
        artists=artists,
    )

###################


@app.get("/api/artists/{slug}")
def get_artist(slug: str) -> dict:
    festival = load_festival(storage=storage)

    artist = festival.find_artist(slug)

    if artist is None:
        raise HTTPException(
            status_code=404,
            detail=f"No artist '{slug}'.",
        )

    performances = festival.performances_for_artist(slug)
    performance_views = []

    for performance in performances:
        venue_object = festival.find_venue(performance.venue)

        if venue_object is None:
            continue

        artist_slugs = []

        if performance.artist is not None:
            artist_slugs.append(performance.artist)

        if performance.host is not None:
            artist_slugs.append(performance.host)

        if performance.teacher is not None:
            artist_slugs.append(performance.teacher)

        artist_slugs.extend(performance.acts)

        performance_artists = []

        for artist_slug in artist_slugs:
            related_artist = festival.find_artist(artist_slug)

            if related_artist is not None:
                performance_artists.append({
                    "slug": related_artist.slug,
                    "name": related_artist.name,
                })

        performance_views.append(
            performance.to_view(
                venue_name=venue_object.name,
                artists=performance_artists,
            )
        )

    performance_views.sort(key=lambda item: item["start"])

    return {
        "slug": artist.slug,
        "name": artist.name,
        "bio": artist.bio,
        "photo_url": artist.photo_url,
        "performances": performance_views,
    }


@app.get("/api/now")
def get_now(at: datetime | None = None) -> dict:
    festival = load_festival(storage=storage)
    moment = at if at is not None else datetime.now()

    def serialize_performance(performance: Performance) -> dict:
        venue_object = festival.find_venue(performance.venue)

        if venue_object is None:
            return {}

        artist_slugs = sorted(performance.artist_slugs())

        artists = []

        for slug in artist_slugs:
            artist_object = festival.find_artist(slug)

            if artist_object is not None:
                artists.append({
                    "slug": artist_object.slug,
                    "name": artist_object.name,
                })

        return performance.to_view(
            venue_name=venue_object.name,
            artists=artists,
        )

    now_playing = festival.now_playing(moment)
    up_next = festival.up_next(moment, limit=3)

    return {
        "now_playing": [
            serialize_performance(performance)
            for performance in now_playing
        ],
        "up_next": [
            serialize_performance(performance)
            for performance in up_next
        ],
    }


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parents[2] / "web" / "public", html=True),
    name="website",
)



