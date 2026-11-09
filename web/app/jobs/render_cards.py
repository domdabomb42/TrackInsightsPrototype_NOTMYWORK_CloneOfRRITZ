"""Export athlete cards as PNG files from the command line.

    cd web
    python -m app.jobs.render_cards 306292 --out ~/Desktop/cards        # one athlete
    python -m app.jobs.render_cards --all --year 2026 --out /tmp/cards   # a season
    python -m app.jobs.render_cards --all --year 2026 --out /tmp/cards --workers 5

The site itself renders cards in memory when someone asks for one and keeps
nothing on disk. This job is for pulling a batch of files to post or print:
it renders the same images and writes them to the folder you name.
"""

import argparse
import multiprocessing
import os
import sys
import time

from app import create_app, db
from app.queries.cards import list_cards_for_athlete
from app.services import cards


def _season_cards(year):
    theRows = db.session.execute(db.text(
        "select distinct ar.athlete_id from athlete_result ar join meet m on m.meet_id = ar.meet_id "
        "where m.year = :year"
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


def _write_all(theRendered, out):
    os.makedirs(out, exist_ok=True)
    for n in range(len(theRendered)):
        theCard, theDesign, theData = theRendered[n]
        with open(os.path.join(out, cards.download_name(theCard, theDesign)), "wb") as theHandle:
            theHandle.write(theData)


def _worker(num, cardList, designs, out, started):
    theApp = create_app()
    with theApp.test_request_context():
        def progress(count, total, done):
            if count % 200 == 0 or count == total:
                print("worker " + str(num) + " is at card " + str(count) + " of " + str(total) + ", " + str(int(time.time() - started)) + "s in", flush=True)
        theRendered = cards.render_many(cardList, designs, progress)
        _write_all(theRendered, out)
        return len(theRendered)


def main(argv):
    theParser = argparse.ArgumentParser(description="Export athlete cards as PNG files.")
    theParser.add_argument("athlete_id", type=int, nargs="?", default=None)
    theParser.add_argument("--all", action="store_true", help="every card of one season (needs --year)")
    theParser.add_argument("--year", type=int, default=None)
    theParser.add_argument("--design", choices=list(cards.theDesignCodes), default=None)
    theParser.add_argument("--out", required=True, help="folder to write the PNG files into")
    theParser.add_argument("--workers", type=int, default=1, help="browsers to run side by side for --all")
    theArgs = theParser.parse_args(argv)

    theDesigns = list(cards.theDesignCodes)
    if theArgs.design is not None:
        theDesigns = [theArgs.design]

    theApp = create_app()
    with theApp.test_request_context():
        theStart = time.time()
        if theArgs.all == True:
            if theArgs.year is None:
                print("we need --year with --all")
                return 2
            theCards = _season_cards(theArgs.year)
            print("we found " + str(len(theCards)) + " cards for " + str(theArgs.year) + " and we will write " + str(len(theCards) * len(theDesigns)) + " PNGs to " + theArgs.out)
            if theArgs.workers > 1:
                theSlices = [theCards[n::theArgs.workers] for n in range(theArgs.workers)]
                theContext = multiprocessing.get_context("spawn")
                with theContext.Pool(theArgs.workers) as thePool:
                    theCounts = thePool.starmap(_worker, [(n, theSlices[n], theDesigns, theArgs.out, theStart) for n in range(theArgs.workers)])
                theDone = sum(theCounts)
            else:
                theRendered = cards.render_many(theCards, theDesigns)
                _write_all(theRendered, theArgs.out)
                theDone = len(theRendered)
            print("we wrote " + str(theDone) + " PNGs in " + str(int(time.time() - theStart)) + "s")
            return 0

        if theArgs.athlete_id is None:
            print("we need an athlete_id, or --all with --year")
            return 2
        theCards = list_cards_for_athlete(theArgs.athlete_id)
        if len(theCards) == 0:
            print("we found no cards for athlete " + str(theArgs.athlete_id))
            return 1
        theRendered = cards.render_many(theCards, theDesigns)
        _write_all(theRendered, theArgs.out)
        for n in range(len(theRendered)):
            print("we wrote " + cards.download_name(theRendered[n][0], theRendered[n][1]) + " (" + theRendered[n][0]["acc1"] + ")")
        print("we wrote " + str(len(theRendered)) + " cards for " + theCards[0]["name"] + " to " + theArgs.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
