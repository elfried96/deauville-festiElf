"""L'API JSON du festival (voir API.md), plus le site et l'admin."""

from datetime import date, datetime

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .errors import (
    FestivalConflictError,
    FestivalError,
    FestivalNotFoundError,
    FestivalValidationError,
)
from .festival import Festival, load_festival, save_festival
from .models import Artist, Performance, performance_from_data
from .storage import PROJECT_ROOT, JSONStorage, Storage

WEB_DIR = PROJECT_ROOT / "web"

# Le type de chaque erreur du festival donne le code HTTP.
STATUS_CODES = {
    FestivalNotFoundError: 404,
    FestivalConflictError: 409,
    FestivalValidationError: 422,
}


class ArtistBody(BaseModel):
    """Le corps de POST /api/artists."""

    name: str
    bio: str = ""
    photo_url: str = ""


class PerformanceBody(BaseModel):
    """Les champs enregistrés d'une performance ; ceux d'un autre type
    restent vides."""

    kind: str
    title: str
    venue: str
    start: datetime
    duration_minutes: int
    description: str = ""
    artist: str | None = None
    min_age: int | None = None
    host: str | None = None
    acts: list[str] | None = None
    teacher: str | None = None
    max_participants: int | None = None
    participants: list[str] | None = None


class ParticipantBody(BaseModel):
    """Le corps de POST /api/performances/{id}/participants."""

    name: str


def create_app(storage: Storage) -> FastAPI:
    """Construit l'application ; elle lit et écrit dans `storage`."""
    app = FastAPI(title="Deauville Festival du Rire API")

    @app.exception_handler(FestivalError)
    async def festival_error_handler(
        request: Request,
        exc: FestivalError,
    ) -> JSONResponse:
        status_code = STATUS_CODES.get(type(exc), 500)
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    def open_festival() -> Festival:
        return load_festival(storage)

    def performance_from_body(body: PerformanceBody) -> Performance:
        return performance_from_data(body.model_dump(mode="json", exclude_none=True))

    # --- Lecture ---------------------------------------------------------

    @app.get("/api/festival")
    def get_festival() -> dict:
        return open_festival().to_view()

    @app.get("/api/venues")
    def list_venues() -> list[dict]:
        return [venue.to_view() for venue in open_festival().venues]

    @app.get("/api/artists")
    def list_artists() -> list[dict]:
        artists = sorted(open_festival().artists, key=lambda artist: artist.slug)
        return [artist.to_view() for artist in artists]

    @app.get("/api/artists/{slug}")
    def get_artist(slug: str) -> dict:
        festival = open_festival()
        view = festival.get_artist(slug).to_view()
        view["performances"] = [
            festival.performance_view(p) for p in festival.performances_for_artist(slug)
        ]
        return view

    @app.get("/api/programme")
    def get_programme(day: date | None = None, venue: str | None = None) -> list[dict]:
        festival = open_festival()
        return [
            festival.performance_view(p)
            for p in festival.programme(day=day, venue=venue)
        ]

    @app.get("/api/performances/{identifier}")
    def get_performance(identifier: str) -> dict:
        festival = open_festival()
        return festival.performance_view(festival.get_performance(identifier))

    @app.get("/api/now")
    def get_now(at: datetime | None = None) -> dict:
        festival = open_festival()
        moment = at if at is not None else datetime.now().replace(second=0)

        return {
            "at": moment.isoformat(timespec="minutes"),
            "now_playing": [
                festival.performance_view(p) for p in festival.now_playing(moment)
            ],
            "up_next": [
                festival.performance_view(p) for p in festival.up_next(moment, limit=3)
            ],
        }

    # --- Écriture (admin) : chaque changement est enregistré aussitôt ----

    @app.post("/api/artists", status_code=201)
    def create_artist(body: ArtistBody) -> dict:
        festival = open_festival()
        artist = Artist(name=body.name, bio=body.bio, photo_url=body.photo_url)
        festival.add_artist(artist)
        save_festival(festival, storage)
        return artist.to_view()

    @app.post("/api/performances", status_code=201)
    def create_performance(body: PerformanceBody) -> dict:
        festival = open_festival()
        performance = performance_from_body(body)
        festival.add_performance(performance)
        save_festival(festival, storage)
        return festival.performance_view(performance)

    @app.put("/api/performances/{identifier}")
    def update_performance(identifier: str, body: PerformanceBody) -> dict:
        festival = open_festival()
        performance = festival.replace_performance(
            identifier, performance_from_body(body)
        )
        save_festival(festival, storage)
        return festival.performance_view(performance)

    @app.delete("/api/performances/{identifier}", status_code=204)
    def delete_performance(identifier: str) -> Response:
        festival = open_festival()
        festival.cancel_performance(identifier)
        save_festival(festival, storage)
        return Response(status_code=204)

    @app.post("/api/performances/{identifier}/participants", status_code=201)
    def register_participant(identifier: str, body: ParticipantBody) -> dict:
        festival = open_festival()
        workshop = festival.register_participant(identifier, body.name)
        save_festival(festival, storage)
        return festival.performance_view(workshop)

    # --- Le site et l'admin (l'admin avant "/", qui attrape tout) --------

    app.mount(
        "/admin",
        StaticFiles(directory=WEB_DIR / "admin", html=True),
        name="admin",
    )
    app.mount(
        "/",
        StaticFiles(directory=WEB_DIR / "public", html=True),
        name="website",
    )

    return app


# L'application par défaut, sur data/festival.json
# (pour `uv run uvicorn deauville.api:app --reload`).
app = create_app(JSONStorage())
