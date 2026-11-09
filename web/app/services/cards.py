"""Athlete cards: the full card dict, its HTML, and its rendered PNG.

The queries layer decides which results earn a card and what the card says.
This layer adds the school's colors and logos, builds the HTML from the approved
templates, and renders the PNG with headless Chromium, cached on disk so each
card is rendered once.
"""

import base64
import hashlib
import os
import re
import tempfile
import threading

from flask import current_app, url_for

from common.const import CONST

from ..queries.cards import get_card_data, list_cards_for_athlete
from . import card_templates
from .school_colors import school_colors


theCardWidth = 1080
theCardHeight = 1350
theDesignCodes = ("B", "E")
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
theTemplateVersion = "3"
theSilhouetteVersion = "2"
theStickerSize = 400
theSilhouetteWidth = 1200
theInkDark = 170
theInkLight = 235
theMinInkCoverage = 0.015
theChromiumArgs = ["--disable-gpu", "--headless"]
theChromiumNoSandbox = "--no-sandbox"


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


def card_cache_dir():
    theConfigured = current_app.config.get("CARD_CACHE_DIR")
    if theConfigured:
        return theConfigured
    return os.path.join(_static_folder(), "cards")


def _white_logo_dir():
    return os.path.join(_static_folder(), "cards", "logos")


def school_logo_path(school_id):
    if school_id is None:
        return None
    thePath = _static_path(os.path.join(CONST.SCHOOL_LOGO_STATIC_SUBDIR, str(school_id) + "." + CONST.SCHOOL_LOGO_EXT))
    if os.path.isfile(thePath) == True:
        return thePath
    return None


def white_logo_path(school_id):
    theSource = school_logo_path(school_id)
    if theSource is None:
        return None
    theTarget = os.path.join(_white_logo_dir(), str(school_id) + "_white_v" + theSilhouetteVersion + ".png")
    if os.path.isfile(theTarget) == True:
        return theTarget
    try:
        from PIL import Image
    except ImportError:
        current_app.logger.warning("Pillow is not installed, so card %s has no white logo silhouette", school_id)
        return None
    try:
        theImage = Image.open(theSource).convert("RGBA")
        theAlpha = _silhouette_alpha(theImage)
        if theAlpha is None:
            return None
        theWhite = Image.new("RGBA", theAlpha.size, (255, 255, 255, 255))
        theWhite.putalpha(theAlpha)
        os.makedirs(_white_logo_dir(), exist_ok=True)
        theHandle, theTemp = tempfile.mkstemp(dir=_white_logo_dir(), suffix=".png")
        os.close(theHandle)
        theWhite.save(theTemp, format="PNG")
        os.replace(theTemp, theTarget)
    except OSError as theError:
        current_app.logger.warning("could not build the white logo for school %s: %s", school_id, theError)
        return None
    return theTarget


def _ink_mask(image):
    theWidth, theHeight = image.size
    theAlpha = image.getchannel("A")
    theCorners = [
        image.getpixel((0, 0)),
        image.getpixel((theWidth - 1, 0)),
        image.getpixel((0, theHeight - 1)),
        image.getpixel((theWidth - 1, theHeight - 1)),
    ]
    theOpaqueCorners = []
    for n in range(len(theCorners)):
        if theCorners[n][3] >= 250:
            theOpaqueCorners.append(theCorners[n][:3])
    theBackground = None
    if len(theOpaqueCorners) >= 3 and min(theOpaqueCorners[0]) < theInkLight:
        theBackground = theOpaqueCorners[0]
    thePixels = list(image.getdata())
    theAlphaValues = list(theAlpha.getdata())
    theValues = []
    for n in range(len(thePixels)):
        thePixel = thePixels[n]
        if theBackground is None:
            theLightest = min(thePixel[0], thePixel[1], thePixel[2])
            if theLightest >= theInkLight:
                theInk = 0
            elif theLightest <= theInkDark:
                theInk = 255
            else:
                theInk = int(255 * (theInkLight - theLightest) / float(theInkLight - theInkDark))
        else:
            theDistance = abs(thePixel[0] - theBackground[0]) + abs(thePixel[1] - theBackground[1]) + abs(thePixel[2] - theBackground[2])
            if theDistance <= theKnockoutNear:
                theInk = 0
            elif theDistance >= theKnockoutFar:
                theInk = 255
            else:
                theInk = int(255 * (theDistance - theKnockoutNear) / float(theKnockoutFar - theKnockoutNear))
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


def _static_url(path):
    theRelative = os.path.relpath(path, _static_folder()).replace(os.sep, "/")
    return url_for("static", filename=theRelative)


def _data_uri(path):
    theExtension = os.path.splitext(path)[1].lower()
    theMime = theMimeTypes.get(theExtension, "application/octet-stream")
    with open(path, "rb") as theHandle:
        theBytes = theHandle.read()
    return "data:" + theMime + ";base64," + base64.b64encode(theBytes).decode("ascii")


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
    theWhitePath = white_logo_path(card["school_id"])
    theColors = school_colors(card["school_id"], theLogoPath)
    theLogo = None
    theWhite = None
    if theLogoPath is not None:
        if embed == True:
            theLogo = _data_uri(theLogoPath)
        else:
            theLogo = _static_url(theLogoPath)
    if theWhitePath is not None:
        if embed == True:
            theWhite = _data_uri(theWhitePath)
        else:
            theWhite = _static_url(theWhitePath)
    return {
        "name": card["school_name"],
        "primary": theColors["primary"],
        "accent": theColors["accent"],
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
        theHtml[theDesign] = url_for("main.card_page", athlete_id=card["athlete_id"], meet_id=card["meet_id"], event_name=card["event"], design=theDesign)
        thePng[theDesign] = url_for("main.card_png", athlete_id=card["athlete_id"], meet_id=card["meet_id"], event_name=card["event"], design=theDesign)
        theShare[theDesign] = url_for("main.card_share_page", athlete_id=card["athlete_id"], meet_id=card["meet_id"], event_name=card["event"], design=theDesign, _external=True)
        theNames[theDesign] = download_name(card, theDesign)
    return {"html_url": theHtml, "png_url": thePng, "share_url": theShare, "download_name": theNames}


def sticker_path(card, design):
    theTarget = os.path.join(card_cache_dir(), card["cardId"] + "-" + _render_key(card, design) + "-" + design + "-sticker.png")
    if os.path.isfile(theTarget) == True:
        return theTarget
    from PIL import Image

    theSource = render_png(card, design)
    theCard = Image.open(theSource).convert("RGBA")
    theScale = theStickerSize / float(theCard.height)
    theWidth = int(round(theCard.width * theScale))
    theCard = theCard.resize((theWidth, theStickerSize), Image.LANCZOS)
    theSticker = Image.new("RGBA", (theStickerSize, theStickerSize), (0, 0, 0, 0))
    theSticker.paste(theCard, ((theStickerSize - theWidth) // 2, 0))
    theTemp = _temp_beside(theTarget)
    try:
        theSticker.save(theTemp, format="PNG", optimize=True)
        _finish(theTemp, theTarget)
    finally:
        if os.path.exists(theTemp) == True:
            os.remove(theTemp)
    return theTarget


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


def _render_key(card, design):
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


def png_path(card, design):
    theName = card["cardId"] + "-" + _render_key(card, design) + "-" + design + ".png"
    return os.path.join(card_cache_dir(), theName)


def _screenshot(page, html, path):
    page.set_content(html, wait_until="load", timeout=theRenderTimeout)
    page.evaluate("document.fonts.ready")
    page.evaluate("window.fitCardText && window.fitCardText()")
    page.screenshot(path=path, clip={"x": 0, "y": 0, "width": theCardWidth, "height": theCardHeight}, timeout=theRenderTimeout)


def _finish(temp, target):
    try:
        os.replace(temp, target)
    finally:
        if os.path.exists(temp) == True:
            os.remove(temp)


def _temp_beside(target):
    theHandle, theTemp = tempfile.mkstemp(dir=os.path.dirname(target), suffix=".png")
    os.close(theHandle)
    return theTemp


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


def render_png(card, design):
    theTarget = png_path(card, design)
    if os.path.isfile(theTarget) == True:
        return theTarget
    theStart = _playwright()
    theHtml = card_html(card, design, embed=True)
    os.makedirs(os.path.dirname(theTarget), exist_ok=True)
    with theRenderGate:
        if os.path.isfile(theTarget) == True:
            return theTarget
        theTemp = _temp_beside(theTarget)
        try:
            with theStart() as thePlaywright:
                theBrowser = _launch(thePlaywright)
                try:
                    thePage = theBrowser.new_page(viewport={"width": theCardWidth, "height": theCardHeight})
                    _screenshot(thePage, theHtml, theTemp)
                finally:
                    theBrowser.close()
            _finish(theTemp, theTarget)
        finally:
            if os.path.exists(theTemp) == True:
                os.remove(theTemp)
    return theTarget


def render_many(cardList, designs, progress=None):
    theStart = _playwright()
    theDone = 0
    theSkipped = 0
    with theStart() as thePlaywright:
        theBrowser = _launch(thePlaywright)
        try:
            thePage = theBrowser.new_page(viewport={"width": theCardWidth, "height": theCardHeight})
            for n in range(len(cardList)):
                for i in range(len(designs)):
                    theTarget = png_path(cardList[n], designs[i])
                    if os.path.isfile(theTarget) == True:
                        theSkipped = theSkipped + 1
                        continue
                    os.makedirs(os.path.dirname(theTarget), exist_ok=True)
                    theTemp = _temp_beside(theTarget)
                    try:
                        _screenshot(thePage, card_html(cardList[n], designs[i], embed=True), theTemp)
                        _finish(theTemp, theTarget)
                    finally:
                        if os.path.exists(theTemp) == True:
                            os.remove(theTemp)
                    theDone = theDone + 1
                if progress is not None:
                    progress(n + 1, len(cardList), theDone, theSkipped)
        finally:
            theBrowser.close()
    return (theDone, theSkipped)
