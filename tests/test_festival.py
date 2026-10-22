
from datetime import date, datetime

import pytest

from models import Artist, Venue, Performance, SoloShow, Lineup, Workshop, Festival
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

    with pytest.raises(ValueError, match="Unknown venue"):
        festival.add_performance(performance)



def test_unknown_artist_is_rejected(festival):
    performance = make_performance(
        venue="le-kiosque",
        artist="artiste-inexistant",
    )

    with pytest.raises(ValueError, match="Unknown artist"):
        festival.add_performance(performance)





def test_artist_in_lineup_conflict_is_rejected(festival):
    festival.venues.append(make_venue())

    # Enregistrer tous les artistes du Lineup.
    host = make_artist(name="Animateur")
    second_artist = make_artist(name="Artiste 2")

    festival.artists.extend([host, second_artist])

    performance = make_performance(
        kind="lineup",
        venue="autre-salle",
        acts=["karim-benali", second_artist.slug],
    )

    with pytest.raises(ValueError, match="Karim Benali is on stage"):
        festival.add_performance(performance)







def test_venue_conflict_is_rejected(festival):
    another_artist = make_artist()
    festival.artists.append(another_artist)

    performance = make_performance(
        venue="le-kiosque",
        artist=another_artist.slug,
    )

    with pytest.raises(ValueError, match="Le Kiosque is already booked"):
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

    with pytest.raises(ValueError, match="not a day of the festival"):
        festival.add_performance(performance)



@pytest.mark.parametrize("duration", [0, 361])
def test_invalid_duration_is_rejected(duration):
    with pytest.raises(ValueError, match="Duration must be between 1 and 360"):
        make_performance(duration=duration)
