"""Precompute every athlete card into web/data/cards.db.

One row per card for every athlete who has a postseason result: the accolade
cards (champions, runners-up, qualifiers, state medalists) and, for any season
an athlete competed without earning one of those, a single season card for their
best result. The site reads this file; when it is missing or was built from a
different Track.db, the queries compute the same answer live.

    cd web
    python -m app.jobs.precompute_cards
    python -m app.jobs.precompute_cards --check

Commit web/data/cards.db along with Track.db. It is a few megabytes and the
deploy clones it with everything else.
"""

import os
import sqlite3
import sys
import time
from datetime import datetime, timezone

from app import create_app, db
from app.queries.cache import _db_fingerprint
from app.queries.cards import (
    _compute_cards_for_athlete,
    cards_db_path,
    cards_status,
    list_cards_for_athlete,
    theCardColumns,
)


theSchema = """
create table card (
    athlete_id integer not null,
    meet_id integer not null,
    event text not null,
    year integer not null,
    meet_type text not null,
    tier text not null,
    place integer,
    result text not null,
    gender text,
    name text not null,
    first text,
    last text,
    school_id integer,
    school_name text,
    acc1 text not null,
    acc2 text not null,
    cardId text not null,
    kind text not null,
    sort_order integer not null,
    primary key (athlete_id, meet_id, event)
);
create index card_athlete on card (athlete_id, sort_order);
create index card_year_stage on card (year, meet_type);
create table card_build (key text primary key, value text);
"""


def build_cards_db(path):
    theStart = time.time()
    theIds = [row[0] for row in db.session.execute(db.text("select distinct athlete_id from athlete_result order by athlete_id")).fetchall()]
    print("we are building cards for " + str(len(theIds)) + " athletes")
    theTemp = path + ".building"
    if os.path.exists(theTemp) == True:
        os.remove(theTemp)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    theConnection = sqlite3.connect(theTemp)
    try:
        theConnection.executescript(theSchema)
        theInsert = "insert into card (" + ", ".join(theCardColumns) + ", sort_order) values (" + ", ".join(["?"] * (len(theCardColumns) + 1)) + ")"
        theTotal = 0
        theSeason = 0
        theBatch = []
        for n in range(len(theIds)):
            theCards = _compute_cards_for_athlete(theIds[n])
            for i in range(len(theCards)):
                theRow = []
                for k in range(len(theCardColumns)):
                    theRow.append(theCards[i][theCardColumns[k]])
                theRow.append(i)
                theBatch.append(tuple(theRow))
                if theCards[i]["kind"] == "season":
                    theSeason = theSeason + 1
            theTotal = theTotal + len(theCards)
            if len(theBatch) >= 2000:
                theConnection.executemany(theInsert, theBatch)
                theBatch = []
            if n % 2000 == 0 and n > 0:
                print("we are at athlete " + str(n) + " of " + str(len(theIds)) + " with " + str(theTotal) + " cards so far, " + str(int(time.time() - theStart)) + "s in", flush=True)
                list_cards_for_athlete.cache_clear()
        if len(theBatch) > 0:
            theConnection.executemany(theInsert, theBatch)
        theMeta = [
            ("db_fingerprint", _db_fingerprint()),
            ("generated_at", datetime.now(timezone.utc).isoformat(timespec="seconds")),
            ("athletes", str(len(theIds))),
            ("cards", str(theTotal)),
            ("season_cards", str(theSeason)),
        ]
        theConnection.executemany("insert into card_build (key, value) values (?, ?)", theMeta)
        theConnection.commit()
    finally:
        theConnection.close()
    os.replace(theTemp, path)
    print("we wrote " + str(theTotal) + " cards (" + str(theSeason) + " season cards) for " + str(len(theIds)) + " athletes to " + path + " in " + str(int(time.time() - theStart)) + "s")
    return theTotal


def main():
    theApp = create_app()
    with theApp.app_context():
        build_cards_db(cards_db_path())
        list_cards_for_athlete.cache_clear()


def check():
    theApp = create_app()
    with theApp.app_context():
        theStatus = cards_status()
    if theStatus["built"] == False:
        print("cards.db: NOT BUILT -- run python -m app.jobs.precompute_cards")
        return 2
    if theStatus["stale"] == True:
        print("cards.db: STALE (built " + str(theStatus["generated_at"]) + ") -- the results changed since; the site is computing cards live")
        return 1
    print("cards.db: current (" + str(theStatus["count"]) + " cards, built " + str(theStatus["generated_at"]) + ")")
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    main()
