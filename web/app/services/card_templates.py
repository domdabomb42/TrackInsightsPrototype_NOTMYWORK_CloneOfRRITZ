"""The two athlete card designs, Poster B (left rail) and Poster E (blackout).

Ported from the approved prototype. The HTML is the design, so the markup and
inline styles stay as they were; only the asset URLs come in from outside.

Card dict keys:
  name, school (name, primary, accent, logo, logoWhite), gender, event,
  result, tier, acc1, acc2, cardId, year
Assets dict keys:
  tiLogo, fonts (oswald500, oswald700, mono400, mono700)
"""

theFont = "font-family:Oswald,'Arial Narrow',sans-serif;"

theGrain = (
    '<svg aria-hidden="true" style="position:absolute;inset:0;width:100%;height:100%;opacity:0.14;'
    'mix-blend-mode:overlay;pointer-events:none" xmlns="http://www.w3.org/2000/svg"><filter id="g">'
    '<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch"></feTurbulence>'
    '<feColorMatrix type="saturate" values="0"></feColorMatrix></filter>'
    '<rect width="100%" height="100%" filter="url(#g)"></rect></svg>'
)

theDesignNames = {"B": "School Color", "E": "Blackout", "A": "Centered"}

theFitScript = (
    "<script>(function(){function fit(){var els=document.querySelectorAll('[data-fit]');"
    "for(var i=0;i<els.length;i++){var el=els[i];var min=parseInt(el.getAttribute('data-fit'),10)||24;"
    "var size=parseFloat(el.getAttribute('data-size'))||parseFloat(getComputedStyle(el).fontSize);"
    "el.style.fontSize=size+'px';var limit=el.parentNode.clientWidth;"
    "var guard=0;while(el.scrollWidth>limit&&size>min&&guard<80){size=size-2;el.style.fontSize=size+'px';guard++;}}}"
    "window.fitCardText=fit;if(document.fonts&&document.fonts.ready){document.fonts.ready.then(fit);}else{fit();}"
    "window.addEventListener('load',fit);})();</script>"
)


def fontCss(fonts):
    return (
        "@font-face{font-family:'Oswald';font-weight:500;src:url('" + fonts["oswald500"] + "') format('woff2')}"
        "@font-face{font-family:'Oswald';font-weight:700;src:url('" + fonts["oswald700"] + "') format('woff2')}"
        "@font-face{font-family:'Space Mono';font-weight:400;src:url('" + fonts["mono400"] + "') format('woff2')}"
        "@font-face{font-family:'Space Mono';font-weight:700;src:url('" + fonts["mono700"] + "') format('woff2')}"
        "body{margin:0;background:#000}"
    )


def ink(school):
    if school["accent"] == "#ffffff":
        return school["primary"]
    return "#111111"


def mono(size, extra=""):
    return "font-family:'Space Mono',monospace;font-size:" + str(size) + "px;letter-spacing:0.14em;" + extra


def escape(text):
    theText = str(text)
    theText = theText.replace("&", "&amp;")
    theText = theText.replace("<", "&lt;")
    theText = theText.replace(">", "&gt;")
    theText = theText.replace('"', "&quot;")
    return theText


def twoLines(text):
    theParts = text.split(" ", 1)
    if len(theParts) == 1:
        return escape(text)
    return escape(theParts[0]) + "<br>" + escape(theParts[1])


def oneLineSize(text, big, small):
    if len(text) <= 15:
        return big
    return small


def tiBlock(assets, size=110):
    return (
        '<div style="display:flex;align-items:center;gap:18px"><img src="' + assets["tiLogo"] + '" alt="Track Insights" '
        'style="width:' + str(size) + "px;height:" + str(size) + "px;border-radius:" + str(int(size * 0.18)) + 'px">'
        '<div style="font-size:' + str(int(size * 0.4)) + 'px;font-weight:700;line-height:0.95;color:#ffffff">Track<br>Insights</div></div>'
    )


def yearTag(school, year, theId):
    return (
        '<div style="display:flex;flex-direction:column;align-items:flex-end"><div style="background:' + school["accent"]
        + ";color:" + ink(school) + ";" + mono(26, "font-weight:700;padding:14px 22px 10px;line-height:1") + '">' + str(year) + "</div>"
        '<div style="' + mono(16, "margin-top:10px;text-align:right;color:rgba(255,255,255,0.75)") + '">' + escape(theId) + "</div></div>"
    )


def wrap(assets, inner):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><style>' + fontCss(assets["fonts"])
        + "</style></head><body>" + inner + theFitScript + "</body></html>"
    )


def fitAttrs(size, minimum):
    return 'data-fit="' + str(minimum) + '" data-size="' + str(size) + '"'


def nameLines(c):
    theFirst = (c.get("first") or "").strip()
    theLast = (c.get("last") or "").strip()
    if theFirst != "" and theLast != "":
        return escape(theFirst) + "<br>" + escape(theLast)
    return twoLines(c["name"])


def whiteLogo(school, style):
    if school.get("logoWhite") is None:
        return ""
    return '<img src="' + school["logoWhite"] + '" alt="" aria-hidden="true" style="' + style + '">'


def logoChip(school):
    if school.get("logo") is None:
        return ""
    return (
        '<div style="width:110px;height:110px;flex-shrink:0;background:#ffffff;border-radius:16px;display:flex;align-items:center;'
        'justify-content:center;margin-bottom:10px"><img src="' + school["logo"] + '" alt="" style="max-height:84px;max-width:84px;width:auto;height:auto"></div>'
    )


def designRail(c, assets):
    s = c["school"]
    theAccent = s["accent"]
    theAcc2 = ""
    if c["acc2"] != "":
        theAcc2 = '<div ' + fitAttrs(62, 36) + ' style="margin-top:16px;font-size:62px;font-weight:700;letter-spacing:0.04em;color:#ffffff;white-space:nowrap">' + escape(c["acc2"]) + "</div>"
    return (
        '<div style="width:1080px;height:1350px;position:relative;overflow:hidden;background:' + s["primary"] + ";" + theFont + 'color:#ffffff;text-transform:uppercase">'
        '<div style="position:absolute;inset:0;background:linear-gradient(90deg,rgba(0,0,0,0.45) 0%,rgba(0,0,0,0) 55%),linear-gradient(180deg,rgba(0,0,0,0) 50%,rgba(0,0,0,0.5) 100%)"></div>'
        + whiteLogo(s, "position:absolute;right:-380px;top:120px;width:1250px;height:auto;opacity:0.15;transform:rotate(-8deg);filter:blur(2px)")
        + theGrain
        + '<div style="position:absolute;left:0;top:0;bottom:0;width:30px;background:' + theAccent + '"></div>'
        '<div style="position:absolute;top:56px;left:90px;right:60px;display:flex;align-items:flex-start;justify-content:space-between">' + tiBlock(assets) + yearTag(s, c["year"], c["cardId"]) + "</div>"
        '<div style="position:absolute;left:90px;right:60px;top:280px">'
        '<div ' + fitAttrs(170, 90) + ' style="font-size:170px;font-weight:700;line-height:0.86;letter-spacing:-0.025em;text-shadow:0 10px 30px rgba(0,0,0,0.35);white-space:nowrap">' + nameLines(c) + "</div>"
        '<div style="display:flex;align-items:center;gap:20px;margin-top:26px"><div style="height:4px;width:70px;background:' + theAccent + ';flex-shrink:0"></div><div style="min-width:0;flex:1"><div ' + fitAttrs(28, 16) + ' style="' + mono(28, "font-weight:700;color:rgba(255,255,255,0.92);white-space:nowrap") + '">' + escape(s["name"]) + "</div></div></div></div>"
        '<div style="position:absolute;left:90px;right:60px;top:690px">'
        '<div ' + fitAttrs(124, 64) + ' style="font-size:124px;font-weight:700;line-height:0.88;letter-spacing:-0.01em;color:' + theAccent + ';text-shadow:0 6px 0 rgba(0,0,0,0.3);white-space:nowrap">' + twoLines(c["acc1"]) + "</div>"
        + theAcc2 + "</div>"
        '<div style="position:absolute;left:90px;right:60px;bottom:64px;display:flex;align-items:flex-end;justify-content:space-between;gap:30px">'
        '<div style="min-width:0;flex:1"><div ' + fitAttrs(30, 18) + ' style="' + mono(30, "font-weight:700;color:rgba(255,255,255,0.9);white-space:nowrap") + '">' + escape(c["gender"]) + " " + escape(c["event"]) + "</div>"
        '<div ' + fitAttrs(200, 100) + ' style="font-size:200px;font-weight:700;line-height:0.86;letter-spacing:-0.035em;margin-top:8px;text-shadow:0 10px 30px rgba(0,0,0,0.4);white-space:nowrap">' + escape(c["result"]) + "</div></div>"
        + logoChip(s) + "</div>"
        "</div>"
    )


def designBlackout(c, assets):
    s = c["school"]
    theBlock = s["primary"]
    theBlockInk = "#ffffff"
    theHot = s["accent"]
    if s["primary"] == "#111111":
        theBlock = s["accent"]
        theBlockInk = "#111111"
    if s["accent"] == "#ffffff":
        theHot = "#ff4d6d"
    theAcc2 = ""
    if c["acc2"] != "":
        theAcc2 = '<div style="position:absolute;left:60px;right:60px;top:860px;text-align:center"><div ' + fitAttrs(56, 32) + ' style="font-size:56px;font-weight:700;letter-spacing:0.06em;color:' + theHot + ';white-space:nowrap">' + escape(c["acc2"]) + "</div></div>"
    return (
        '<div style="width:1080px;height:1350px;position:relative;overflow:hidden;background:#0b0b0f;' + theFont + 'color:#ffffff;text-transform:uppercase">'
        '<div style="position:absolute;inset:0;background:radial-gradient(ellipse 90% 60% at 50% 20%,rgba(255,255,255,0.10) 0%,rgba(255,255,255,0) 70%)"></div>'
        + whiteLogo(s, "position:absolute;left:50%;top:52%;width:1100px;height:auto;transform:translate(-50%,-50%) rotate(-8deg);opacity:0.09;filter:blur(2px)")
        + theGrain
        + '<div style="position:absolute;left:0;right:0;top:0;height:26px;background:' + theBlock + '"></div>'
        '<div style="position:absolute;left:0;right:0;top:26px;height:6px;background:' + theHot + '"></div>'
        '<div style="position:absolute;top:80px;left:60px;right:60px;display:flex;align-items:flex-start;justify-content:space-between">' + tiBlock(assets) + yearTag(s, c["year"], c["cardId"]) + "</div>"
        '<div style="position:absolute;left:60px;right:60px;top:290px;text-align:center">'
        '<div ' + fitAttrs(156, 84) + ' style="font-size:156px;font-weight:700;line-height:0.88;letter-spacing:-0.02em;white-space:nowrap">' + nameLines(c) + "</div>"
        '<div ' + fitAttrs(28, 16) + ' style="' + mono(28, "font-weight:700;margin-top:26px;color:rgba(255,255,255,0.8);white-space:nowrap") + '">' + escape(s["name"]) + "</div></div>"
        '<div style="position:absolute;left:60px;right:60px;top:650px;background:' + theBlock + ";color:" + theBlockInk + ';padding:34px 30px 30px;text-align:center;box-shadow:0 20px 50px rgba(0,0,0,0.6)">'
        '<div ' + fitAttrs(oneLineSize(c["acc1"], 110, 92), 56) + ' style="font-size:' + str(oneLineSize(c["acc1"], 110, 92)) + 'px;font-weight:700;line-height:0.9;letter-spacing:-0.01em;white-space:nowrap">' + escape(c["acc1"]) + "</div></div>"
        + theAcc2
        + '<div style="position:absolute;left:60px;right:60px;bottom:70px;text-align:center">'
        '<div ' + fitAttrs(30, 18) + ' style="' + mono(30, "font-weight:700;color:rgba(255,255,255,0.8);white-space:nowrap") + '">' + escape(c["gender"]) + " " + escape(c["event"]) + "</div>"
        '<div ' + fitAttrs(200, 100) + ' style="font-size:200px;font-weight:700;line-height:0.9;letter-spacing:-0.03em;margin-top:6px;color:' + theHot + ';white-space:nowrap">' + escape(c["result"]) + "</div></div>"
        "</div>"
    )


def designStack(c, assets):
    s = c["school"]
    theAccent = s["accent"]
    theInk = ink(s)
    theAcc2 = ""
    if c["acc2"] != "":
        theAcc2 = (
            '<div style="position:absolute;left:60px;right:60px;top:958px;text-align:center"><div ' + fitAttrs(50, 30) + ' style="font-size:50px;font-weight:700;letter-spacing:0.06em;color:#ffffff;white-space:nowrap">'
            '<span style="color:' + theAccent + '">&#9733;</span>&nbsp; ' + escape(c["acc2"]) + ' &nbsp;<span style="color:' + theAccent + '">&#9733;</span></div></div>'
        )
    return (
        '<div style="width:1080px;height:1350px;position:relative;overflow:hidden;background:' + s["primary"] + ";" + theFont + 'color:#ffffff;text-transform:uppercase">'
        '<div style="position:absolute;inset:0;background:radial-gradient(ellipse 80% 55% at 50% 30%,rgba(255,255,255,0.18) 0%,rgba(255,255,255,0) 70%),linear-gradient(180deg,rgba(0,0,0,0) 40%,rgba(0,0,0,0.55) 100%)"></div>'
        + whiteLogo(s, "position:absolute;left:50%;top:48%;width:1050px;height:auto;transform:translate(-50%,-50%);opacity:0.13;filter:blur(2px)")
        + theGrain
        + '<div style="position:absolute;top:56px;left:60px;right:60px;display:flex;align-items:flex-start;justify-content:space-between">' + tiBlock(assets) + yearTag(s, c["year"], c["cardId"]) + "</div>"
        '<div style="position:absolute;left:60px;right:60px;top:250px;text-align:center">'
        '<div ' + fitAttrs(156, 84) + ' style="font-size:156px;font-weight:700;line-height:0.88;letter-spacing:-0.02em;text-shadow:0 10px 30px rgba(0,0,0,0.35);white-space:nowrap">' + nameLines(c) + "</div>"
        '<div style="display:flex;align-items:center;justify-content:center;gap:22px;margin-top:28px">'
        '<div style="height:3px;width:90px;background:' + theAccent + ';flex-shrink:0"></div>'
        '<div style="min-width:0;max-width:700px"><div ' + fitAttrs(28, 16) + ' style="' + mono(28, "font-weight:700;white-space:nowrap") + '">' + escape(s["name"]) + "</div></div>"
        '<div style="height:3px;width:90px;background:' + theAccent + ';flex-shrink:0"></div></div></div>'
        '<div style="position:absolute;left:-300px;top:-200px;width:260px;height:1500px;background:linear-gradient(90deg,rgba(255,255,255,0) 0%,rgba(255,255,255,0.22) 50%,rgba(255,255,255,0) 100%);transform:rotate(24deg) translateX(900px);filter:blur(10px)"></div>'
        '<div style="position:absolute;left:-40px;right:-40px;top:642px;height:300px;background:rgba(0,0,0,0.45);transform:rotate(-2.5deg)"></div>'
        '<div style="position:absolute;left:-40px;right:-40px;top:620px;height:300px;background:' + theAccent + ';transform:rotate(-2.5deg);box-shadow:0 20px 50px rgba(0,0,0,0.35)"></div>'
        '<div style="position:absolute;left:0;right:0;top:628px;height:290px;display:flex;align-items:center;justify-content:center;text-align:center;transform:rotate(-2.5deg)">'
        '<div style="width:960px"><div ' + fitAttrs(126, 64) + ' style="font-size:126px;font-weight:700;line-height:0.86;letter-spacing:-0.01em;color:' + theInk + ';white-space:nowrap">' + twoLines(c["acc1"]) + "</div></div></div>"
        + theAcc2
        + '<div style="position:absolute;left:60px;right:60px;bottom:56px;text-align:center">'
        '<div ' + fitAttrs(30, 18) + ' style="' + mono(30, "font-weight:700;color:rgba(255,255,255,0.9);white-space:nowrap") + '">' + escape(c["gender"]) + " " + escape(c["event"]) + "</div>"
        '<div ' + fitAttrs(196, 100) + ' style="font-size:196px;font-weight:700;line-height:0.9;letter-spacing:-0.03em;margin-top:6px;text-shadow:0 10px 30px rgba(0,0,0,0.4);white-space:nowrap">' + escape(c["result"]) + "</div></div>"
        "</div>"
    )


theDesigns = {"B": designRail, "E": designBlackout, "A": designStack}


def cardHtml(design, c, assets):
    return wrap(assets, theDesigns[design](c, assets))
