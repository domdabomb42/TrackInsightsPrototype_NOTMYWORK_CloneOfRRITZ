"""Render athlete cards to PNG from the command line.

    cd web
    python -m app.jobs.render_cards 306292            # one athlete, both designs
    python -m app.jobs.render_cards 306292 --design E # one design
    python -m app.jobs.render_cards --all --year 2026 # every card of a season

Writes into the card cache (static/cards/) unless --out is given, so the site
serves the same files afterwards. A season is a few thousand cards; with one
browser kept open it runs at several cards a second. Cards already in the cache
are skipped, so the job can be stopped and restarted.
"""

import argparse
import os
import shutil
import sys
import time

from app import create_app, db
from app.queries.cards import list_cards_for_athlete
from app.services import cards


def _season_cards(year):
    theRows = db.session.execute(db.text(
        "select distinct ar.athlete_id from athlete_result ar join meet m on m.meet_id = ar.meet_id "
        "where ar.result_type = 'Final' and ar.place between 1 and 9 and m.year = :year"
    ), {"year": year}).fetchall()
    theCards = []
    for n in range(len(theRows)):
        theList = list_cards_for_athlete(theRows[n][0])
        for i in range(len(theList)):
            if theList[i]["year"] == year:
                theCards.append(theList[i])
        if n % 500 == 0:
            list_cards_for_athlete.cache_clear()
    return theCards


def main(argv):
    theParser = argparse.ArgumentParser(description="Render athlete cards to PNG.")
    theParser.add_argument("athlete_id", type=int, nargs="?", default=None)
    theParser.add_argument("--all", action="store_true", help="every card of one season (needs --year)")
    theParser.add_argument("--year", type=int, default=None)
    theParser.add_argument("--design", choices=list(cards.theDesignCodes), default=None)
    theParser.add_argument("--out", default=None, help="copy the PNGs here as well (single athlete only)")
    theParser.add_argument("--force", action="store_true", help="render again even when a PNG is cached")
    theArgs = theParser.parse_args(argv)

    theDesigns = list(cards.theDesignCodes)
    if theArgs.design is not None:
        theDesigns = [theArgs.design]

    theApp = create_app()
    with theApp.test_request_context():
        if theArgs.all == True:
            if theArgs.year is None:
                print("we need --year with --all")
                return 2
            theStart = time.time()
            theCards = _season_cards(theArgs.year)
            print("we found " + str(len(theCards)) + " cards for " + str(theArgs.year) + " and we will render " + str(len(theCards) * len(theDesigns)) + " PNGs")

            def progress(num, total, done, skipped):
                if num % 100 == 0 or num == total:
                    theElapsed = time.time() - theStart
                    print("we are at card " + str(num) + " of " + str(total) + ", rendered " + str(done) + ", already had " + str(skipped) + ", " + str(int(theElapsed)) + "s in", flush=True)

            theDone, theSkipped = cards.render_many(theCards, theDesigns, progress)
            print("we rendered " + str(theDone) + " PNGs and skipped " + str(theSkipped) + " cached ones in " + str(int(time.time() - theStart)) + "s")
            return 0

        if theArgs.athlete_id is None:
            print("we need an athlete_id, or --all with --year")
            return 2
        theCards = list_cards_for_athlete(theArgs.athlete_id)
        if len(theCards) == 0:
            print("we found no cards for athlete " + str(theArgs.athlete_id))
            return 1
        theCount = 0
        for n in range(len(theCards)):
            theCard = theCards[n]
            for i in range(len(theDesigns)):
                theDesign = theDesigns[i]
                theTarget = cards.png_path(theCard, theDesign)
                if theArgs.force == True and os.path.isfile(theTarget) == True:
                    os.remove(theTarget)
                thePath = cards.render_png(theCard, theDesign)
                if theArgs.out is not None:
                    os.makedirs(theArgs.out, exist_ok=True)
                    shutil.copyfile(thePath, os.path.join(theArgs.out, cards.download_name(theCard, theDesign)))
                theCount = theCount + 1
                print("we rendered " + theCard["cardId"] + " " + theDesign + " (" + theCard["acc1"] + ") -> " + thePath)
        print("we rendered " + str(theCount) + " cards for " + theCards[0]["name"] + " and we were expecting " + str(len(theCards) * len(theDesigns)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
