"""Athlete cards: which results earn one, what it says, and how it is served."""
import os
import re

import pytest

from app.queries.cards import (
    accolade_for,
    card_id,
    card_result,
    cards_status,
    get_card_data,
    list_cards_for_athlete,
)
from app.services.school_colors import normalize_hex


theCardIdPattern = re.compile(r"^TI\d{2}-(SEC|REG|STA)-[0-9A-F]{4}$")


@pytest.mark.parametrize("meet_type,place,advanced,expected", [
    ("Sectional", 1, True, ("Sectional Champion", "Regional Qualifier")),
    ("Sectional", 2, True, ("Sectional Runner-Up", "Regional Qualifier")),
    ("Sectional", 3, True, ("Regional Qualifier", "")),
    ("Sectional", 5, True, ("Regional Qualifier", "")),
    ("Regional", 1, True, ("Regional Champion", "State Qualifier")),
    ("Regional", 2, True, ("Regional Runner-Up", "State Qualifier")),
    ("Regional", 3, True, ("State Qualifier", "")),
    ("State", 1, False, ("State Champion", "")),
    ("State", 2, False, ("State Runner-Up", "")),
    ("State", 3, False, ("State Medalist", "3rd in Indiana")),
    ("State", 6, False, ("State Medalist", "6th in Indiana")),
    ("State", 9, False, ("State Medalist", "9th in Indiana")),
])
def test_every_accolade_case(meet_type, place, advanced, expected):
    assert accolade_for(meet_type, place, advanced) == expected


@pytest.mark.parametrize("meet_type,place,advanced", [
    ("Sectional", 4, False),
    ("Regional", 7, False),
    ("State", 10, False),
    ("State", 0, False),
    ("Sectional", None, True),
])
def test_results_that_earn_no_card(meet_type, place, advanced):
    assert accolade_for(meet_type, place, advanced) is None


def test_card_id_format_and_stability():
    theFirst = card_id(101, 4, "100 Meters", 2024, "Sectional")
    theAgain = card_id(101, 4, "100 Meters", 2024, "Sectional")
    theOtherEvent = card_id(101, 4, "200 Meters", 2024, "Sectional")
    theState = card_id(101, 6, "100 Meters", 2024, "State")
    assert theCardIdPattern.match(theFirst)
    assert theFirst.startswith("TI24-SEC-")
    assert theFirst == theAgain
    assert theFirst != theOtherEvent
    assert theState.startswith("TI24-STA-")


@pytest.mark.parametrize("raw,expected", [
    ("5' 4\"", "5-4"),
    ("17' 3.75\"", "17-3.75"),
    ("34'2\"", "34-2"),
    ("7-2", "7-2"),
    ("4:58.69", "4:58.69"),
    ("44.59", "44.59"),
    (None, ""),
])
def test_card_result_reads_like_a_mark(raw, expected):
    assert card_result(raw) == expected


def test_normalize_hex():
    assert normalize_hex("#0033A0") == "#0033a0"
    assert normalize_hex("fff") == "#ffffff"
    assert normalize_hex("not a color") is None
    assert normalize_hex(None) is None


def test_athlete_cards_follow_the_fixture_results(app):
    with app.app_context():
        theCards = list_cards_for_athlete(101)
        theKeys = [(c["year"], c["meet_type"], c["event"], c["acc1"], c["acc2"], c["kind"]) for c in theCards]
        assert theKeys == [
            (2024, "Regional", "100 Meters", "State Qualifier", "", "accolade"),
            (2024, "Sectional", "100 Meters", "Regional Qualifier", "", "accolade"),
            (2023, "Sectional", "100 Meters", "Sectional Finalist", "10th Place", "season"),
        ]
        assert theCards[0]["cardId"].startswith("TI24-REG-")
        assert theCards[1]["school_name"] == "Alpha High"


def test_every_competitor_gets_a_season_card(app):
    with app.app_context():
        theCards = list_cards_for_athlete(105)
        assert len(theCards) == 1
        assert theCards[0]["acc1"] == "Sectional Finalist"
        assert theCards[0]["acc2"] == "10th Place"
        assert theCards[0]["result"] == "10:00.00"
        assert theCards[0]["kind"] == "season"


def test_a_season_with_an_accolade_gets_no_extra_season_card(app):
    with app.app_context():
        theCards = list_cards_for_athlete(111)
        theKinds = [(c["year"], c["kind"]) for c in theCards]
        assert theKinds == [(2024, "accolade"), (2024, "accolade")]


def test_stored_cards_db_is_read_when_it_matches_the_results(app, tmp_path):
    from app.jobs.precompute_cards import build_cards_db

    with app.app_context():
        thePath = str(tmp_path / "cards.db")
        app.config["CARDS_DB_PATH"] = thePath
        assert cards_status()["built"] is False
        theTotal = build_cards_db(thePath)
        assert theTotal > 0
        theStatus = cards_status()
        assert theStatus["built"] is True
        assert theStatus["stale"] is False
        assert theStatus["count"] == theTotal
        list_cards_for_athlete.cache_clear()
        theStored = list_cards_for_athlete(102)
        assert [c["acc1"] for c in theStored] == ["Regional Runner-Up", "Sectional Runner-Up"]
        assert theStored[0]["cardId"] == card_id(102, 5, "100 Meters", 2024, "Regional")


def test_a_fourth_place_who_ran_the_next_round_is_a_qualifier(app):
    with app.app_context():
        theCard = get_card_data(101, 4, "100 Meters")
        assert theCard is not None
        assert theCard["place"] == 4
        assert theCard["acc1"] == "Regional Qualifier"


def test_runner_up_gets_both_lines(app):
    with app.app_context():
        theCard = get_card_data(102, 4, "100 Meters")
        assert theCard["acc1"] == "Sectional Runner-Up"
        assert theCard["acc2"] == "Regional Qualifier"
        theRegional = get_card_data(102, 5, "100 Meters")
        assert theRegional["acc1"] == "Regional Runner-Up"
        assert theRegional["acc2"] == "State Qualifier"


def test_prelims_and_unknown_athletes_earn_nothing(app):
    with app.app_context():
        assert get_card_data(101, 6, "100 Meters") is None
        assert list_cards_for_athlete(999999) == []


def test_card_page_renders_the_approved_markup(client):
    theResponse = client.get("/card/102/4/100 Meters?design=B")
    assert theResponse.status_code == 200
    theHtml = theResponse.get_data(as_text=True)
    assert "Sectional<br>Runner-Up" in theHtml
    assert "Regional Qualifier" in theHtml
    assert "Blake<br>Sprinter" in theHtml
    assert "width:1080px;height:1350px" in theHtml
    assert "/static/fonts/oswald-latin-700-normal.woff2" in theHtml
    theBlackout = client.get("/card/102/4/100 Meters?design=E")
    assert theBlackout.status_code == 200
    theBlackoutHtml = theBlackout.get_data(as_text=True)
    assert "background:#0b0b0f" in theBlackoutHtml
    assert "Sectional Runner-Up" in theBlackoutHtml


def test_card_page_rejects_unknown_designs_and_missing_cards(client):
    assert client.get("/card/102/4/100 Meters?design=Z").status_code == 400
    assert client.get("/card/101/6/100 Meters").status_code == 404
    assert client.get("/card/999/4/100 Meters").status_code == 404


def test_cards_api_lists_urls_per_design(client):
    theResponse = client.get("/api/athletes/102/cards")
    assert theResponse.status_code == 200
    theCards = theResponse.get_json()["cards"]
    assert len(theCards) == 2
    theCard = theCards[1]
    assert theCard["meet_type"] == "Sectional"
    assert theCard["html_url"]["B"].endswith("?design=B")
    assert theCard["png_url"]["E"].endswith(".png?design=E")
    assert theCard["download_name"]["B"] == "blake-sprinter-2024-sectional-100-meters-b.png"
    assert client.get("/api/athletes/999/cards").status_code == 404


def test_card_png_renders_once_and_is_cached(app, client):
    pytest.importorskip("playwright")
    theResponse = client.get("/card/102/4/100 Meters.png?design=B")
    if theResponse.status_code == 503:
        pytest.skip("Chromium is not installed for Playwright on this machine")
    assert theResponse.status_code == 200
    assert theResponse.content_type == "image/png"
    assert theResponse.data[:8] == b"\x89PNG\r\n\x1a\n"
    theCacheDir = app.config["CARD_CACHE_DIR"]
    theFiles = [name for name in os.listdir(theCacheDir) if name.startswith("TI24-SEC-") and name.endswith("-B.png")]
    assert len(theFiles) >= 1
    assert not [name for name in os.listdir(theCacheDir) if name.startswith("tmp")]
    theAgain = client.get("/card/102/4/100 Meters.png?design=B")
    assert theAgain.status_code == 200
    assert theAgain.data == theResponse.data
