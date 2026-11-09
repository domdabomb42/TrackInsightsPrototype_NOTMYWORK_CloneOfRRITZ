"""Cards

Which postseason results earn an athlete card, and what the card says.
"""

import hashlib
import re
from functools import lru_cache

from sqlalchemy.orm import joinedload

from .. import db
from ..models import Athlete, AthleteResult, Event, Meet

from common.const import CONST

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


@lru_cache(maxsize=1024)
def list_cards_for_athlete(athlete_id):
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
            AthleteResult.result_type == CONST.RESULT_TYPE.FINAL,
            Meet.meet_type.in_(CONST.MEET_TYPE.ALL),
            Meet.year.isnot(None),
            Event.event_type != CONST.EVENT_TYPE.RELAY,
            AthleteResult.place.isnot(None),
            AthleteResult.place > 0,
        )
        .all()
    )
    if len(theRows) == 0:
        return []
    theAppeared = _athlete_appearances(athlete_id)
    theGender = theAthlete.gender
    theSchoolName = ""
    theSchoolId = None
    if theAthlete.school is not None:
        theSchoolName = theAthlete.school.school_name or ""
        theSchoolId = theAthlete.school.school_id
    theName = ((theAthlete.first or "").strip() + " " + (theAthlete.last or "").strip()).strip()
    theCards = []
    for n in range(len(theRows)):
        theResult = theRows[n][0]
        theMeet = theRows[n][1]
        theType = theRows[n][2] or CONST.EVENT_TYPE.TRACK
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
        theCards.append({
            "athlete_id": athlete_id,
            "meet_id": theMeet.meet_id,
            "event": theResult.event,
            "year": theMeet.year,
            "meet_type": theMeet.meet_type,
            "tier": theTierName[theMeet.meet_type],
            "place": theResult.place,
            "result": card_result(theResult.result),
            "gender": theGender,
            "name": theName,
            "first": (theAthlete.first or "").strip(),
            "last": (theAthlete.last or "").strip(),
            "school_id": theSchoolId,
            "school_name": theSchoolName,
            "acc1": theAccolade[0],
            "acc2": theAccolade[1],
            "cardId": card_id(athlete_id, theMeet.meet_id, theResult.event, theMeet.year, theMeet.meet_type),
        })
    theCards.sort(key=lambda item: (-item["year"], -_stage_rank(item["meet_type"]), item["event"]))
    return theCards


def get_card_data(athlete_id, meet_id, event):
    theCards = list_cards_for_athlete(athlete_id)
    for n in range(len(theCards)):
        if theCards[n]["meet_id"] == meet_id and theCards[n]["event"] == event:
            return theCards[n]
    return None
