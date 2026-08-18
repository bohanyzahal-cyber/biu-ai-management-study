#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""בונה את חוברת-לבחינה.html — חוברת מודפסת אחת לקלסר הבחינה.

מקורות (לא נערכים כאן — עורכים אותם ומריצים שוב):
  דף-עזר-להדפסה.html   → סעיף "שליפה מהירה"
  מילון-מושגים.html    → משפטי זיהוי · מילון א־ת · זוגות · דפוסים
  פקודות-ומבנים.html   → סעיף פקודות
  מדריך-למידה.html     → סעיף מדריך הלמידה
  הדפסת-שאלות.html     → כל בנקי השאלות (DATA)

הרצה:  python build_booklet.py
"""
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "חוברת-לבחינה.html"
TEMPLATE = ROOT / "booklet_template.html"

SRC_CHEAT = ROOT / "דף-עזר-להדפסה.html"
SRC_GLOSS = ROOT / "מילון-מושגים.html"
SRC_CMDS = ROOT / "פקודות-ומבנים.html"
SRC_GUIDE = ROOT / "מדריך-למידה.html"
SRC_QUEST = ROOT / "הדפסת-שאלות.html"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def attr(s: str, limit: int = 0) -> str:
    s = strip_tags(s)
    if limit and len(s) > limit:
        s = s[: limit - 1].rstrip() + "…"
    return html.escape(s, quote=True)


def wrap_b(inner: str, cls: str = "", t: str = "", h: str = "", x: bool = False,
           keep: bool = False) -> str:
    a = []
    if t:
        a.append(f'data-t="{t}"')
    if h:
        a.append(f'data-h="{h}"')
    if x:
        a.append('data-x="1"')
    if keep:
        a.append('data-keep="1"')
    c = f"b {cls}".strip()
    return f'<div class="{c}" {" ".join(a)}>{inner}</div>\n'


TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)((?:\"[^\"]*\"|'[^']*'|[^>\"'])*)>")
TOP_TAGS = {"h1", "h2", "h3", "h4", "p", "div", "pre", "table", "ul", "ol",
            "blockquote", "hr", "section", "article"}
VOID = {"hr", "br", "img", "meta", "input", "link"}


def split_top(src: str):
    """מפצל HTML שטוח לאלמנטים עליונים (עוקב אחרי קינון של אותו תג)."""
    out, i, n = [], 0, len(src)
    while i < n:
        m = TAG_RE.search(src, i)
        if not m:
            break
        tag = m.group(2).lower()
        if m.group(1) == "/" or tag not in TOP_TAGS:
            i = m.end()
            continue
        if tag in VOID:
            out.append(src[m.start(): m.end()])
            i = m.end()
            continue
        depth, j = 0, m.end()
        for mm in TAG_RE.finditer(src, m.start()):
            if mm.group(2).lower() != tag:
                continue
            depth += -1 if mm.group(1) == "/" else 1
            if depth == 0:
                j = mm.end()
                break
        out.append(src[m.start(): j])
        i = j
    return out


def chunk_table(tbl: str, max_rows: int = 12):
    """מפצל טבלה ארוכה לכמה טבלאות עם אותה כותרת — כדי שכל חלק ייכנס בטור."""
    m = re.match(r"(?s)\s*(<table[^>]*>)(.*)</table>\s*$", tbl)
    if not m:
        return [tbl]
    open_tag, body = m.group(1), m.group(2)
    thead_m = re.search(r"(?s)<thead>.*?</thead>", body)
    thead = thead_m.group(0) if thead_m else ""
    rest = body.replace(thead, "")
    rows = re.findall(r"(?s)<tr[^>]*>.*?</tr>", rest)
    if len(rows) <= max_rows:
        return [tbl]
    chunks = []
    for k in range(0, len(rows), max_rows):
        part = "".join(rows[k: k + max_rows])
        chunks.append(f"{open_tag}{thead}<tbody>{part}</tbody></table>")
    return chunks


# ───────────────────────── דף עזר (שליפה מהירה) ─────────────────────────

def extract_cheat() -> str:
    src = read(SRC_CHEAT)
    blocks = []
    for blk in re.findall(r'(?s)<div class="blk">.*?</ul></div></div>', src):
        title_m = re.search(r"(?s)<h2>(.*?)</h2>", blk)
        title = attr(title_m.group(1), 26) if title_m else ""
        blocks.append(wrap_b(blk, "cheat", t=title, h=title, x=True))
    grid_m = re.search(r'(?s)<div class="grid2">(.*?)</div>\s*<table', src)
    tables = re.findall(r"(?s)<table>.*?</table>", grid_m.group(1)) if grid_m else []
    blocks.append(wrap_b("<h4 class=subh>⚡ טבלאות שליפה — סדרים · רשימות · מספרים · הבחנות</h4>",
                         "", t="טבלאות שליפה", h="טבלאות שליפה", x=True, keep=True))
    for t in tables:
        blocks.append(wrap_b(t, "cheattbl", h="טבלאות שליפה"))
    tail_m = re.search(r'(?s)(<table><tr><td style="text-align:center.*?</table>)', src)
    if tail_m:
        blocks.append(wrap_b(tail_m.group(1), "cheattbl", h="עקרון-על"))
    return "".join(blocks)


# ───────────────────────── מילון: 4 הפאנלים ─────────────────────────

def _panel_line(src: str, marker: str) -> str:
    for line in src.splitlines():
        if marker in line:
            return re.sub(r'\sdata-s="[^"]*"', "", line)
    raise SystemExit(f"פאנל לא נמצא: {marker}")


def _term_of(article: str) -> str:
    m = re.search(r"(?s)<h3>(.*?)</h3>", article)
    if not m:
        return ""
    sp = re.search(r"<span class=(?:he|en)>(.*?)</span>", m.group(1))
    return attr(sp.group(1) if sp else m.group(1), 26)


def extract_glossary() -> str:
    line = _panel_line(read(SRC_GLOSS), '<div class="panel panel-glossary"')
    start = line.find("<div class=letter")
    inner = line[start:]
    if inner.endswith("</div>"):
        inner = inner[: -len("</div>")]
    tokens = re.split(r"(?=<div class=letter )|(?=<article )", inner)
    blocks, n_items = [], 0
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        if tok.startswith("<div class=letter"):
            m = re.search(r'(?s)id="L([^"]+)">(.*?)</div>', tok)
            letter = html.escape(m.group(1)) if m else "?"
            blocks.append(wrap_b(f"<div class=lhead><span>{letter}</span></div>",
                                 "", t=letter, x=True, keep=True))
        elif tok.startswith("<article"):
            n_items += 1
            tok = tok.replace('<article class="item t"', '<article class="item"', 1)
            blocks.append(wrap_b(tok, "gitem", t=_term_of(tok)))
    print(f"  מילון: {n_items} מושגים")
    return "".join(blocks)


def extract_chapters() -> str:
    line = _panel_line(read(SRC_GLOSS), '<div class="panel panel-chapters')
    blocks, n_items = [], 0
    for lec, body in re.findall(r'(?s)<section class=chap data-l="([^"]+)">(.*?)</section>', line):
        h2 = re.search(r"(?s)<h2>(.*?)</h2>", body)
        label = f"הרצאה {lec}" if lec.isdigit() else (attr(h2.group(1), 20) if h2 else "כללי")
        title = attr(h2.group(1), 44) if h2 else label
        blocks.append(wrap_b(f"<h4 class=chaphead>{h2.group(1) if h2 else title}</h4>",
                             "", t=label, h=title, x=True, keep=True))
        for art in re.findall(r"(?s)<article .*?</article>", body):
            n_items += 1
            art = art.replace('<article class="item t"', '<article class="item"', 1)
            art = re.sub(r'<article class="item[^"]*"', '<article class="item"', art, count=1)
            blocks.append(wrap_b(art, "gitem", h=title))
    print(f"  משפטי זיהוי: {n_items}")
    return "".join(blocks)


def extract_tables() -> str:
    src = read(SRC_GLOSS)
    blocks = []
    cmp_line = _panel_line(src, '<div class="panel panel-compare')
    tbl = re.search(r"(?s)<table class=cmpt>.*?</table>", cmp_line)
    blocks.append(wrap_b("<h4 class=subh>⚖️ זוגות מושגים שקל להתבלבל ביניהם</h4>",
                         "", t="זוגות מושגים", h="זוגות מושגים", x=True, keep=True))
    for c in chunk_table(tbl.group(0), 14):
        blocks.append(wrap_b(c, "cmpblk", h="זוגות מושגים"))
    q_line = _panel_line(src, '<div class="panel panel-quick')
    tbl2 = re.search(r"(?s)<table class=cmpt>.*?</table>", q_line)
    blocks.append(wrap_b("<h4 class=subh>🔁 דפוסים חוזרים בשאלות — משפט המפתח</h4>",
                         "", t="דפוסים חוזרים", h="דפוסים חוזרים", x=True, keep=True))
    for c in chunk_table(tbl2.group(0), 14):
        blocks.append(wrap_b(c, "cmpblk", h="דפוסים חוזרים"))
    return "".join(blocks)


# ───────────────────────── פקודות ומבנים ─────────────────────────

def extract_commands() -> str:
    src = read(SRC_CMDS)
    start = src.find('<h2 id="git"')
    end = src.find("</div>", src.find('<p class=src'))
    region = src[start:end]
    blocks, cur = [], ""
    for el in split_top(region):
        tag = re.match(r"<([a-zA-Z0-9]+)", el).group(1).lower()
        if tag == "h2":
            cur = attr(el, 40)
            blocks.append(wrap_b(el, "", t=attr(el, 24), h=cur, x=True, keep=True))
        elif tag == "table":
            for c in chunk_table(el, 12):
                blocks.append(wrap_b(c, "", h=cur))
        elif tag in ("h3", "h4"):
            blocks.append(wrap_b(el, "", h=cur, keep=True))
        else:
            blocks.append(wrap_b(el, "", h=cur))
    return "".join(blocks)


# ───────────────────────── מדריך הלמידה ─────────────────────────

def _guide_short(h1_text: str) -> str:
    m = re.search(r"הרצאה\s*(\d+)", h1_text)
    return f"הרצאה {m.group(1)}" if m else attr(h1_text, 18)


# הרצאה 11 חסרה במדריך המקורי (נוספה לקורס אחרי כתיבתו).
# התמצית כאן מבוססת על בלוק הרצאה 11 בדף-עזר-להדפסה.html ועל משפטי הזיהוי.
L11_DIGEST = """<h1>🟦 הרצאה 11 — מצגות HTML בסוכן AI (תמצית)</h1>"""
L11_BODY = """<p><em>ההרצאה נוספה אחרי כתיבת המדריך; תמצית זו מבוססת על דף העזר (סעיף 2) ומשפטי הזיהוי (סעיף 3).</em></p>
<ul>
<li><strong>מחסום הכלי</strong> מתהפך: מתארים <strong>כוונה בשפה טבעית</strong> — והסוכן בונה את המצגת.</li>
<li><strong>Full-Stack</strong> = Front-end (מה שרואים) + Back-end (השרת). <strong>מבחן ניתוק הכבל:</strong> נעצר = תלוי שרת · ממשיך = מקומי. מצגת HTML = <strong>מקומית</strong>.</li>
<li>מצגת = <strong>אתר מקומי</strong> · הדפדפן = נגן · כל שקופית = <strong>דף HTML</strong> · <code>index.html</code> = דף הנחיתה · משתפים את <strong>כל התיקייה</strong>.</li>
<li><strong>Pipeline בן 4 שלבים:</strong> תסריט (בצ'אט) → קובץ AI.txt → סוכן CLI מייצר HTML → לחיצה כפולה על <code>index.html</code>. מתחילים מ<strong>תסריט</strong>, לא משקופיות; עובדים הדרגתית.</li>
<li>שני סוגי מצגות: <strong>אובייקטים</strong> (טכני, "קר") · <strong>תמונות</strong> (חגיגי). <strong>JSON</strong> = גשר לשאיבת סגנון (כמו ב-Suno).</li>
<li><strong>3 שכבות:</strong> HTML (מבנה) · CSS (עיצוב) · JS (התנהגות) = <strong>הפרדת דאגות</strong>. ‏<code>.js</code> אינו Java. <strong>BiDi</strong> = כיווניות דו-סטרית (UAX #9).</li>
<li>פס-קול עם <strong>FFmpeg</strong> (החיבור להרצאה 10). <strong>תיאום רב-סוכני:</strong> תסריטאי + מקודד → סוכן שליט/חוזר. מגבלות: הזיות (אדם בלולאה) · נגישות (WCAG) · אבטחה. חלופות: reveal.js / Marp.</li>
</ul>"""


def extract_guide() -> str:
    src = read(SRC_GUIDE)
    start = src.find('<h1 id="_1"')
    end = src.find("<script", start)
    if end == -1:
        end = src.rfind("</div>")
    region = src[start:end]
    blocks, cur = [], "מפת החומר ומספרים"
    h1short = ""
    first_h1_seen = False
    skipping = False
    l11_added = False

    def add_l11():
        nonlocal l11_added
        if l11_added:
            return
        l11_added = True
        blocks.append(wrap_b(L11_DIGEST, "gh1", t="הרצאה 11",
                             h="הרצאה 11 — מצגות HTML בסוכן AI", x=True, keep=True))
        blocks.append(wrap_b(L11_BODY, "", h="הרצאה 11 — מצגות HTML בסוכן AI"))

    for el in split_top(region):
        tag = re.match(r"<([a-zA-Z0-9]+)", el).group(1).lower()
        text = strip_tags(el)
        if tag == "hr":
            continue
        if tag == "h1":
            if not first_h1_seen and 'id="_1"' in el:
                first_h1_seen = True
                continue  # כותרת המסמך — עמוד השער של הסעיף מחליף אותה
            if "מאגר שאלות" in text:
                # מדגם השאלות שבמדריך מיותר בחוברת — השאלות המלאות בסעיפים 8–11
                add_l11()
                skipping = True
                continue
            skipping = False
            h1short = _guide_short(text)
            cur = attr(text, 46)
            blocks.append(wrap_b(el, "gh1", t=html.escape(h1short), h=cur, x=True, keep=True))
        elif tag == "h2":
            if skipping and "מקורות" not in text:
                continue
            skipping = False
            if "מקורות" in text:
                add_l11()  # המקורות באים אחרי ההרצאות — הרצאה 11 נכנסת לפניהם
                h1short = ""
            special = ("מספרים" in text and "לזכור" in text) or "מפת החומר" in text or "מקורות" in text
            if special or not h1short.startswith("הרצאה"):
                cur = attr(text, 46)
            else:
                cur = attr(f"{h1short} · {text}", 52)
            blocks.append(wrap_b(el, "", t=attr(text, 24) if special else "",
                                 h=cur, x=special, keep=True))
        elif skipping:
            continue
        elif tag in ("h3", "h4"):
            blocks.append(wrap_b(el, "", h=cur, keep=True))
        elif tag == "table":
            for c in chunk_table(el, 12):
                blocks.append(wrap_b(c, "", h=cur))
        else:
            blocks.append(wrap_b(el, "", h=cur))
    add_l11()
    return "".join(blocks)


# ───────────────────────── בנק השאלות ─────────────────────────

def extract_data() -> list:
    src = read(SRC_QUEST)
    m = re.search(r"const DATA=(\[.*)", src)
    if not m:
        raise SystemExit("DATA לא נמצא בהדפסת-שאלות.html")
    raw = m.group(1).splitlines()[0].strip()
    for cut in (raw, raw.rstrip(";"), raw[: raw.rfind("]") + 1]):
        try:
            return json.loads(cut)
        except json.JSONDecodeError:
            continue
    raise SystemExit("DATA לא ניתן לפענוח כ-JSON")


def main() -> None:
    print("בונה חוברת…")
    data = extract_data()
    by_id = {t["id"]: t for t in data}
    for need in ("sample180", "official", "commands"):
        if need not in by_id:
            raise SystemExit(f"נושא חסר ב-DATA: {need}")
    lec_ids = [t["id"] for t in data if re.fullmatch(r"l\d+", t["id"])]
    n_lec = sum(len(by_id[i]["qs"]) for i in lec_ids)
    print(f"  שאלות: לדוגמה {len(by_id['sample180']['qs'])} · רשמיות {len(by_id['official']['qs'])}"
          f" · הרצאות {n_lec} · פקודות {len(by_id['commands']['qs'])}")

    payloads = {
        "{{P_CHEAT}}": extract_cheat(),
        "{{P_IDENT}}": extract_chapters(),
        "{{P_GLOSSARY}}": extract_glossary(),
        "{{P_TABLES}}": extract_tables(),
        "{{P_COMMANDS}}": extract_commands(),
        "{{P_GUIDE}}": extract_guide(),
        "{{DATA}}": json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        "{{UPDATED}}": date.today().strftime("%d.%m.%Y"),
    }
    out = read(TEMPLATE)
    for k, v in payloads.items():
        if k not in out:
            raise SystemExit(f"טוקן חסר בתבנית: {k}")
        out = out.replace(k, v)
    OUT.write_text(out, encoding="utf-8")
    print(f"נכתב: {OUT.name} ({OUT.stat().st_size // 1024}K)")


if __name__ == "__main__":
    sys.exit(main())
