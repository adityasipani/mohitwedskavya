"""Turn Mohit & Kavya's hand-built invite into the reusable Gulabi Mahal template.

Run again whenever the original card gets a design improvement:
    python3 make_template.py
"""
import re, shutil, pathlib

SRC = pathlib.Path("/home/claude/mohit-kavya-invite.html")
ASSETS_FROM = pathlib.Path("/home/claude/deploy")
T = pathlib.Path(__file__).parent / "templates" / "gulabi-mahal"

s = SRC.read_text()

# 1. details block -> placeholder filled in by build.py
start = s.index("const INVITE = {")
end = s.index("};", start) + 2
s = s[:start] + "const INVITE = /*@@INVITE@@*/;" + s[end:]

# 2. head: build.py writes the real title and share-preview tags
s = re.sub(r"<title>.*?</title>", "<!--@@HEAD@@-->", s, count=1)

def sub(old, new, count=1):
    global s
    if old not in s:
        raise SystemExit(f"Template step failed, text not found: {old[:70]!r}")
    s = s.replace(old, new, count)

# 3. couple-specific text in the page itself
sub('aria-label="Mohit and Kavya at the palace"', 'aria-label="@@COUPLE_ALT@@"', 2)
sub("<p>From Bikaner to Una, every day a new colour</p>", "<p>@@FESTIVITIES_LINE@@</p>")
sub('<p class="small">From the city of havelis, kites and camel caravans</p>', '<p class="small">@@FOOTER_LINE@@</p>')
sub("<p>With love and good wishes from the Sipani and Sharma families</p>", "<p>@@BLESSINGS_LINE@@</p>")
sub('"See you in Bikaner"', '"See you in "+INVITE.city')

# 4. designer credit -> The Royal Patrika House
credit = re.search(r'<div class="credit">.*?</div></div>', s, re.S).group(0)
s = s.replace(credit, "@@CREDIT@@")

# 5. quiz: shared results service, votes kept per invitation
sub('fetch("/api/quiz",{cache:"no-store"})', 'fetch(QAPI,{cache:"no-store"})')
sub('fetch("/api/quiz",{method:"POST"', 'fetch(QAPI,{method:"POST"')
sub("const QRES={", 'const QAPI=INVITE.quizApi+"?site="+encodeURIComponent(INVITE.slug);\nconst QRES={')
tail_at = s.index("const QAPI=")
s = s[:tail_at] + s[tail_at:].replace('"Mohit"', '"groom"').replace('"Kavya"', '"bride"')
s = s.replace('"mk-voter"', '"rph-voter"').replace('"mk-quiz2"', 'INVITE.slug+"-quiz"')

left = [m.start() for m in re.finditer(r"Mohit|Kavya|Sipani|Bikaner", s)]
if left:
    raise SystemExit("Still couple-specific text at: " + ", ".join(repr(s[i-30:i+30]) for i in left[:5]))

# personal guest name on the envelope: add ?to=Sharma%20Family to the link
sub('<p class="fe-tap"><span>Tap to open</span></p>', '<p class="fe-tap"><span>Tap to open</span></p><p class="fe-guest" id="feGuest" hidden></p>')
sub('.fe-tap{', '.fe-guest{position:absolute;left:0;right:0;top:calc(50% + clamp(160px,43vw,210px));z-index:8;margin:0;text-align:center;font-family:"Cormorant Garamond",Georgia,serif;font-style:italic;font-size:1.05rem;color:#74402F;transition:opacity .4s ease}#intro.open .fe-guest{opacity:0}\n.fe-tap{')
sub('$("envCity").textContent=INVITE.venueLine.toUpperCase();', '$("envCity").textContent=INVITE.venueLine.toUpperCase();(function(){try{const g=(new URLSearchParams(location.search).get("to")||"").replace(/[<>]/g,"").trim().slice(0,60);if(g){const el=$("feGuest");el.textContent="Specially for "+g;el.hidden=false;}}catch(e){}})();')

# hidden logo slots: no file unless the client has a monogram logo
s = s.replace(' src="logo-mk.webp"', '')

# 6. full document shell, the same way the live card is published
i = s.index("</style>") + len("</style>")
shell = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
         '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
         '<meta name="theme-color" content="#F8E4E2">\n<meta name="robots" content="noindex, nofollow">\n'
         '<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
         'body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n')
s = shell + s[:i] + "\n</head>\n<body>\n" + s[i:].lstrip("\n")
if "</html>" not in s[-200:]:
    s += "\n</body>\n</html>\n"

T.mkdir(parents=True, exist_ok=True)
(T / "template.html").write_text(s)

# shared artwork for this design (never the couple's own photos, logo or song)
keep = ["hero.webp", "fountain.webp", "footer-scene.webp", "couple-poster.webp", "couple.mp4",
        "couple-hd-poster.webp", "couple-hd-poster-blur.webp", "couple-hd.mp4"]
for scene in ["sangeet", "carnival", "mayra", "reception", "wedding"]:
    keep += [p.name for p in ASSETS_FROM.glob(f"{scene}*") if p.suffix in (".webp", ".mp4")]
for name in sorted(set(keep)):
    shutil.copy2(ASSETS_FROM / name, T / "assets" / name)
print("template.html", len(s), "bytes;", len(set(keep)), "assets")
