"""Build one client's invitation website from their details file.

    python3 build.py rahul-weds-riya

Reads   clients/<slug>/details.json  (+ photos/, optional song and logo in the same folder)
Writes  out/<slug>/                  a complete site, ready to upload
"""
import json, re, shutil, sys, html, pathlib, asyncio
from datetime import datetime
from PIL import Image, ImageOps

ROOT = pathlib.Path(__file__).parent
RPH_SITE = "https://theroyalpatrikahouse.pages.dev"
QUIZ_API = RPH_SITE + "/api/quiz"
RPH_INSTAGRAM = "https://instagram.com/theroyalpatrikahouse"

# Artwork that ships with each design, by function type.
SCENES = {
    "gulabi-mahal": {
        "sangeet":   {"image": "sangeet-poster.webp", "video": "sangeet.mp4", "twirl": True},
        "carnival":  {"image": "carnival-poster.webp", "video": "carnival.mp4"},
        "mayra":     {"image": "mayra.webp"},
        "reception": {"image": "reception-poster.webp", "video": "reception.mp4"},
        "wedding":   {"image": "wedding-poster.webp", "video": "wedding.mp4"},
    }
}
# Functions we don't have dedicated art for yet borrow the closest scene.
ALIASES = {"haldi": "mayra", "mehendi": "carnival", "mehndi": "carnival", "tilak": "mayra", "bhaat": "mayra",
           "cocktail": "reception", "engagement": "reception", "ring ceremony": "reception", "phere": "wedding",
           "pheras": "wedding", "shubh vivah": "wedding", "vivah": "wedding", "baraat": "wedding", "garba": "sangeet"}

DEFAULTS = {
    "blessingLine": "॥ श्री गणेशाय नमः ॥",
    "heroImage": "hero.webp", "heroMode": "video",
    "music": "", "logo": "",
    "quiz": [{"q": "Who will get emotional first?", "answer": ""},
             {"q": "Who takes longer to get ready?", "answer": ""},
             {"q": "Who hits the dance floor first?", "answer": ""},
             {"q": "Who said “I love you” first?", "answer": ""}],
    "blessings": [], "contacts": [], "credit": True,
}

esc = lambda s: html.escape(str(s), quote=True)


def fail(msg):
    raise SystemExit("✗ " + msg)


def load(slug):
    folder = ROOT / "clients" / slug
    f = folder / "details.json"
    if not f.exists():
        fail(f"{f} not found")
    d = {**DEFAULTS, **json.loads(f.read_text())}
    d["slug"] = slug
    for k in ["groom", "bride", "city", "dates", "countdownTo", "events", "manuhar", "groomFamily", "brideFamily"]:
        if not d.get(k):
            fail(f"details.json is missing '{k}'")
    d.setdefault("design", "gulabi-mahal")
    d.setdefault("venueLine", d["city"])
    d.setdefault("festivitiesLine", "Every day, a new colour")
    d.setdefault("blessingsLine", "With love and good wishes from both our families")
    d.setdefault("footerLine", f"See you in {d['city']}")
    try:
        datetime.fromisoformat(d["countdownTo"])
    except ValueError:
        fail("countdownTo must look like 2027-02-16T19:00:00+05:30")
    return folder, d


def resolve_events(d):
    lib = SCENES[d["design"]]
    maps = {}
    for i, e in enumerate(d["events"]):
        for k in ["name", "date", "time", "where"]:
            if not e.get(k):
                fail(f"event {i + 1} is missing '{k}'")
        if not re.fullmatch(r"\d{1,2} [A-Z][a-z]{2} \d{4}", e["date"]):
            fail(f"event '{e['name']}': date must look like 14 Feb 2027")
        want = (e.get("scene") or e["name"]).lower()
        scene = want if want in lib else ALIASES.get(want, "wedding")
        e["scene"] = scene
        for k, v in lib[scene].items():
            e.setdefault(k, v)
        e.setdefault("day", f"DAY {i + 1}")
        e.setdefault("tagline", "")
        e.setdefault("men", "")
        e.setdefault("women", "")
        e.setdefault("palette", [])
        if e.get("map"):
            maps.setdefault(e["where"].split(",")[0], {"name": e["where"], "url": e.pop("map")})
    d["maps"] = list(maps.values())


def photos(folder, out, d):
    src = sorted(p for p in (folder / "photos").glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".heic")) if (folder / "photos").exists() else []
    names = []
    for i, p in enumerate(src, 1):
        im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
        base = f"gallery-{i}"
        for suffix, h in [("lg", 1800), ("md", 1300), ("sm", 800), ("th", 220)]:
            w = round(im.width * h / im.height)
            (im.resize((w, h), Image.LANCZOS) if im.height > h else im).save(out / f"{base}-{suffix}.webp", quality=82 if suffix != "th" else 70)
        names.append(base)
    d["gallery"] = names


def credit_html(d):
    if not d.get("credit", True):
        return ""
    return (f'<div class="credit"><div class="wrap cr-row"><p class="cr-text">Designed by <span class="cr-n">The Royal Patrika House</span></p>'
            f'<div class="cr-icons"><a class="cr-ic" href="{RPH_INSTAGRAM}" target="_blank" rel="noopener" aria-label="The Royal Patrika House on Instagram">'
            '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="1.6"/>'
            '<circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="17.5" cy="6.5" r="1.1" fill="currentColor"/></svg></a>'
            f'<a class="cr-ic" href="{RPH_SITE}" target="_blank" rel="noopener" aria-label="The Royal Patrika House website">'
            '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.6"/>'
            '<path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3Z" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></a>'
            '</div></div></div>')


async def render_og(out, d):
    from playwright.async_api import async_playwright
    days, month = d["dates"]["days"], d["dates"]["month"]
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
    @font-face{{font-family:Pag;src:url(file:///usr/share/texmf/fonts/opentype/public/tex-gyre/texgyrepagella-regular.otf)}}
    @font-face{{font-family:PagI;src:url(file:///usr/share/texmf/fonts/opentype/public/tex-gyre/texgyrepagella-italic.otf)}}
    body{{margin:0;width:1200px;height:630px;overflow:hidden;background:linear-gradient(90deg,#FBEFEA 0 52%,#F4E1DA);font-family:Pag;position:relative}}
    .art{{position:absolute;right:0;top:0;width:640px;height:630px;background:url(couple-hd-poster.webp) center 40%/cover;-webkit-mask:linear-gradient(90deg,transparent,#000 22%)}}
    .t{{position:absolute;left:60px;top:0;bottom:0;width:560px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}}
    .n{{font:italic 86px/1.05 PagI;color:#9C5464}}.n i{{color:#C29A5B;font-size:64px;margin:0 10px}}
    .r{{width:300px;height:1px;background:#C9A066;margin:26px auto 22px;position:relative}}
    .c{{font:30px Pag;letter-spacing:.32em;color:#8E6A5A;text-transform:uppercase}}.d{{font:italic 36px PagI;color:#9C5464;margin-top:12px}}
    .b{{position:absolute;inset:16px;border:1.5px solid #D9B98A;border-radius:6px}}
    </style></head><body><div class="art"></div><div class="b"></div><div class="t">
    <div class="n">{esc(d['groom'])} <i>&amp;</i> {esc(d['bride'])}</div><div class="r"></div>
    <div class="c">{esc(d['venueLine'])}</div><div class="d">{esc(days)} {esc(month)}</div></div></body></html>"""
    tmp = out / "_og.html"
    tmp.write_text(page)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1200, "height": 630})
        await pg.goto(tmp.as_uri())
        await pg.wait_for_timeout(500)
        await pg.screenshot(path=str(out / "og.png"))
        await b.close()
    Image.open(out / "og.png").convert("RGB").save(out / "og.jpg", quality=86)
    (out / "og.png").unlink()
    tmp.unlink()


def build(slug):
    folder, d = load(slug)
    resolve_events(d)
    tdir = ROOT / "templates" / d["design"]
    out = ROOT / "out" / slug
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # artwork: shared design files the page uses
    needed = {"hero.webp", "fountain.webp", "footer-scene.webp", "couple-poster.webp", "couple.mp4",
              "couple-hd-poster.webp", "couple-hd-poster-blur.webp", "couple-hd.mp4"}
    for e in d["events"]:
        for k in ("image", "video"):
            if e.get(k):
                needed.add(e[k])
                if k == "image":
                    needed.add(re.sub(r"\.webp$", "-blur.webp", e[k]))
    for n in needed:
        src = tdir / "assets" / n
        if src.exists():
            shutil.copy2(src, out / n)

    photos(folder, out, d)
    for k in ("music", "logo"):
        if d.get(k):
            src = folder / d[k]
            if not src.exists():
                fail(f"{k} file {d[k]} not found in the client folder")
            shutil.copy2(src, out / src.name)
            d[k] = src.name

    url = f"https://{d['domain']}" if d.get("domain") else f"https://{slug}.pages.dev"
    invite = {k: d[k] for k in ["groom", "bride", "blessingLine", "city", "venueLine", "maps", "heroImage", "heroMode",
                                "music", "dates", "countdownTo", "logo", "manuhar", "groomFamily", "brideFamily",
                                "events", "quiz", "blessings", "gallery", "contacts"]}
    invite["venue"] = d["events"][0]["where"]
    invite["slug"] = slug
    invite["quizApi"] = QUIZ_API

    title = f"{d['groom']} & {d['bride']} — Wedding Invitation"
    desc = d.get("shareText") or f"With love, {d['groom']} & {d['bride']} invite you to celebrate their wedding. {d['dates']['days']} {d['dates']['month']} · {d['venueLine']}."
    head = (f"<title>{esc(title)}</title>\n<meta name=\"description\" content=\"{esc(desc)}\">\n"
            f"<meta property=\"og:type\" content=\"website\">\n<meta property=\"og:url\" content=\"{url}/\">\n"
            f"<meta property=\"og:title\" content=\"{esc(title)}\">\n<meta property=\"og:description\" content=\"{esc(desc)}\">\n"
            f"<meta property=\"og:image\" content=\"{url}/og.jpg\">\n<meta property=\"og:image:width\" content=\"1200\">\n"
            f"<meta property=\"og:image:height\" content=\"630\">\n<meta name=\"twitter:card\" content=\"summary_large_image\">\n"
            "<link rel=\"preload\" as=\"image\" href=\"couple-hd-poster.webp\" fetchpriority=\"high\">")

    page = (tdir / "template.html").read_text()
    js = json.dumps(invite, ensure_ascii=False, indent=1).replace("</", "<\\/")
    for key, val in {"/*@@INVITE@@*/": js, "<!--@@HEAD@@-->": head, "@@CREDIT@@": credit_html(d),
                     "@@COUPLE_ALT@@": esc(f"{d['groom']} and {d['bride']} at the palace"),
                     "@@FESTIVITIES_LINE@@": esc(d["festivitiesLine"]), "@@BLESSINGS_LINE@@": esc(d["blessingsLine"]),
                     "@@FOOTER_LINE@@": esc(d["footerLine"])}.items():
        if key not in page:
            fail(f"template is missing {key}; run make_template.py")
        page = page.replace(key, val)
    if "@@" in page:
        fail("an @@placeholder@@ was left unfilled")
    (out / "index.html").write_text(page)
    (out / "_headers").write_text("/*.webp\n  Cache-Control: public, max-age=2592000\n/*.mp4\n  Cache-Control: public, max-age=2592000\n")

    shutil.copy2(tdir / "assets" / "couple-hd-poster.webp", out / "couple-hd-poster.webp")
    asyncio.run(render_og(out, d))
    size = sum(p.stat().st_size for p in out.iterdir()) / 1e6
    print(f"✓ {slug}: {len(d['events'])} functions, {len(d['gallery'])} photos, {size:.1f} MB → {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        fail("usage: python3 build.py <client-slug>")
    build(sys.argv[1])
