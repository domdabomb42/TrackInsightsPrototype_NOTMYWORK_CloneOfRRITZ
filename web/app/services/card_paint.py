"""Paints the athlete card PNGs with Pillow, no browser needed.

Same three designs and the same layout numbers as card_templates.py, which
stays the HTML preview. This is what the .png routes and the export job use,
so cards render on any server that can run the site.
"""

import io
import math
from functools import lru_cache

import numpy
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

theWidth = 1080
theHeight = 1350
theBlack = (0, 0, 0)
theWhite = (255, 255, 255)
theGrainOpacity = 0.12
theGrainSeed = 7
theGrainScale = 2
theGrainLevels = 3
theSoftShadowBlur = 15
theSoftShadowDrop = 10
theHardShadowDrop = 6
theFitStep = 2
theMonoSpacing = 0.14


def _rgb(theHex):
    theHex = theHex.lstrip("#")
    return (int(theHex[0:2], 16), int(theHex[2:4], 16), int(theHex[4:6], 16))


@lru_cache(maxsize=256)
def _font(thePath, theSize):
    return ImageFont.truetype(thePath, int(theSize))


@lru_cache(maxsize=8)
def _image_file(thePath):
    return Image.open(thePath).convert("RGBA")


def _text_width(theFont, theText, theSpacing):
    if theSpacing == 0:
        return theFont.getlength(theText)
    theTotal = 0.0
    for n in range(len(theText)):
        theTotal = theTotal + theFont.getlength(theText[n]) + theSpacing
    return theTotal


def _draw_text(theDraw, theX, theBaseline, theText, theFont, theSpacing):
    if theSpacing == 0:
        theDraw.text((theX, theBaseline), theText, fill=255, font=theFont, anchor="ls")
        return
    theCursor = theX
    for n in range(len(theText)):
        theDraw.text((theCursor, theBaseline), theText[n], fill=255, font=theFont, anchor="ls")
        theCursor = theCursor + theFont.getlength(theText[n]) + theSpacing


def _fit(theLines, thePath, theSize, theMinimum, theSpacingEm, theLimit):
    while True:
        theFont = _font(thePath, theSize)
        theSpacing = theSpacingEm * theSize
        theWidest = 0.0
        for n in range(len(theLines)):
            theWidest = max(theWidest, _text_width(theFont, theLines[n], theSpacing))
        if theWidest <= theLimit or theSize - theFitStep < theMinimum:
            return theFont, theSpacing, theWidest
        theSize = theSize - theFitStep


def _baseline(theTop, theLineHeight, theFont):
    theAscent, theDescent = theFont.getmetrics()
    return theTop + (theLineHeight - (theAscent + theDescent)) / 2.0 + theAscent


def _normal_height(theFont):
    theAscent, theDescent = theFont.getmetrics()
    return theAscent + theDescent


def _paste_color(theCanvas, theColor, theMask, theOpacity=1.0, theOffset=(0, 0)):
    if theOpacity < 1.0:
        theMask = theMask.point(lambda v: int(v * theOpacity))
    theCanvas.paste(Image.new("RGB", theCanvas.size, theColor), theOffset, theMask)


def _paint_text(theCanvas, theItems, theColor, theOpacity=1.0, theShadow=None):
    theMask = Image.new("L", theCanvas.size, 0)
    theDraw = ImageDraw.Draw(theMask)
    for n in range(len(theItems)):
        theX, theBaseline, theText, theFont, theSpacing = theItems[n]
        _draw_text(theDraw, theX, theBaseline, theText, theFont, theSpacing)
    if theShadow == "soft":
        theBlur = theMask.filter(ImageFilter.GaussianBlur(theSoftShadowBlur))
        _paste_color(theCanvas, theBlack, theBlur, 0.35, (0, theSoftShadowDrop))
    elif theShadow == "hard":
        _paste_color(theCanvas, theBlack, theMask, 0.3, (0, theHardShadowDrop))
    _paste_color(theCanvas, theColor, theMask, theOpacity)


def _alpha_mask(theArray):
    return Image.fromarray(numpy.clip(theArray * 255.0, 0, 255).astype("uint8"), "L")


def _horizontal_wash(theCanvas, theColor, theStart, theEnd):
    theX = numpy.linspace(0.0, 1.0, theWidth)
    theRow = numpy.clip(theStart * (1.0 - theX / theEnd), 0.0, theStart)
    theArray = numpy.tile(theRow, (theHeight, 1))
    _paste_color(theCanvas, theColor, _alpha_mask(theArray))


def _vertical_wash(theCanvas, theColor, theFrom, theStrength):
    theY = numpy.linspace(0.0, 1.0, theHeight)
    theColumn = numpy.clip((theY - theFrom) / (1.0 - theFrom), 0.0, 1.0) * theStrength
    theArray = numpy.tile(theColumn[:, None], (1, theWidth))
    _paste_color(theCanvas, theColor, _alpha_mask(theArray))


def _radial_wash(theCanvas, theColor, theCenter, theRadii, theStrength, theFade):
    theY, theX = numpy.mgrid[0:theHeight, 0:theWidth]
    theDistance = numpy.sqrt(((theX - theCenter[0]) / float(theRadii[0])) ** 2 + ((theY - theCenter[1]) / float(theRadii[1])) ** 2)
    theArray = numpy.clip(1.0 - theDistance / theFade, 0.0, 1.0) * theStrength
    _paste_color(theCanvas, theColor, _alpha_mask(theArray))


def _grain(theCanvas):
    theRandom = numpy.random.default_rng(theGrainSeed)
    theSmall = (theHeight // theGrainScale, theWidth // theGrainScale)
    theValues = theRandom.integers(0, theGrainLevels, theSmall) * (255 // (theGrainLevels - 1))
    theNoise = Image.fromarray(theValues.astype("uint8"), "L").resize((theWidth, theHeight), Image.BILINEAR).convert("RGB")
    theOverlay = ImageChops.overlay(theCanvas, theNoise)
    theCanvas.paste(Image.blend(theCanvas, theOverlay, theGrainOpacity))


def _watermark(theCanvas, theBytes, theBoxWidth, theCenter, theOpacity, theAngle, theDark):
    if theBytes is None:
        return
    theLogo = Image.open(io.BytesIO(theBytes)).convert("RGBA")
    theBoxHeight = max(1, int(round(theLogo.size[1] * theBoxWidth / float(theLogo.size[0]))))
    theLogo = theLogo.resize((theBoxWidth, theBoxHeight), Image.LANCZOS)
    theAlpha = theLogo.getchannel("A").filter(ImageFilter.GaussianBlur(2)).point(lambda v: int(v * theOpacity))
    theColor = theWhite
    if theDark == True:
        theColor = theBlack
    theLayer = Image.new("RGBA", theLogo.size, theColor + (0,))
    theLayer.putalpha(theAlpha)
    if theAngle != 0:
        theLayer = theLayer.rotate(theAngle, resample=Image.BICUBIC, expand=True)
    thePosition = (int(round(theCenter[0] - theLayer.size[0] / 2.0)), int(round(theCenter[1] - theLayer.size[1] / 2.0)))
    theCanvas.paste(theLayer, thePosition, theLayer)


def _rounded(theImage, theRadius):
    theMask = Image.new("L", theImage.size, 0)
    ImageDraw.Draw(theMask).rounded_rectangle((0, 0, theImage.size[0] - 1, theImage.size[1] - 1), radius=theRadius, fill=255)
    theAlpha = ImageChops.multiply(theImage.getchannel("A"), theMask)
    theOut = theImage.copy()
    theOut.putalpha(theAlpha)
    return theOut


def _ti_block(theCanvas, theFiles, theLeft, theTop, theInk, theSize=110):
    theLogo = _rounded(_image_file(theFiles["tiLogo"]).resize((theSize, theSize), Image.LANCZOS), int(theSize * 0.18))
    theCanvas.paste(theLogo, (theLeft, theTop), theLogo)
    theFont = _font(theFiles["fonts"]["oswald700"], int(theSize * 0.4))
    theLineHeight = int(theSize * 0.4) * 0.95
    theBlockTop = theTop + (theSize - 2 * theLineHeight) / 2.0
    theX = theLeft + theSize + 18
    _paint_text(theCanvas, [
        (theX, _baseline(theBlockTop, theLineHeight, theFont), "TRACK", theFont, 0),
        (theX, _baseline(theBlockTop + theLineHeight, theLineHeight, theFont), "INSIGHTS", theFont, 0),
    ], theInk)


def _tag(theCanvas, theFiles, theRight, theTop, theColor, theInk, theYear, theId, theIdColor, theIdOpacity):
    theYearFont = _font(theFiles["fonts"]["mono700"], 26)
    theSpacing = theMonoSpacing * 26
    theYearText = str(theYear)
    theBoxWidth = int(round(_text_width(theYearFont, theYearText, theSpacing) + 44))
    theBoxHeight = 14 + 26 + 10
    ImageDraw.Draw(theCanvas).rectangle((theRight - theBoxWidth, theTop, theRight, theTop + theBoxHeight), fill=theColor)
    _paint_text(theCanvas, [(theRight - theBoxWidth + 22, _baseline(theTop + 14, 26, theYearFont), theYearText, theYearFont, theSpacing)], theInk)
    theIdFont = _font(theFiles["fonts"]["mono400"], 16)
    theIdSpacing = theMonoSpacing * 16
    theIdWidth = _text_width(theIdFont, theId, theIdSpacing)
    theIdTop = theTop + theBoxHeight + 10
    _paint_text(theCanvas, [(theRight - theIdWidth, theIdTop + theIdFont.getmetrics()[0], theId.upper(), theIdFont, theIdSpacing)], theIdColor, theIdOpacity)


def _name_lines(theCard):
    theFirst = (theCard.get("first") or "").strip()
    theLast = (theCard.get("last") or "").strip()
    if theFirst != "" and theLast != "":
        return [theFirst.upper(), theLast.upper()]
    return _two_lines(theCard["name"])


def _two_lines(theText):
    theParts = str(theText).upper().split(" ", 1)
    return theParts


def _chip(theCanvas, theSchool, theRight, theBottom):
    theBytes = theSchool.get("chipBytes")
    if theBytes is None:
        return 0
    theAspect = theSchool.get("logoAspect", 1.0)
    theChipWidth = int(round(min(260, max(110, 84 * theAspect + 26))))
    theBox = (theRight - theChipWidth, theBottom - 110, theRight, theBottom)
    ImageDraw.Draw(theCanvas).rounded_rectangle(theBox, radius=16, fill=theWhite)
    theLogo = Image.open(io.BytesIO(theBytes)).convert("RGBA")
    theScale = min((theChipWidth - 26) / float(theLogo.size[0]), 84 / float(theLogo.size[1]), 1.0)
    theLogo = theLogo.resize((max(1, int(round(theLogo.size[0] * theScale))), max(1, int(round(theLogo.size[1] * theScale)))), Image.LANCZOS)
    thePosition = (int(round(theBox[0] + (theChipWidth - theLogo.size[0]) / 2.0)), int(round(theBox[1] + (110 - theLogo.size[1]) / 2.0)))
    theCanvas.paste(theLogo, thePosition, theLogo)
    return theChipWidth


def _school_row(theCanvas, theFiles, theTop, theLeft, theName, theAccent, theColor, theOpacity, theBarWidth, theBarHeight, theGap, theCentered):
    theFont, theSpacing, theTextWidth = _fit([theName], theFiles["fonts"]["mono700"], 28, 16, theMonoSpacing, 700)
    theRowHeight = _normal_height(theFont)
    theTotal = theBarWidth * 2 + theGap * 2 + theTextWidth
    theStart = theLeft
    if theCentered == True:
        theStart = theWidth / 2.0 - theTotal / 2.0
    theMiddle = theTop + theRowHeight / 2.0
    theDraw = ImageDraw.Draw(theCanvas)
    theDraw.rectangle((theStart, theMiddle - theBarHeight / 2.0, theStart + theBarWidth, theMiddle + theBarHeight / 2.0), fill=theAccent)
    theTextX = theStart + theBarWidth + theGap
    _paint_text(theCanvas, [(theTextX, theTop + theFont.getmetrics()[0], theName, theFont, theSpacing)], theColor, theOpacity)
    theSecond = theTextX + theTextWidth + theGap
    theDraw.rectangle((theSecond, theMiddle - theBarHeight / 2.0, theSecond + theBarWidth, theMiddle + theBarHeight / 2.0), fill=theAccent)
    return theRowHeight


def _rail_card(theCard, theFiles, theBackground, theAccent, theTagInk, theWash, theLogoOpacity, theInk):
    theSchool = theCard["school"]
    theCanvas = Image.new("RGB", (theWidth, theHeight), _rgb(theBackground))
    theLight = theInk != "#ffffff"
    theInkColor = _rgb(theInk)
    theAccentColor = _rgb(theAccent)
    theMuted = (theWhite, 0.9)
    theFaint = (theWhite, 0.75)
    theSoft = "soft"
    theHard = "hard"
    if theLight == True:
        theMuted = ((17, 17, 17), 0.85)
        theFaint = ((17, 17, 17), 0.7)
        theSoft = None
        theHard = None
    if theWash == "dark":
        _horizontal_wash(theCanvas, theBlack, 0.45, 0.55)
        _vertical_wash(theCanvas, theBlack, 0.5, 0.5)
    elif theWash == "light":
        _horizontal_wash(theCanvas, theWhite, 0.3, 0.55)
        _vertical_wash(theCanvas, theBlack, 0.55, 0.14)
    else:
        _radial_wash(theCanvas, theWhite, (theWidth * 0.3, theHeight * 0.2), (theWidth * 0.9, theHeight * 0.6), 0.08, 0.7)
        _vertical_wash(theCanvas, theBlack, 0.5, 0.5)
    theLogoBox = 1250
    theLogoBytes = theSchool.get("whiteBytes")
    if theLogoBytes is not None:
        theLogoImage = Image.open(io.BytesIO(theLogoBytes))
        theLogoHeight = theLogoBox * theLogoImage.size[1] / float(theLogoImage.size[0])
        _watermark(theCanvas, theLogoBytes, theLogoBox, (theWidth + 380 - theLogoBox / 2.0, 120 + theLogoHeight / 2.0), theLogoOpacity, 8, theLight)
    _grain(theCanvas)
    ImageDraw.Draw(theCanvas).rectangle((0, 0, 30, theHeight), fill=theAccentColor)
    _ti_block(theCanvas, theFiles, 90, 56, theInkColor)
    _tag(theCanvas, theFiles, 1020, 56, theAccentColor, _rgb(theTagInk), theCard["year"], theCard["cardId"], theFaint[0], theFaint[1])
    theLimit = 930
    theLines = _name_lines(theCard)
    theFont, theSpacing, theWide = _fit(theLines, theFiles["fonts"]["oswald700"], 170, 90, -0.025, theLimit)
    theLineHeight = theFont.size * 0.86
    theItems = []
    for n in range(len(theLines)):
        theItems.append((90, _baseline(280 + n * theLineHeight, theLineHeight, theFont), theLines[n], theFont, theSpacing))
    _paint_text(theCanvas, theItems, theInkColor, 1.0, theSoft)
    theRowTop = 280 + len(theLines) * theLineHeight + 26
    _school_row(theCanvas, theFiles, theRowTop, 90, theSchool["name"].upper(), theAccentColor, theMuted[0], theMuted[1], 70, 4, 20, False)
    theAccLines = _two_lines(theCard["acc1"])
    theFont, theSpacing, theWide = _fit(theAccLines, theFiles["fonts"]["oswald700"], 124, 64, -0.01, theLimit)
    theLineHeight = theFont.size * 0.88
    theItems = []
    for n in range(len(theAccLines)):
        theItems.append((90, _baseline(690 + n * theLineHeight, theLineHeight, theFont), theAccLines[n], theFont, theSpacing))
    _paint_text(theCanvas, theItems, theAccentColor, 1.0, theHard)
    if theCard["acc2"] != "":
        theTop = 690 + len(theAccLines) * theLineHeight + 16
        theFont, theSpacing, theWide = _fit([theCard["acc2"].upper()], theFiles["fonts"]["oswald700"], 62, 36, 0.04, theLimit)
        _paint_text(theCanvas, [(90, theTop + theFont.getmetrics()[0], theCard["acc2"].upper(), theFont, theSpacing)], theInkColor)
    theBottom = theHeight - 64
    theChipWidth = _chip(theCanvas, theSchool, 1020, theBottom - 10)
    theColumn = theLimit
    if theChipWidth > 0:
        theColumn = theLimit - theChipWidth - 30
    theResultFont, theResultSpacing, theWide = _fit([theCard["result"].upper()], theFiles["fonts"]["oswald700"], 200, 100, -0.035, theColumn)
    theResultHeight = theResultFont.size * 0.86
    theEventFont, theEventSpacing, theWide = _fit([(theCard["gender"] + " " + theCard["event"]).upper()], theFiles["fonts"]["mono700"], 30, 18, theMonoSpacing, theColumn)
    theEventTop = theBottom - theResultHeight - 8 - _normal_height(theEventFont)
    _paint_text(theCanvas, [(90, theEventTop + theEventFont.getmetrics()[0], (theCard["gender"] + " " + theCard["event"]).upper(), theEventFont, theEventSpacing)], theMuted[0], theMuted[1])
    _paint_text(theCanvas, [(90, _baseline(theBottom - theResultHeight, theResultHeight, theResultFont), theCard["result"].upper(), theResultFont, theResultSpacing)], theInkColor, 1.0, theSoft)
    return theCanvas


def _ink(theSchool):
    if theSchool["accent"] == "#ffffff":
        return theSchool["primary"]
    return "#111111"


def _rail(theCard, theFiles):
    theSchool = theCard["school"]
    if theSchool["primary"] != "#111111":
        return _rail_card(theCard, theFiles, theSchool["primary"], theSchool["accent"], _ink(theSchool), "dark", 0.15, "#ffffff")
    if theSchool["accent"] != "#ffffff":
        return _rail_card(theCard, theFiles, theSchool["accent"], "#111111", theSchool["accent"], "light", 0.1, "#111111")
    return _rail_card(theCard, theFiles, "#f2f2f3", "#111111", "#ffffff", "light", 0.07, "#111111")


def _blackout(theCard, theFiles):
    theGlow = theCard["school"]["glow"]
    theInk = "#111111"
    if theGlow == "#ffffff":
        theInk = "#0b0b0f"
    return _rail_card(theCard, theFiles, "#0b0b0f", theGlow, theInk, "radial", 0.1, "#ffffff")


def _rotated_layer(theDrawFn, theCenterY, theAngle):
    theMargin = 100
    theLayer = Image.new("RGBA", (theWidth + 2 * theMargin, theHeight), (0, 0, 0, 0))
    theDrawFn(theLayer, theMargin)
    theLayer = theLayer.rotate(theAngle, resample=Image.BICUBIC, center=(theMargin + theWidth / 2.0, theCenterY))
    return theLayer.crop((theMargin, 0, theMargin + theWidth, theHeight))


def _star(theDraw, theCenter, theRadius, theFill):
    thePoints = []
    for n in range(10):
        theAngle = -math.pi / 2 + n * math.pi / 5
        theReach = theRadius
        if n % 2 == 1:
            theReach = theRadius * 0.42
        thePoints.append((theCenter[0] + math.cos(theAngle) * theReach, theCenter[1] + math.sin(theAngle) * theReach))
    theDraw.polygon(thePoints, fill=theFill)


def _stack(theCard, theFiles):
    theSchool = theCard["school"]
    theAccent = _rgb(theSchool["accent"])
    theInkColor = _rgb(_ink(theSchool))
    theCanvas = Image.new("RGB", (theWidth, theHeight), _rgb(theSchool["primary"]))
    _radial_wash(theCanvas, theWhite, (theWidth * 0.5, theHeight * 0.3), (theWidth * 0.8, theHeight * 0.55), 0.18, 0.7)
    _vertical_wash(theCanvas, theBlack, 0.4, 0.55)
    _watermark(theCanvas, theSchool.get("whiteBytes"), 1050, (theWidth / 2.0, theHeight * 0.48), 0.13, 0, False)
    _grain(theCanvas)
    _ti_block(theCanvas, theFiles, 60, 56, theWhite)
    _tag(theCanvas, theFiles, 1020, 56, theAccent, theInkColor, theCard["year"], theCard["cardId"], theWhite, 0.75)
    theLines = _name_lines(theCard)
    theFont, theSpacing, theWide = _fit(theLines, theFiles["fonts"]["oswald700"], 156, 84, -0.02, 960)
    theLineHeight = theFont.size * 0.88
    theItems = []
    for n in range(len(theLines)):
        theLineWidth = _text_width(theFont, theLines[n], theSpacing)
        theItems.append((theWidth / 2.0 - theLineWidth / 2.0, _baseline(250 + n * theLineHeight, theLineHeight, theFont), theLines[n], theFont, theSpacing))
    _paint_text(theCanvas, theItems, theWhite, 1.0, "soft")
    _school_row(theCanvas, theFiles, 250 + len(theLines) * theLineHeight + 28, 60, theSchool["name"].upper(), theAccent, theWhite, 1.0, 90, 3, 22, True)

    def drawShadowBand(theLayer, theMargin):
        ImageDraw.Draw(theLayer).rectangle((theMargin - 40, 642, theMargin + theWidth + 40, 942), fill=(0, 0, 0, int(255 * 0.45)))

    def drawBand(theLayer, theMargin):
        ImageDraw.Draw(theLayer).rectangle((theMargin - 40, 620, theMargin + theWidth + 40, 920), fill=theAccent + (255,))

    def drawBandShadow(theLayer, theMargin):
        ImageDraw.Draw(theLayer).rectangle((theMargin - 40, 640, theMargin + theWidth + 40, 940), fill=(0, 0, 0, int(255 * 0.35)))

    theShadowBand = _rotated_layer(drawShadowBand, 792, 2.5)
    theCanvas.paste(theShadowBand, (0, 0), theShadowBand)
    theDrop = _rotated_layer(drawBandShadow, 790, 2.5).filter(ImageFilter.GaussianBlur(25))
    theCanvas.paste(theDrop, (0, 0), theDrop)
    theBand = _rotated_layer(drawBand, 770, 2.5)
    theCanvas.paste(theBand, (0, 0), theBand)
    theAccLines = _two_lines(theCard["acc1"])
    theAccFont, theAccSpacing, theWide = _fit(theAccLines, theFiles["fonts"]["oswald700"], 126, 64, -0.01, 960)
    theAccHeight = theAccFont.size * 0.86
    theBlockTop = 628 + (290 - len(theAccLines) * theAccHeight) / 2.0

    def drawBandText(theLayer, theMargin):
        theDraw = ImageDraw.Draw(theLayer)
        for n in range(len(theAccLines)):
            theLineWidth = _text_width(theAccFont, theAccLines[n], theAccSpacing)
            theX = theMargin + theWidth / 2.0 - theLineWidth / 2.0
            theBaseline = _baseline(theBlockTop + n * theAccHeight, theAccHeight, theAccFont)
            theCursor = theX
            for i in range(len(theAccLines[n])):
                theDraw.text((theCursor, theBaseline), theAccLines[n][i], fill=theInkColor + (255,), font=theAccFont, anchor="ls")
                theCursor = theCursor + theAccFont.getlength(theAccLines[n][i]) + theAccSpacing

    theText = _rotated_layer(drawBandText, 773, 2.5)
    theCanvas.paste(theText, (0, 0), theText)
    if theCard["acc2"] != "":
        theAcc2 = theCard["acc2"].upper()
        theFont, theSpacing, theTextWidth = _fit([theAcc2], theFiles["fonts"]["oswald700"], 50, 30, 0.06, 960 - 2 * (0.9 * 50 + 2 * 14))
        theStar = theFont.size * 0.45
        theSpace = theFont.getlength(" ") * 2 + theSpacing * 2
        theTotal = theTextWidth + 2 * (theStar * 2 + theSpace)
        theStart = theWidth / 2.0 - theTotal / 2.0
        theBaseline = 958 + theFont.getmetrics()[0]
        theMiddle = theBaseline - theFont.size * 0.36
        theDraw = ImageDraw.Draw(theCanvas)
        _star(theDraw, (theStart + theStar, theMiddle), theStar, theAccent)
        _paint_text(theCanvas, [(theStart + theStar * 2 + theSpace, theBaseline, theAcc2, theFont, theSpacing)], theWhite)
        _star(theDraw, (theStart + theTotal - theStar, theMiddle), theStar, theAccent)
    theBottom = theHeight - 56
    theResultText = theCard["result"].upper()
    theResultFont, theResultSpacing, theResultWidth = _fit([theResultText], theFiles["fonts"]["oswald700"], 196, 100, -0.03, 960)
    theResultHeight = theResultFont.size * 0.9
    theEventText = (theCard["gender"] + " " + theCard["event"]).upper()
    theEventFont, theEventSpacing, theEventWidth = _fit([theEventText], theFiles["fonts"]["mono700"], 30, 18, theMonoSpacing, 960)
    theEventTop = theBottom - theResultHeight - 6 - _normal_height(theEventFont)
    _paint_text(theCanvas, [(theWidth / 2.0 - theEventWidth / 2.0, theEventTop + theEventFont.getmetrics()[0], theEventText, theEventFont, theEventSpacing)], theWhite, 0.9)
    _paint_text(theCanvas, [(theWidth / 2.0 - theResultWidth / 2.0, _baseline(theBottom - theResultHeight, theResultHeight, theResultFont), theResultText, theResultFont, theResultSpacing)], theWhite, 1.0, "soft")
    return theCanvas


thePainters = {"B": _rail, "E": _blackout, "A": _stack}


def paint(theCard, theDesign, theFiles):
    theCanvas = thePainters[theDesign](theCard, theFiles)
    theBuffer = io.BytesIO()
    theCanvas.save(theBuffer, format="PNG", optimize=True)
    return theBuffer.getvalue()
