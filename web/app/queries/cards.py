"""Cards

Which postseason results earn an athlete card, and what the card says.
"""

import hashlib
import os
import re
import sqlite3
from functools import lru_cache

from sqlalchemy.orm import joinedload

from .. import db
from ..models import Athlete, AthleteResult, Event, Meet

from common.const import CONST

from .athletes import _fetch_relay_rows_for_athlete
from .cache import _active_db_path, _db_fingerprint
from .shared import (
    _AUTO_DEPTH,
    _CALLBACK_SLOTS,
    _STAGE_ORDER,
    _callback_group,
    _is_lower_better,
    _is_valid_postseason_mark,
)


theTierCode = {
    CONST.MEET_TYPE.SECTIONAL: "SEC",
    CONST.MEET_TYPE.REGIONAL: "REG",
    CONST.MEET_TYPE.STATE: "STA",
}

theTierName = {
    CONST.MEET_TYPE.SECTIONAL: "sectional",
    CONST.MEET_TYPE.REGIONAL: "regional",
    CONST.MEET_TYPE.STATE: "state",
}

theNextStage = {
    CONST.MEET_TYPE.SECTIONAL: CONST.MEET_TYPE.REGIONAL,
    CONST.MEET_TYPE.REGIONAL: CONST.MEET_TYPE.STATE,
}

theStateMedalDepth = 9

theKindAccolade = "accolade"
theKindSeason = "season"


class _RelayRow:
    def __init__(self, relay):
        self.event = relay.event
        self.place = relay.place
        self.result = relay.result
        self.result2 = relay.result2
        self.result_type = CONST.RESULT_TYPE.FINAL
        self.meet_id = relay.meet_id

theCardColumns = (
    "athlete_id", "meet_id", "event", "year", "meet_type", "tier", "place", "result",
    "gender", "name", "first", "last", "school_id", "school_name", "acc1", "acc2", "cardId", "kind",
)

theFeetInches = re.compile(r"^\s*(\d+)'\s*([\d.]+)\"?\s*$")


def ordinal(num):
    theRemainder = num % 100
    if theRemainder >= 11 and theRemainder <= 13:
        return str(num) + "th"
    theSuffix = {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")
    return str(num) + theSuffix


def accolade_for(meet_type, num, advanced):
    if num is None or num < 1:
        return None
    if meet_type == CONST.MEET_TYPE.STATE:
        if num == 1:
            return ("State Champion", "")
        if num == 2:
            return ("State Runner-Up", "")
        if num <= theStateMedalDepth:
            return ("State Medalist", ordinal(num) + " in Indiana")
        return None
    theNext = theNextStage.get(meet_type)
    if theNext is None:
        return None
    theQualifier = theNext + " Qualifier"
    if num == 1:
        return (meet_type + " Champion", theQualifier)
    if num == 2:
        return (meet_type + " Runner-Up", theQualifier)
    if advanced == True:
        return (theQualifier, "")
    return None


def card_id(athlete_id, meet_id, event, year, meet_type):
    theKey = str(athlete_id) + "|" + str(meet_id) + "|" + str(event)
    theHash = hashlib.md5(theKey.encode("utf-8")).hexdigest()[:4].upper()
    theYear = str(year)[-2:]
    return "TI" + theYear + "-" + theTierCode[meet_type] + "-" + theHash


def card_result(result):
    if result is None:
        return ""
    theText = str(result).strip()
    theMatch = theFeetInches.match(theText)
    if theMatch is None:
        return theText
    return theMatch.group(1) + "-" + theMatch.group(2)


@lru_cache(maxsize=256)
def _pool_rows(year, gender, meet_type, event):
    theRows = (
        db.session.query(
            AthleteResult.athlete_id,
            AthleteResult.meet_id,
            Meet.meet_num,
            AthleteResult.place,
            AthleteResult.result2,
            Event.event_type,
        )
        .join(Meet, AthleteResult.meet_id == Meet.meet_id)
        .join(Event, AthleteResult.event == Event.event)
        .filter(
            Meet.year == year,
            Meet.gender == gender,
            Meet.meet_type == meet_type,
            AthleteResult.event == event,
            AthleteResult.result_type == CONST.RESULT_TYPE.FINAL,
            AthleteResult.place.isnot(None),
            AthleteResult.place > 0,
            AthleteResult.result2.isnot(None),
        )
        .all()
    )
    theOutput = []
    for n in range(len(theRows)):
        theRow = theRows[n]
        theType = theRow.event_type or CONST.EVENT_TYPE.TRACK
        if _is_valid_postseason_mark(theRow.result2, theType) == False:
            continue
        theOutput.append((theRow.athlete_id, theRow.meet_id, theRow.meet_num, theRow.place, theRow.result2))
    return tuple(theOutput)


def _callback_advanced(athlete_id, meet_id, meet_num, event, year, gender, meet_type, mark, event_type):
    theSlots = _CALLBACK_SLOTS.get(meet_type)
    if theSlots is None:
        return False
    theGroup = _callback_group(meet_type, meet_num, event)
    theLowerIsBetter = _is_lower_better(event_type)
    thePool = _pool_rows(year, gender, meet_type, event)
    theBetter = 0
    theEqual = 0
    theContenders = 0
    for n in range(len(thePool)):
        theEntry = thePool[n]
        if theEntry[3] <= _AUTO_DEPTH:
            continue
        if _callback_group(meet_type, theEntry[2], event) != theGroup:
            continue
        theContenders = theContenders + 1
        theOther = theEntry[4]
        if theOther == mark:
            theEqual = theEqual + 1
        elif theLowerIsBetter == True and theOther < mark:
            theBetter = theBetter + 1
        elif theLowerIsBetter == False and theOther > mark:
            theBetter = theBetter + 1
    if theContenders <= theSlots:
        return False
    if theBetter + theEqual <= theSlots:
        return True
    return False


def _advanced(athlete_id, meet_id, meet_num, event, year, gender, meet_type, place, mark, event_type, appeared):
    if meet_type == CONST.MEET_TYPE.STATE:
        return False
    if place <= _AUTO_DEPTH:
        return True
    theNext = theNextStage.get(meet_type)
    if (theNext, year, event) in appeared:
        return True
    if _is_valid_postseason_mark(mark, event_type) == False:
        return False
    return _callback_advanced(athlete_id, meet_id, meet_num, event, year, gender, meet_type, mark, event_type)


def _relay_advanced(meet_type, year, event, place, appeared):
    if meet_type == CONST.MEET_TYPE.STATE:
        return False
    if place <= _AUTO_DEPTH:
        return True
    theNext = theNextStage.get(meet_type)
    if (theNext, year, event) in appeared:
        return True
    return False


def _athlete_appearances(athlete_id):
    theRows = (
        db.session.query(Meet.meet_type, Meet.year, AthleteResult.event)
        .join(Meet, AthleteResult.meet_id == Meet.meet_id)
        .filter(AthleteResult.athlete_id == athlete_id)
        .all()
    )
    theSet = set()
    for n in range(len(theRows)):
        theSet.add((theRows[n][0], theRows[n][1], theRows[n][2]))
    return theSet


def _stage_rank(meet_type):
    if meet_type in _STAGE_ORDER:
        return _STAGE_ORDER.index(meet_type)
    return -1


def _best_mark(result, event_type, prelims):
    if _is_valid_postseason_mark(result.result2, event_type) == True:
        return card_result(result.result)
    thePrelim = prelims.get((result.meet_id, result.event))
    if thePrelim is not None:
        return card_result(thePrelim)
    return card_result(result.result)


def _prelim_marks(rows):
    theMarks = {}
    for n in range(len(rows)):
        theResult = rows[n][0]
        theType = rows[n][2] or CONST.EVENT_TYPE.TRACK
        if theResult.result_type != CONST.RESULT_TYPE.PRELIM:
            continue
        if _is_valid_postseason_mark(theResult.result2, theType) == False:
            continue
        theMarks[(theResult.meet_id, theResult.event)] = theResult.result
    return theMarks


def _card_row(athlete, athlete_id, result, meet, kind, acc1, acc2, mark):
    theSchoolName = ""
    theSchoolId = None
    if athlete.school is not None:
        theSchoolName = athlete.school.school_name or ""
        theSchoolId = athlete.school.school_id
    theFirst = (athlete.first or "").strip()
    theLast = (athlete.last or "").strip()
    return {
        "athlete_id": athlete_id,
        "meet_id": meet.meet_id,
        "event": result.event,
        "year": meet.year,
        "meet_type": meet.meet_type,
        "tier": theTierName[meet.meet_type],
        "place": result.place,
        "result": mark,
        "gender": athlete.gender,
        "name": (theFirst + " " + theLast).strip(),
        "first": theFirst,
        "last": theLast,
        "school_id": theSchoolId,
        "school_name": theSchoolName,
        "acc1": acc1,
        "acc2": acc2,
        "cardId": card_id(athlete_id, meet.meet_id, result.event, meet.year, meet.meet_type),
        "kind": kind,
    }


def _season_card(athlete, athlete_id, rows, year, prelims):
    theBest = None
    theBestKey = None
    for n in range(len(rows)):
        theResult = rows[n][0]
        theMeet = rows[n][1]
        theType = rows[n][2] or CONST.EVENT_TYPE.TRACK
        if theMeet.year != year:
            continue
        theIsFinal = theResult.result_type == CONST.RESULT_TYPE.FINAL
        thePlaced = theResult.place is not None and theResult.place > 0
        theValid = _is_valid_postseason_mark(theResult.result2, theType)
        thePlace = theResult.place
        if thePlaced == False:
            thePlace = 10000
        theKey = (
            0 if theIsFinal == True else 1,
            0 if theValid == True else 1,
            -_stage_rank(theMeet.meet_type),
            thePlace,
            theResult.event,
        )
        if theBestKey is None or theKey < theBestKey:
            theBest = rows[n]
            theBestKey = theKey
    if theBest is None:
        return None
    theResult = theBest[0]
    theMeet = theBest[1]
    theMark = _best_mark(theResult, theBest[2] or CONST.EVENT_TYPE.TRACK, prelims)
    if theResult.result_type == CONST.RESULT_TYPE.FINAL and theResult.place is not None and theResult.place > 0:
        return _card_row(athlete, athlete_id, theResult, theMeet, theKindSeason, theMeet.meet_type + " Finalist", ordinal(theResult.place) + " Place", theMark)
    return _card_row(athlete, athlete_id, theResult, theMeet, theKindSeason, theMeet.meet_type + " Competitor", "", theMark)


def _compute_cards_for_athlete(athlete_id):
    theAthlete = (
        Athlete.query.options(joinedload(Athlete.school))
        .filter_by(athlete_id=athlete_id)
        .one_or_none()
    )
    if theAthlete is None:
        return []
    theRows = (
        db.session.query(AthleteResult, Meet, Event.event_type)
        .join(Meet, AthleteResult.meet_id == Meet.meet_id)
        .join(Event, AthleteResult.event == Event.event)
        .filter(
            AthleteResult.athlete_id == athlete_id,
            Meet.meet_type.in_(CONST.MEET_TYPE.ALL),
            Meet.year.isnot(None),
            Event.event_type != CONST.EVENT_TYPE.RELAY,
        )
        .all()
    )
    theRelays = _fetch_relay_rows_for_athlete(athlete_id, meet_types=CONST.MEET_TYPE.ALL)
    for n in range(len(theRelays)):
        theRelay = theRelays[n][0]
        theRelayMeet = theRelays[n][1]
        if theRelayMeet.year is None:
            continue
        theRows.append((_RelayRow(theRelay), theRelayMeet, CONST.EVENT_TYPE.RELAY))
    if len(theRows) == 0:
        return []
    theAppeared = _athlete_appearances(athlete_id)
    for n in range(len(theRows)):
        if theRows[n][2] == CONST.EVENT_TYPE.RELAY:
            theAppeared.add((theRows[n][1].meet_type, theRows[n][1].year, theRows[n][0].event))
    thePrelims = _prelim_marks(theRows)
    theGender = theAthlete.gender
    theCards = []
    theYearsCovered = set()
    theYearsSeen = set()
    for n in range(len(theRows)):
        theResult = theRows[n][0]
        theMeet = theRows[n][1]
        theType = theRows[n][2] or CONST.EVENT_TYPE.TRACK
        theYearsSeen.add(theMeet.year)
        if theResult.result_type != CONST.RESULT_TYPE.FINAL:
            continue
        if theResult.place is None or theResult.place <= 0:
            continue
        if theType == CONST.EVENT_TYPE.RELAY:
            theAdvanced = _relay_advanced(theMeet.meet_type, theMeet.year, theResult.event, theResult.place, theAppeared)
        else:
            theAdvanced = _advanced(
                athlete_id,
                theMeet.meet_id,
                theMeet.meet_num,
                theResult.event,
                theMeet.year,
                theGender,
                theMeet.meet_type,
                theResult.place,
                theResult.result2,
                theType,
                theAppeared,
            )
        theAccolade = accolade_for(theMeet.meet_type, theResult.place, theAdvanced)
        if theAccolade is None:
            continue
        theMark = _best_mark(theResult, theType, thePrelims)
        theCards.append(_card_row(theAthlete, athlete_id, theResult, theMeet, theKindAccolade, theAccolade[0], theAccolade[1], theMark))
        theYearsCovered.add(theMeet.year)
    theMissingYears = sorted(theYearsSeen - theYearsCovered)
    for n in range(len(theMissingYears)):
        theSeasonCard = _season_card(theAthlete, athlete_id, theRows, theMissingYears[n], thePrelims)
        if theSeasonCard is not None:
            theCards.append(theSeasonCard)
    theCards.sort(key=lambda item: (-item["year"], -_stage_rank(item["meet_type"]), item["event"]))
    return theCards


def cards_db_path():
    from flask import current_app

    theConfigured = None
    try:
        theConfigured = current_app.config.get("CARDS_DB_PATH")
    except RuntimeError:
        theConfigured = None
    if theConfigured:
        return theConfigured
    return os.path.join(os.path.dirname(_active_db_path()), "cards.db")


def _open_cards_db(path):
    theUri = "file:" + path.replace(os.sep, "/") + "?mode=ro"
    return sqlite3.connect(theUri, uri=True)


def cards_status():
    thePath = cards_db_path()
    if os.path.isfile(thePath) == False:
        return {"built": False, "stale": True, "path": thePath, "generated_at": None, "count": 0}
    try:
        theConnection = _open_cards_db(thePath)
        try:
            theMeta = dict(theConnection.execute("select key, value from card_build").fetchall())
            theCount = theConnection.execute("select count(*) from card").fetchone()[0]
        finally:
            theConnection.close()
    except sqlite3.Error:
        return {"built": False, "stale": True, "path": thePath, "generated_at": None, "count": 0}
    theStale = theMeta.get("db_fingerprint") != _db_fingerprint()
    return {
        "built": True,
        "stale": theStale,
        "path": thePath,
        "generated_at": theMeta.get("generated_at"),
        "count": theCount,
    }


def _stored_cards_for_athlete(athlete_id):
    theStatus = cards_status()
    if theStatus["built"] == False or theStatus["stale"] == True:
        return None
    theConnection = _open_cards_db(theStatus["path"])
    try:
        theRows = theConnection.execute(
            "select " + ", ".join(theCardColumns) + " from card where athlete_id = ? order by sort_order",
            (athlete_id,),
        ).fetchall()
    finally:
        theConnection.close()
    theCards = []
    for n in range(len(theRows)):
        theCard = {}
        for i in range(len(theCardColumns)):
            theCard[theCardColumns[i]] = theRows[n][i]
        theCards.append(theCard)
    return theCards


@lru_cache(maxsize=1024)
def list_cards_for_athlete(athlete_id):
    theStored = _stored_cards_for_athlete(athlete_id)
    if theStored is not None:
        return theStored
    return _compute_cards_for_athlete(athlete_id)


def get_card_data(athlete_id, meet_id, event):
    theCards = list_cards_for_athlete(athlete_id)
    for n in range(len(theCards)):
        if theCards[n]["meet_id"] == meet_id and theCards[n]["event"] == event:
            return theCards[n]
    return None
