"""Render an athlete's cards to PNG from the command line.

    cd web
    python -m app.jobs.render_cards 306292            # every card, both designs
    python -m app.jobs.render_cards 306292 --design E # one design
    python -m app.jobs.render_cards 306292 --out /tmp/cards

Writes into the card cache (static/cards/) unless --out is given, so the site
serves the same files afterwards. Useful for checking a school's colors and
logo before a postseason, and for pulling a batch of cards to post.
"""

import argparse
import os
import shutil
import sys

from app import create_app
from app.services import cards


def main(argv):
    theParser = argparse.ArgumentParser(description="Render an athlete's cards to PNG.")
    theParser.add_argument("athlete_id", type=int)
    theParser.add_argument("--design", choices=list(cards.theDesignCodes), default=None)
    theParser.add_argument("--out", default=None, help="copy the PNGs here as well")
    theParser.add_argument("--force", action="store_true", help="render again even when a PNG is cached")
    theArgs = theParser.parse_args(argv)

    theDesigns = list(cards.theDesignCodes)
    if theArgs.design is not None:
        theDesigns = [theArgs.design]

    theApp = create_app()
    with theApp.test_request_context():
        theCards = cards.list_cards_for_athlete(theArgs.athlete_id)
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
