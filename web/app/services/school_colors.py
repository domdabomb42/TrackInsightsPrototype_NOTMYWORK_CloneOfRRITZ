"""School colors for the athlete cards.

Hand-maintained colors live in web/data/school_colors.json, keyed by school_id.
A school without an entry gets colors sampled from its logo, or the defaults.
"""

import colorsys
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
theCardBlack = (11, 11, 15)
theMinAccentOnPrimary = 3.0
theMinAccentOnBlack = 4.5
theMinWhiteOnPrimary = 3.0
theSameHue = 0.11
theVividAccent = 0.5
theLightPrimary = 0.3
theYellowHueLow = 0.07
theYellowHueHigh = 0.2
theMinPrimaryShare = 0.025
theTintedSaturation = 0.12
theRichSaturation = 0.6
theGlowMinChannel = 40
theGlowSaturation = 0.85
theGlowMinSaturation = 0.3
theRichValueLow = 0.35
theRichValueHigh = 0.62


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


def _linear(channel):
    theValue = channel / 255.0
    if theValue <= 0.03928:
        return theValue / 12.92
    return ((theValue + 0.055) / 1.055) ** 2.4


def _relative_luminance(rgb):
    return 0.2126 * _linear(rgb[0]) + 0.7152 * _linear(rgb[1]) + 0.0722 * _linear(rgb[2])


def _contrast(rgb1, rgb2):
    theFirst = _relative_luminance(rgb1)
    theSecond = _relative_luminance(rgb2)
    if theFirst < theSecond:
        theFirst, theSecond = theSecond, theFirst
    return (theFirst + 0.05) / (theSecond + 0.05)


def _mix(rgb, target, amount):
    return (
        int(round(rgb[0] + (target[0] - rgb[0]) * amount)),
        int(round(rgb[1] + (target[1] - rgb[1]) * amount)),
        int(round(rgb[2] + (target[2] - rgb[2]) * amount)),
    )


def _reads_as_accent(rgb):
    if _relative_luminance(rgb) > theLightPrimary:
        return True
    theHue = colorsys.rgb_to_hsv(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)[0]
    if theHue >= theYellowHueLow and theHue <= theYellowHueHigh:
        return True
    return False


def _richen(rgb):
    if _saturation(rgb) < theTintedSaturation or max(rgb) < 60:
        return rgb
    theHue, theSat, theVal = colorsys.rgb_to_hsv(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
    theSat = max(theSat, theRichSaturation)
    theVal = min(max(theVal, theRichValueLow), theRichValueHigh)
    theRed, theGreen, theBlue = colorsys.hsv_to_rgb(theHue, theSat, theVal)
    return (int(round(theRed * 255)), int(round(theGreen * 255)), int(round(theBlue * 255)))


def _fit_primary(rgb):
    theColor = rgb
    for n in range(10):
        if _contrast((255, 255, 255), theColor) >= theMinWhiteOnPrimary:
            return theColor
        theColor = _mix(theColor, (0, 0, 0), 0.15)
    return theColor


def _same_hue(rgb1, rgb2):
    if _saturation(rgb1) < theSaturated or _saturation(rgb2) < theSaturated:
        return False
    theFirst = colorsys.rgb_to_hsv(rgb1[0] / 255.0, rgb1[1] / 255.0, rgb1[2] / 255.0)[0]
    theSecond = colorsys.rgb_to_hsv(rgb2[0] / 255.0, rgb2[1] / 255.0, rgb2[2] / 255.0)[0]
    theGap = abs(theFirst - theSecond)
    return min(theGap, 1.0 - theGap) < theSameHue


def _fit_accent(rgb, primary):
    if _same_hue(rgb, primary) == True:
        return (255, 255, 255)
    for n in range(11):
        theColor = _mix(rgb, (255, 255, 255), n / 10.0)
        if _contrast(theColor, primary) >= theMinAccentOnPrimary and _contrast(theColor, theCardBlack) >= theMinAccentOnBlack:
            if _saturation(theColor) < theVividAccent:
                return (255, 255, 255)
            return theColor
    return (255, 255, 255)


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
    theCounts = _color_counts(path)
    theRanked = sorted(theCounts.items(), key=lambda item: -item[1])
    theOutput = []
    for n in range(len(theRanked)):
        theOutput.append(theRanked[n][0])
    return theOutput


def _color_counts(path):
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
        if min(thePixel[:3]) > 235:
            continue
        theKey = (
            thePixel[0] // theBucket * theBucket + theBucket // 2,
            thePixel[1] // theBucket * theBucket + theBucket // 2,
            thePixel[2] // theBucket * theBucket + theBucket // 2,
        )
        theCounts[theKey] = theCounts.get(theKey, 0) + 1
    return theCounts


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
    theCounts = _color_counts(path)
    if len(theCounts) == 0:
        return {"primary": theDefaultPrimary, "accent": theDefaultAccent}
    theTotal = float(sum(theCounts.values()))
    theRanked = sorted(theCounts.items(), key=lambda item: -item[1])
    theColors = []
    for n in range(len(theRanked)):
        theColors.append(theRanked[n][0])
    theVivid = []
    for n in range(len(theRanked)):
        theCandidate = theRanked[n][0]
        if _saturation(theCandidate) >= theSaturated and max(theCandidate) >= 60 and theRanked[n][1] / theTotal >= theMinPrimaryShare:
            theVivid.append(theCandidate)
    if len(theVivid) == 0:
        for n in range(len(theRanked)):
            theCandidate = theRanked[n][0]
            if _saturation(theCandidate) >= theTintedSaturation and max(theCandidate) >= 60 and theRanked[n][1] / theTotal >= theMinPrimaryShare:
                theVivid.append(_richen(theCandidate))
                break
    thePrimary = None
    theAccent = None
    if len(theVivid) > 0:
        theLead = theVivid[0]
        if _reads_as_accent(theLead) == True:
            for n in range(1, len(theVivid)):
                theOther = theVivid[n]
                if _reads_as_accent(theOther) == False and _same_hue(theOther, theLead) == False:
                    thePrimary = theOther
                    break
            if thePrimary is None:
                thePrimary = (17, 17, 17)
            theAccent = theLead
        else:
            thePrimary = theLead
    if thePrimary is None:
        thePrimary = (17, 17, 17)
    else:
        thePrimary = _richen(thePrimary)
    thePrimary = _fit_primary(thePrimary)
    if theAccent is None:
        theAccent = _pick_accent(theColors, thePrimary)
    thePrimaryHex = _snap_edges(_to_hex(thePrimary))
    if theAccent is None:
        theAccentHex = theWhite
    else:
        theAccentHex = _snap_edges(_to_hex(_fit_accent(theAccent, thePrimary)))
    if theAccentHex == theNearBlack:
        theAccentHex = theWhite
    return {"primary": thePrimaryHex, "accent": theAccentHex}


def school_colors(school_id, logo_path):
    theConfigured = _configured_colors().get(str(school_id))
    if theConfigured is not None:
        theColors = dict(theConfigured)
    else:
        theColors = dict(_sampled_colors(logo_path, school_id))
    theColors["glow"] = glow_color(theColors["primary"], theColors["accent"])
    return theColors


def _from_hex(color):
    return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))


def glow_color(primary, accent):
    if accent != theWhite:
        return accent
    thePrimary = _from_hex(primary)
    if max(thePrimary) < theGlowMinChannel or _saturation(thePrimary) < theTintedSaturation:
        return theWhite
    theHue, theSat, theValue = colorsys.rgb_to_hsv(thePrimary[0] / 255.0, thePrimary[1] / 255.0, thePrimary[2] / 255.0)
    theBright = colorsys.hsv_to_rgb(theHue, max(theSat, theGlowSaturation), 1.0)
    theBright = (int(round(theBright[0] * 255)), int(round(theBright[1] * 255)), int(round(theBright[2] * 255)))
    for n in range(11):
        theColor = _mix(theBright, (255, 255, 255), n / 10.0)
        if _contrast(theColor, theCardBlack) >= theMinAccentOnBlack:
            if _saturation(theColor) < theGlowMinSaturation:
                return theWhite
            return _to_hex(theColor)
    return theWhite


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
