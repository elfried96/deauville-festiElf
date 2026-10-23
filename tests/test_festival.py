from datetime import date, datetime

import pytest

from deauville.errors import (
    FestivalConflictError,
    FestivalNotFoundError,
    FestivalValidationError,
)
from deauville.festival import Festival
from deauville.models import Artist, Lineup, SoloShow, Venue, Workshop


@pytest.fixture
def festival():
    venue = Venue(
        name="Le Kiosque",
        capacity=120,
        address="Deauville",
    )
    artist = Artist(
        name="Karim Benali",
        bio="Humoriste",
        photo_url="",
    )

    performance = SoloShow(
        identifier="show-1",
        title="Premier spectacle",
        venue=venue.slug,
        start=datetime(2027, 6, 11, 20, 0),
        duration_minutes=60,
        artist=artist.slug,
    )

    return Festival(
        venues=[venue],
        artists=[artist],
        performances=[performance],
        name="Festival de test",
        first_day=date(2027, 6, 10),
        last_day=date(2027, 6, 13),
    )


def make_venue(name="Autre salle"):
    return Venue(name=name, capacity=100, address="Deauville")


def make_artist(name="Autre artiste"):
    return Artist(name=name, bio="Artiste de test", photo_url="")


def make_performance(
    identifier="show-2",
    title="Deuxième spectacle",
    venue="autre-salle",
    start=datetime(2027, 6, 11, 20, 30),
    duration=30,
    artist="karim-benali",
    kind="solo",
    acts=None,
):
    common = {
        "identifier": identifier,
        "title": title,
        "venue": venue,
        "start": start,
        "duration_minutes": duration,
    }

    if kind == "solo":
        return SoloShow(**common, artist=artist)

    if kind == "lineup":
        return Lineup(
            **common,
            host="animateur",
            acts=acts or ["artiste-1", "artiste-2"],
        )

    if kind == "workshop":
        return Workshop(
            **common,
            teacher=artist,
            max_participants=10,
        )

    raise ValueError(f"Unknown performance kind: {kind}")


def test_find_unknown_venue_returns_none(festival):
    assert festival.find_venue("lieu-inexistant") is None


def test_find_unknown_artist_returns_none(festival):
    assert festival.find_artist("artiste-inexistant") is None


def test_find_unknown_performance_returns_none(festival):
    assert festival.find_performance("spectacle-inexistant") is None


def test_now_playing_returns_current_performance(festival):
    moment = datetime(2027, 6, 11, 20, 30)

    result = festival.now_playing(moment)

    assert [p.title for p in result] == ["Premier spectacle"]


def test_up_next_returns_future_performances(festival):
    moment = datetime(2027, 6, 11, 19, 0)

    result = festival.up_next(moment)

    assert [p.title for p in result] == ["Premier spectacle"]


def test_unknown_venue_is_rejected(festival):
    performance = make_performance(venue="lieu-inexistant")

    with pytest.raises(FestivalNotFoundError, match="No venue"):
        festival.add_performance(performance)


def test_unknown_artist_is_rejected(festival):
    performance = make_performance(
        venue="le-kiosque",
        artist="artiste-inexistant",
    )

    with pytest.raises(FestivalNotFoundError, match="Unknown artist"):
        festival.add_performance(performance)


def test_artist_in_lineup_conflict_is_rejected(festival):
    festival.add_venue(make_venue())

    # Enregistrer tous les artistes du Lineup.
    host = make_artist(name="Animateur")
    second_artist = make_artist(name="Artiste 2")

    festival.add_artist(host)
    festival.add_artist(second_artist)

    performance = make_performance(
        kind="lineup",
        venue="autre-salle",
        acts=["karim-benali", second_artist.slug],
    )

    with pytest.raises(FestivalConflictError, match="Karim Benali is on stage"):
        festival.add_performance(performance)


def test_venue_conflict_is_rejected(festival):
    another_artist = make_artist()
    festival.add_artist(another_artist)

    performance = make_performance(
        venue="le-kiosque",
        artist=another_artist.slug,
    )

    with pytest.raises(FestivalConflictError, match="Le Kiosque is already booked"):
        festival.add_performance(performance)


def test_one_am_belongs_to_previous_festival_day():
    performance = make_performance(
        start=datetime(2027, 6, 12, 1, 0),
    )

    assert performance.festival_day == date(2027, 6, 11)


def test_date_outside_festival_is_rejected(festival):
    performance = make_performance(
        venue="le-kiosque",
        start=datetime(2027, 6, 14, 20, 0),
    )

    with pytest.raises(FestivalConflictError, match="not a day of the festival"):
        festival.add_performance(performance)


@pytest.mark.parametrize("duration", [0, 361])
def test_invalid_duration_is_rejected(duration):
    with pytest.raises(FestivalValidationError, match="Duration must be between"):
        make_performance(duration=duration)


def test_lineup_needs_two_acts():
    with pytest.raises(FestivalValidationError, match="at least two acts"):
        make_performance(kind="lineup", acts=["artiste-1"])


def test_collections_cannot_be_changed_from_outside(festival):
    festival.performances.clear()
    festival.artists.clear()

    assert len(festival.performances) == 1
    assert len(festival.artists) == 1


def test_refused_move_leaves_the_schedule_as_it_was(festival):
    festival.add_venue(make_venue())
    other = make_artist()
    festival.add_artist(other)
    festival.add_performance(
        make_performance(
            identifier="show-2",
            venue="autre-salle",
            start=datetime(2027, 6, 11, 18, 0),
            artist=other.slug,
        )
    )
    before = [p.id for p in festival.performances]

    # Karim Benali joue déjà à 20:00 : on essaie de déplacer son concurrent.
    moved = make_performance(
        identifier="moved",
        venue="autre-salle",
        start=datetime(2027, 6, 11, 20, 0),
        artist="karim-benali",
    )

    with pytest.raises(FestivalConflictError):
        festival.replace_performance("show-2", moved)

    assert [p.id for p in festival.performances] == before


def test_workshop_refuses_twice_the_same_name_and_when_full():
    workshop = make_performance(kind="workshop")
    workshop.max_participants = 2

    workshop.register("Lou")
    with pytest.raises(FestivalConflictError, match="already registered"):
        workshop.register("Lou")

    workshop.register("Zoé")
    with pytest.raises(FestivalConflictError, match="full"):
        workshop.register("Adam")


def test_only_a_workshop_takes_participants(festival):
    with pytest.raises(FestivalValidationError, match="not a workshop"):
        festival.register_participant("show-1", "Lou")


def test_same_artist_name_twice_is_refused(festival):
    festival.add_artist(Artist(name="Zoé Tanguy"))

    with pytest.raises(FestivalConflictError, match="already exists"):
        festival.add_artist(Artist(name="zoe tanguy"))
