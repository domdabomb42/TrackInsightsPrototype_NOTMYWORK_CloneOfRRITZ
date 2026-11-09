"""School colors for the athlete cards.

Hand-maintained colors live in web/data/school_colors.json, keyed by school_id.
A school without an entry gets colors sampled from its logo, or the defaults.
"""

import json
import logging
import os
from functools import lru_cache

from common.const import CONST


logger = logging.getLogger(__name__)

theColorsPath = os.path.join(CONST.WEB_DIR, "data", "school_colors.json")
theDefaultPrimary = "#1b2a57"
theDefaultAccent = "#ffffff"
theNearBlack = "#111111"
theWhite = "#ffffff"
theBucket = 32
theSampleSize = 64
theOpaqueAlpha = 200
theDarkEnough = 0.55
theDistinctDistance = 120
theSaturated = 0.35


def _colors_file_stamp():
    try:
        return os.stat(theColorsPath).st_mtime_ns
    except OSError:
        return 0


def _configured_colors():
    return _configured_colors_at(_colors_file_stamp())


@lru_cache(maxsize=4)
def _configured_colors_at(stamp):
    try:
        with open(theColorsPath, encoding="utf-8") as theHandle:
            theRaw = json.load(theHandle)
    except (OSError, ValueError):
        return {}
    theOutput = {}
    for theKey in theRaw:
        theEntry = theRaw[theKey]
        if isinstance(theEntry, dict) == False:
            continue
        thePrimary = normalize_hex(theEntry.get("primary"))
        theAccent = normalize_hex(theEntry.get("accent"))
        if thePrimary is None:
            continue
        if theAccent is None:
            theAccent = theDefaultAccent
        theOutput[str(theKey)] = {"primary": thePrimary, "accent": theAccent}
    return theOutput


def normalize_hex(value):
    if value is None:
        return None
    theText = str(value).strip().lower()
    if theText.startswith("#") == False:
        theText = "#" + theText
    if len(theText) == 4:
        theText = "#" + theText[1] * 2 + theText[2] * 2 + theText[3] * 2
    if len(theText) != 7:
        return None
    for n in range(1, 7):
        if theText[n] not in "0123456789abcdef":
            return None
    return theText


def _luminance(rgb):
    return (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255.0


def _distance(rgb1, rgb2):
    return abs(rgb1[0] - rgb2[0]) + abs(rgb1[1] - rgb2[1]) + abs(rgb1[2] - rgb2[2])


def _to_hex(rgb):
    return "#%02x%02x%02x" % (rgb[0], rgb[1], rgb[2])


def _snap_edges(color):
    theRgb = (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))
    if max(theRgb) < 40:
        return theNearBlack
    if min(theRgb) > 235:
        return theWhite
    return color


def _saturation(rgb):
    theMax = max(rgb)
    if theMax == 0:
        return 0.0
    return (theMax - min(rgb)) / float(theMax)


def _background_of(image):
    theWidth, theHeight = image.size
    theCorners = [
        image.getpixel((0, 0)),
        image.getpixel((theWidth - 1, 0)),
        image.getpixel((0, theHeight - 1)),
        image.getpixel((theWidth - 1, theHeight - 1)),
    ]
    theOpaque = []
    for n in range(len(theCorners)):
        if theCorners[n][3] >= theOpaqueAlpha:
            theOpaque.append(theCorners[n][:3])
    if len(theOpaque) < 3:
        return None
    return theOpaque[0]


def _ranked_colors(path):
    from PIL import Image

    theImage = Image.open(path).convert("RGBA")
    theImage.thumbnail((theSampleSize, theSampleSize))
    theBackground = _background_of(theImage)
    theCounts = {}
    thePixels = list(theImage.getdata())
    for n in range(len(thePixels)):
        thePixel = thePixels[n]
        if thePixel[3] < theOpaqueAlpha:
            continue
        if theBackground is not None and _distance(thePixel[:3], theBackground) < 60:
            continue
        theKey = (
            thePixel[0] // theBucket * theBucket + theBucket // 2,
            thePixel[1] // theBucket * theBucket + theBucket // 2,
            thePixel[2] // theBucket * theBucket + theBucket // 2,
        )
        theCounts[theKey] = theCounts.get(theKey, 0) + 1
    theRanked = sorted(theCounts.items(), key=lambda item: -item[1])
    theOutput = []
    for n in range(len(theRanked)):
        theRgb = theRanked[n][0]
        if min(theRgb) > 235:
            continue
        theOutput.append(theRgb)
    return theOutput


def _pick_accent(ranked, primary):
    for n in range(len(ranked)):
        theCandidate = ranked[n]
        if _saturation(theCandidate) < theSaturated:
            continue
        if max(theCandidate) < 60:
            continue
        if _distance(theCandidate, primary) < theDistinctDistance:
            continue
        return theCandidate
    return None


def _colors_from_logo(path):
    theRanked = _ranked_colors(path)
    if len(theRanked) == 0:
        return {"primary": theDefaultPrimary, "accent": theDefaultAccent}
    theSaturatedDark = []
    for n in range(len(theRanked)):
        theCandidate = theRanked[n]
        if _saturation(theCandidate) >= theSaturated and max(theCandidate) >= 60 and _luminance(theCandidate) < theDarkEnough:
            theSaturatedDark.append(theCandidate)
    theTop = theRanked[0]
    theTopIsInk = _luminance(theTop) < 0.2 and _saturation(theTop) < theSaturated
    if theTopIsInk == True or len(theSaturatedDark) == 0:
        thePrimary = (17, 17, 17)
        if theTopIsInk == False:
            thePrimary = min(theRanked, key=_luminance)
    else:
        thePrimary = theSaturatedDark[0]
    theAccent = _pick_accent(theRanked, thePrimary)
    thePrimaryHex = _snap_edges(_to_hex(thePrimary))
    if theAccent is None:
        theAccentHex = theWhite
    else:
        theAccentHex = _snap_edges(_to_hex(theAccent))
    if theAccentHex == theNearBlack:
        theAccentHex = theWhite
    if _luminance(thePrimary) > 0.65:
        thePrimaryHex = theNearBlack
    return {"primary": thePrimaryHex, "accent": theAccentHex}


def school_colors(school_id, logo_path):
    theConfigured = _configured_colors().get(str(school_id))
    if theConfigured is not None:
        return dict(theConfigured)
    return dict(_sampled_colors(logo_path, school_id))


@lru_cache(maxsize=512)
def _sampled_colors(logo_path, school_id):
    if logo_path is not None and os.path.isfile(logo_path) == True:
        try:
            return _colors_from_logo(logo_path)
        except ImportError:
            logger.warning("Pillow is not installed, so school %s gets the default card colors", school_id)
        except OSError as theError:
            logger.warning("could not read the logo for school %s: %s", school_id, theError)
    return {"primary": theDefaultPrimary, "accent": theDefaultAccent}
