"""Athlete cards: the full card dict, its HTML, and its rendered PNG.

The queries layer decides which results earn a card and what the card says.
This layer adds the school's colors and logos, builds the HTML from the approved
templates, and renders the PNG with headless Chromium when someone asks for it.
Nothing is written to disk: the image is produced in memory and streamed to
the browser, with a small in-memory buffer so a repeat click is instant.
"""

import base64
import hashlib
import io
import os
import re
import threading
from collections import OrderedDict
from functools import lru_cache

from flask import current_app, url_for

from common.const import CONST

from ..queries.cards import get_card_data, list_cards_for_athlete
from . import card_templates
from .school_colors import school_colors


theCardWidth = 1080
theCardHeight = 1350
theDesignCodes = ("B", "E", "A")
theFontFiles = {
    "oswald500": "fonts/oswald-latin-500-normal.woff2",
    "oswald700": "fonts/oswald-latin-700-normal.woff2",
    "mono400": "fonts/space-mono-latin-400-normal.woff2",
    "mono700": "fonts/space-mono-latin-700-normal.woff2",
}
theTiLogoFile = "images/favicon-ti.webp"
theMimeTypes = {
    ".woff2": "font/woff2",
    ".webp": "image/webp",
    ".png": "image/png",
}
theSlugPattern = re.compile(r"[^a-z0-9]+")
theFlatAlpha = 250
theKnockoutNear = 30
theKnockoutFar = 90
theRenderGate = threading.BoundedSemaphore(2)
theRenderTimeout = 20000
theTemplateVersion = "6"
theSilhouetteWidth = 1200
theInkDark = 170
theInkLight = 235
theMinInkCoverage = 0.015
theBorderShare = 0.8
theStickerSize = 400
theChromiumArgs = ["--disable-gpu", "--headless"]
theChromiumNoSandbox = "--no-sandbox"
theRecentImages = 48
theRecentLock = threading.Lock()
theRecent = OrderedDict()


class CardRenderUnavailable(Exception):
    pass


def is_design(design):
    return design in theDesignCodes


def design_name(design):
    return card_templates.theDesignNames.get(design, design)


def _static_folder():
    return current_app.static_folder


def _static_path(filename):
    return os.path.join(_static_folder(), filename)


def school_logo_path(school_id):
    if school_id is None:
        return None
    thePath = _static_path(os.path.join(CONST.SCHOOL_LOGO_STATIC_SUBDIR, str(school_id) + "." + CONST.SCHOOL_LOGO_EXT))
    if os.path.isfile(thePath) == True:
        return thePath
    return None


def _border_background(image):
    theWidth, theHeight = image.size
    theFrame = max(2, int(round(min(theWidth, theHeight) * 0.04)))
    theCounts = {}
    theTotal = 0
    theBorderPixels = 0
    for y in range(theHeight):
        theEdgeRow = y < theFrame or y >= theHeight - theFrame
        for x in range(theWidth):
            if theEdgeRow == False and x >= theFrame and x < theWidth - theFrame:
                continue
            theBorderPixels = theBorderPixels + 1
            thePixel = image.getpixel((x, y))
            if thePixel[3] < 250:
                continue
            theKey = (thePixel[0] // 16 * 16 + 8, thePixel[1] // 16 * 16 + 8, thePixel[2] // 16 * 16 + 8)
            theCounts[theKey] = theCounts.get(theKey, 0) + 1
            theTotal = theTotal + 1
    if theTotal == 0 or theTotal < theBorderPixels * 0.6:
        return None
    theBest = max(theCounts.items(), key=lambda item: item[1])
    if theBest[1] < theTotal * theBorderShare:
        return None
    return theBest[0]


def _ink_mask(image):
    theAlphaChannel = image.getchannel("A")
    theBackground = _border_background(image)
    theAlphaValues = list(theAlphaChannel.getdata())
    thePixels = list(image.getdata())
    theValues = []
    for n in range(len(thePixels)):
        thePixel = thePixels[n]
        theLightest = min(thePixel[0], thePixel[1], thePixel[2])
        if theLightest >= theInkLight:
            theInk = 0
        elif theLightest <= theInkDark:
            theInk = 255
        else:
            theInk = int(255 * (theInkLight - theLightest) / float(theInkLight - theInkDark))
        if theBackground is not None:
            theDistance = abs(thePixel[0] - theBackground[0]) + abs(thePixel[1] - theBackground[1]) + abs(thePixel[2] - theBackground[2])
            if theDistance <= theKnockoutNear:
                theBackgroundInk = 0
            elif theDistance >= theKnockoutFar:
                theBackgroundInk = 255
            else:
                theBackgroundInk = int(255 * (theDistance - theKnockoutNear) / float(theKnockoutFar - theKnockoutNear))
            if min(theBackground) < theInkLight:
                theInk = theBackgroundInk
            else:
                theInk = min(theInk, theBackgroundInk)
        theValues.append(theInk * theAlphaValues[n] // 255)
    return theValues


def _silhouette_alpha(image):
    from PIL import Image, ImageFilter

    theValues = _ink_mask(image)
    theCoverage = sum(1 for n in range(len(theValues)) if theValues[n] > 128) / float(max(len(theValues), 1))
    if theCoverage < theMinInkCoverage:
        return None
    theMask = Image.new("L", image.size)
    theMask.putdata(theValues)
    theMask = theMask.filter(ImageFilter.MedianFilter(3))
    theScale = theSilhouetteWidth / float(image.size[0])
    theSize = (theSilhouetteWidth, max(1, int(round(image.size[1] * theScale))))
    theMask = theMask.resize(theSize, Image.LANCZOS)
    theMask = theMask.filter(ImageFilter.GaussianBlur(1.2))
    return theMask


@lru_cache(maxsize=512)
def _white_logo_bytes(logo_path):
    try:
        from PIL import Image
    except ImportError:
        current_app.logger.warning("Pillow is not installed, so cards have no white logo silhouette")
        return None
    try:
        theImage = Image.open(logo_path).convert("RGBA")
        theAlpha = _silhouette_alpha(theImage)
        if theAlpha is None:
            return None
        theWhite = Image.new("RGBA", theAlpha.size, (255, 255, 255, 255))
        theWhite.putalpha(theAlpha)
        theBuffer = io.BytesIO()
        theWhite.save(theBuffer, format="PNG")
        return theBuffer.getvalue()
    except OSError as theError:
        current_app.logger.warning("could not build the white logo from %s: %s", logo_path, theError)
        return None


def white_logo_png(school_id):
    theSource = school_logo_path(school_id)
    if theSource is None:
        return None
    return _white_logo_bytes(theSource)


def _static_url(path):
    theRelative = os.path.relpath(path, _static_folder()).replace(os.sep, "/")
    return url_for("static", filename=theRelative)


def _data_uri(path):
    theExtension = os.path.splitext(path)[1].lower()
    theMime = theMimeTypes.get(theExtension, "application/octet-stream")
    with open(path, "rb") as theHandle:
        theBytes = theHandle.read()
    return "data:" + theMime + ";base64," + base64.b64encode(theBytes).decode("ascii")


def _bytes_uri(data, mime):
    return "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")


def _assets(embed):
    theFonts = {}
    for theKey in theFontFiles:
        thePath = _static_path(theFontFiles[theKey])
        if embed == True:
            theFonts[theKey] = _data_uri(thePath)
        else:
            theFonts[theKey] = url_for("static", filename=theFontFiles[theKey])
    theTiPath = _static_path(theTiLogoFile)
    if embed == True:
        theTiLogo = _data_uri(theTiPath)
    else:
        theTiLogo = url_for("static", filename=theTiLogoFile)
    return {"tiLogo": theTiLogo, "fonts": theFonts}


def _school_block(card, embed):
    theLogoPath = school_logo_path(card["school_id"])
    theWhite = None
    theWhiteBytes = white_logo_png(card["school_id"])
    theColors = school_colors(card["school_id"], theLogoPath)
    theLogo = None
    if theLogoPath is not None:
        if embed == True:
            theLogo = _data_uri(theLogoPath)
        else:
            theLogo = _static_url(theLogoPath)
    if theWhiteBytes is not None:
        if embed == True:
            theWhite = _bytes_uri(theWhiteBytes, "image/png")
        else:
            theWhite = url_for("main.school_logo_white", school_id=card["school_id"], v=theTemplateVersion)
    return {
        "name": card["school_name"],
        "primary": theColors["primary"],
        "accent": theColors["accent"],
        "glow": theColors["glow"],
        "logo": theLogo,
        "logoWhite": theWhite,
    }


def _slug(text):
    theText = theSlugPattern.sub("-", str(text).lower()).strip("-")
    if theText == "":
        return "card"
    return theText


def download_name(card, design):
    return _slug(card["name"]) + "-" + str(card["year"]) + "-" + _slug(card["meet_type"]) + "-" + _slug(card["event"]) + "-" + design.lower() + ".png"


def _urls(card):
    theHtml = {}
    thePng = {}
    theShare = {}
    theNames = {}
    for n in range(len(theDesignCodes)):
        theDesign = theDesignCodes[n]
        theHtml[theDesign] = url_for("main.card_page", athlete_id=card["athlete_id"], meet_id=card["meet_id"], event_name=card["event"], design=theDesign, v=theTemplateVersion)
        thePng[theDesign] = url_for("main.card_png", athlete_id=card["athlete_id"], meet_id=card["meet_id"], event_name=card["event"], design=theDesign, v=theTemplateVersion)
        theShare[theDesign] = url_for("main.card_share_page", athlete_id=card["athlete_id"], meet_id=card["meet_id"], event_name=card["event"], design=theDesign, _external=True)
        theNames[theDesign] = download_name(card, theDesign)
    return {"html_url": theHtml, "png_url": thePng, "share_url": theShare, "download_name": theNames}


def card_summary(card):
    theSummary = {
        "athlete_id": card["athlete_id"],
        "meet_id": card["meet_id"],
        "event": card["event"],
        "year": card["year"],
        "meet_type": card["meet_type"],
        "place": card["place"],
        "result": card["result"],
        "acc1": card["acc1"],
        "acc2": card["acc2"],
        "card_id": card["cardId"],
    }
    theSummary.update(_urls(card))
    return theSummary


def list_cards(athlete_id):
    theCards = list_cards_for_athlete(athlete_id)
    theOutput = []
    for n in range(len(theCards)):
        theOutput.append(card_summary(theCards[n]))
    return theOutput


def get_card(athlete_id, meet_id, event):
    return get_card_data(athlete_id, meet_id, event)


def card_html(card, design, embed=False):
    theFull = dict(card)
    theFull["school"] = _school_block(card, embed)
    return card_templates.cardHtml(design, theFull, _assets(embed))


def render_key(card, design):
    theParts = [
        str(card["athlete_id"]),
        str(card["meet_id"]),
        str(card["event"]),
        str(card["place"]),
        str(card["result"]),
        str(card["acc1"]),
        str(card["acc2"]),
        str(card["school_id"]),
        design,
        theTemplateVersion,
    ]
    return hashlib.sha1("|".join(theParts).encode("utf-8")).hexdigest()[:16]


def _remember(key, data):
    with theRecentLock:
        theRecent[key] = data
        theRecent.move_to_end(key)
        while len(theRecent) > theRecentImages:
            theRecent.popitem(last=False)


def _recall(key):
    with theRecentLock:
        theData = theRecent.get(key)
        if theData is not None:
            theRecent.move_to_end(key)
        return theData


def forget_rendered_images():
    with theRecentLock:
        theRecent.clear()


def _launch(playwright):
    theExecutable = os.environ.get("CARD_CHROMIUM_PATH") or None
    if theExecutable is None:
        return playwright.chromium.launch()
    theArgs = list(theChromiumArgs)
    if os.environ.get("CARD_CHROMIUM_NO_SANDBOX") == "1":
        theArgs.append(theChromiumNoSandbox)
    return playwright.chromium.launch(executable_path=theExecutable, args=theArgs)


def _playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise CardRenderUnavailable("Playwright is not installed; run pip install -e '.[cards]' and playwright install chromium")
    return sync_playwright


def _screenshot(page, html):
    page.set_content(html, wait_until="load", timeout=theRenderTimeout)
    page.evaluate("document.fonts.ready")
    page.evaluate("window.fitCardText && window.fitCardText()")
    return page.screenshot(type="png", clip={"x": 0, "y": 0, "width": theCardWidth, "height": theCardHeight}, timeout=theRenderTimeout)


def render_png(card, design):
    theKey = render_key(card, design)
    theData = _recall(theKey)
    if theData is not None:
        return theData
    theStart = _playwright()
    theHtml = card_html(card, design, embed=True)
    with theRenderGate:
        theData = _recall(theKey)
        if theData is not None:
            return theData
        with theStart() as thePlaywright:
            theBrowser = _launch(thePlaywright)
            try:
                thePage = theBrowser.new_page(viewport={"width": theCardWidth, "height": theCardHeight})
                theData = _screenshot(thePage, theHtml)
            finally:
                theBrowser.close()
    _remember(theKey, theData)
    return theData


def render_sticker(card, design):
    from PIL import Image

    theKey = render_key(card, design) + "-sticker"
    theData = _recall(theKey)
    if theData is not None:
        return theData
    theCard = Image.open(io.BytesIO(render_png(card, design))).convert("RGBA")
    theScale = theStickerSize / float(theCard.height)
    theWidth = int(round(theCard.width * theScale))
    theCard = theCard.resize((theWidth, theStickerSize), Image.LANCZOS)
    theSticker = Image.new("RGBA", (theStickerSize, theStickerSize), (0, 0, 0, 0))
    theSticker.paste(theCard, ((theStickerSize - theWidth) // 2, 0))
    theBuffer = io.BytesIO()
    theSticker.save(theBuffer, format="PNG", optimize=True)
    theData = theBuffer.getvalue()
    _remember(theKey, theData)
    return theData


def render_many(cardList, designs, progress=None):
    theStart = _playwright()
    theDone = 0
    theOutput = []
    with theStart() as thePlaywright:
        theBrowser = _launch(thePlaywright)
        try:
            thePage = theBrowser.new_page(viewport={"width": theCardWidth, "height": theCardHeight})
            for n in range(len(cardList)):
                for i in range(len(designs)):
                    theData = _screenshot(thePage, card_html(cardList[n], designs[i], embed=True))
                    theOutput.append((cardList[n], designs[i], theData))
                    theDone = theDone + 1
                if progress is not None:
                    progress(n + 1, len(cardList), theDone)
        finally:
            theBrowser.close()
    return theOutput
