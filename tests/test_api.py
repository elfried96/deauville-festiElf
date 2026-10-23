"""L'API de bout en bout, sur un stockage en mémoire : le fichier n'est
jamais touché."""

import pytest
from fastapi.testclient import TestClient

from deauville.api import create_app
from deauville.cli import main
from deauville.errors import FestivalStorageError
from deauville.storage import JSONStorage, MemoryStorage

DATA = {
    "name": "Festival de test",
    "first_day": "2027-06-10",
    "last_day": "2027-06-13",
    "venues": [
        {"name": "Grand Casino", "capacity": 650, "address": "Seafront"},
        {"name": "Le Kiosque", "capacity": 120, "address": "Beach"},
    ],
    "artists": [
        {"name": "Nora Lebrun"},
        {"name": "Maya Choukri"},
        {"name": "Tom Vasseur"},
        {"name": "Max Pellerin"},
    ],
    "performances": [
        {
            "kind": "solo",
            "title": "Maya Live",
            "venue": "le-kiosque",
            "start": "2027-06-13T15:00",
            "duration_minutes": 60,
            "artist": "maya-choukri",
        },
        {
            "kind": "workshop",
            "title": "Stand-up Lab",
            "venue": "grand-casino",
            "start": "2027-06-12T10:30",
            "duration_minutes": 120,
            "teacher": "tom-vasseur",
            "max_participants": 2,
        },
    ],
}

NORA = {
    "kind": "solo",
    "title": "Nora seule",
    "venue": "le-kiosque",
    "start": "2027-06-13T11:00",
    "duration_minutes": 45,
    "artist": "nora-lebrun",
}


@pytest.fixture
def storage():
    return MemoryStorage(DATA)


@pytest.fixture
def client(storage):
    return TestClient(create_app(storage))


def test_read_routes(client):
    assert client.get("/api/festival").json()["days"][0] == "2027-06-10"
    assert [v["slug"] for v in client.get("/api/venues").json()] == [
        "grand-casino",
        "le-kiosque",
    ]
    assert client.get("/api/artists").json()[0]["slug"] == "max-pellerin"

    programme = client.get("/api/programme", params={"day": "2027-06-13"}).json()
    assert [p["title"] for p in programme] == ["Maya Live"]
    assert programme[0]["summary"] == "Maya Choukri"
    assert programme[0]["capacity"] == 120

    artist = client.get("/api/artists/maya-choukri").json()
    assert [p["title"] for p in artist["performances"]] == ["Maya Live"]

    now = client.get("/api/now", params={"at": "2027-06-13T15:30"}).json()
    assert now["at"] == "2027-06-13T15:30"
    assert [p["title"] for p in now["now_playing"]] == ["Maya Live"]


def test_unknown_things_are_404(client):
    assert client.get("/api/artists/nobody").status_code == 404
    assert client.get("/api/performances/nothing").status_code == 404
    assert client.get("/api/programme", params={"venue": "nowhere"}).status_code == 404


def test_the_admin_scenario_of_step_10(client, storage):
    created = client.post("/api/performances", json=NORA)
    assert created.status_code == 201
    assert created.json()["id"] == "le-kiosque-2027-06-13-1100"

    busy = client.post("/api/performances", json={**NORA, "start": "2027-06-13T11:30"})
    assert busy.status_code == 409
    assert "Le Kiosque" in busy.json()["detail"]

    on_stage = client.post(
        "/api/performances",
        json={**NORA, "venue": "grand-casino", "start": "2027-06-13T12:00"},
    )
    assert on_stage.status_code == 409
    assert "Nora Lebrun is on stage" in on_stage.json()["detail"]

    one_act = {
        **NORA,
        "kind": "lineup",
        "start": "2027-06-11T20:00",
        "host": "max-pellerin",
        "acts": ["nora-lebrun"],
    }
    assert client.post("/api/performances", json=one_act).status_code == 422

    moved = client.put(
        "/api/performances/le-kiosque-2027-06-13-1100",
        json={**NORA, "start": "2027-06-13T12:00"},
    )
    assert moved.json()["id"] == "le-kiosque-2027-06-13-1200"

    refused = client.put(
        "/api/performances/le-kiosque-2027-06-13-1200",
        json={**NORA, "start": "2027-06-13T15:00"},
    )
    assert refused.status_code == 409
    assert client.get("/api/performances/le-kiosque-2027-06-13-1200").status_code == 200

    # Tout a été enregistré dans le stockage.
    ids = [p["id"] for p in storage.load()["performances"]]
    assert "le-kiosque-2027-06-13-1200" in ids


def test_participants(client):
    url = "/api/performances/grand-casino-2027-06-12-1030/participants"

    first = client.post(url, json={"name": "Lou"})
    assert first.status_code == 201
    assert first.json()["places_left"] == 1

    assert client.post(url, json={"name": "Lou"}).status_code == 409
    assert client.post(url, json={"name": "Zoé"}).status_code == 201
    assert client.post(url, json={"name": "Adam"}).status_code == 409

    solo = "/api/performances/le-kiosque-2027-06-13-1500/participants"
    assert client.post(solo, json={"name": "Lou"}).status_code == 422


def test_artists_and_delete(client):
    assert client.post("/api/artists", json={"name": "Zoé Tanguy"}).status_code == 201
    assert client.post("/api/artists", json={"name": "zoe tanguy"}).status_code == 409
    assert client.post("/api/artists", json={"name": "  "}).status_code == 422

    deleted = client.delete("/api/performances/le-kiosque-2027-06-13-1500")
    assert deleted.status_code == 204
    assert client.get("/api/performances/le-kiosque-2027-06-13-1500").status_code == 404


def test_wrong_shape_is_refused_by_fastapi(client):
    response = client.post("/api/performances", json={"kind": "solo"})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_website_and_admin_are_served(client):
    assert client.get("/").status_code == 200
    assert client.get("/admin/").status_code == 200


def test_cli_uses_the_data_option(tmp_path, capsys):
    data_file = tmp_path / "festival.json"
    JSONStorage(data_file).save(DATA)

    main(["--data", str(data_file), "programme", "2027-06-13"])

    assert "Maya Live" in capsys.readouterr().out


# --- Étape 12 : le reste du contrat d'API.md --------------------------------

LINEUP = {
    "kind": "lineup",
    "title": "Gala",
    "venue": "grand-casino",
    "start": "2027-06-10T20:30",
    "duration_minutes": 90,
    "host": "max-pellerin",
    "acts": ["nora-lebrun", "maya-choukri"],
}


def test_programme_filters(client):
    client.post("/api/performances", json=LINEUP)

    everything = client.get("/api/programme").json()
    assert [p["start"] for p in everything] == sorted(p["start"] for p in everything)

    kiosque = client.get("/api/programme", params={"venue": "le-kiosque"}).json()
    assert {p["venue"] for p in kiosque} == {"le-kiosque"}

    both = client.get(
        "/api/programme", params={"day": "2027-06-10", "venue": "grand-casino"}
    ).json()
    assert [p["title"] for p in both] == ["Gala"]


def test_a_lineup_view(client):
    created = client.post("/api/performances", json=LINEUP).json()

    view = client.get(f"/api/performances/{created['id']}").json()
    assert view["host"] == "max-pellerin"
    assert view["acts"] == ["nora-lebrun", "maya-choukri"]
    # Tout le monde sur scène, dans l'ordre d'apparition : l'animateur d'abord.
    assert [a["slug"] for a in view["artists"]] == [
        "max-pellerin",
        "nora-lebrun",
        "maya-choukri",
    ]
    assert view["summary"] == "hosted by Max Pellerin, with Nora Lebrun, Maya Choukri"
    assert view["end"] == "2027-06-10T22:00"


def test_a_workshop_view(client):
    view = client.get("/api/performances/grand-casino-2027-06-12-1030").json()
    assert view["capacity"] == 2
    assert view["places_left"] == 2
    assert view["participants"] == []


def test_now_gives_three_at_most(client):
    client.post("/api/performances", json=LINEUP)
    client.post("/api/performances", json=NORA)

    now = client.get("/api/now", params={"at": "2027-06-01T12:00"}).json()
    assert now["now_playing"] == []
    assert len(now["up_next"]) == 3


def test_night_belongs_to_the_previous_day(client):
    night = {**NORA, "start": "2027-06-12T01:00"}
    view = client.post("/api/performances", json=night).json()
    assert view["festival_day"] == "2027-06-11"


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"venue": "nowhere"}, 404),
        ({"artist": "nobody"}, 404),
        ({"start": "2027-06-20T20:00"}, 409),
        ({"duration_minutes": 0}, 422),
        ({"duration_minutes": 361}, 422),
        ({"title": "  "}, 422),
        ({"kind": "concert"}, 422),
        ({"min_age": 25}, 422),
    ],
)
def test_each_error_status(client, change, status):
    response = client.post("/api/performances", json={**NORA, **change})
    assert response.status_code == status
    assert isinstance(response.json()["detail"], str)


def test_same_slot_twice_is_409(client):
    assert client.post("/api/performances", json=NORA).status_code == 201
    assert client.post("/api/performances", json=NORA).status_code == 409


def test_put_can_keep_its_own_slot(client):
    client.post("/api/performances", json=NORA)
    response = client.put(
        "/api/performances/le-kiosque-2027-06-13-1100",
        json={**NORA, "title": "Nouveau titre"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Nouveau titre"


def test_put_unknown_is_404(client):
    response = client.put("/api/performances/nothing", json=NORA)
    assert response.status_code == 404


def test_delete_twice(client):
    url = "/api/performances/le-kiosque-2027-06-13-1500"
    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 404


def test_wrong_parameter_is_refused_by_fastapi(client):
    response = client.get("/api/programme", params={"day": "June 11"})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


# --- Le fichier : une copie dans tmp_path, jamais data/festival.json --------


@pytest.fixture
def data_file(tmp_path):
    path = tmp_path / "festival.json"
    JSONStorage(path).save(DATA)
    return path


def test_every_change_is_saved_to_the_file(data_file):
    client = TestClient(create_app(JSONStorage(data_file)))
    client.post("/api/performances", json=NORA)

    # Une nouvelle application sur le même fichier voit le changement.
    restarted = TestClient(create_app(JSONStorage(data_file)))
    response = restarted.get("/api/performances/le-kiosque-2027-06-13-1100")
    assert response.status_code == 200


def test_missing_file_is_500(tmp_path):
    client = TestClient(create_app(JSONStorage(tmp_path / "missing.json")))
    response = client.get("/api/venues")
    assert response.status_code == 500
    assert "not found" in response.json()["detail"]


def test_damaged_file_is_500(data_file):
    data_file.write_text("{ not json", encoding="utf-8")
    client = TestClient(create_app(JSONStorage(data_file)))
    assert client.get("/api/programme").status_code == 500


def test_file_that_cannot_be_written_is_500(tmp_path):
    class ReadOnlyStorage(MemoryStorage):
        def save(self, data):
            raise FestivalStorageError("The data file cannot be written.")

    client = TestClient(create_app(ReadOnlyStorage(DATA)))
    response = client.post("/api/performances", json=NORA)
    assert response.status_code == 500
    # Rien n'a changé.
    assert client.get("/api/performances/le-kiosque-2027-06-13-1100").status_code == 404
