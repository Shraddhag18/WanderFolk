"""
WanderFolk look and feel: one stylesheet plus small HTML builders, so app.py stays about the flow.
Everything that reaches the page through these helpers is HTML-escaped.
"""

from __future__ import annotations

import re
from html import escape
from urllib.parse import quote

AVATAR_COLORS = ["#e4572e", "#0f766e", "#7c3aed", "#d97706", "#2563eb", "#be185d"]

# First match wins, so the specific ones go first.
ACTIVITY_ICONS = [
    (r"arrive|check in", "🏨"), (r"\bdrive to\b|driving", "🚗"), (r"tour|museum", "🗺️"), (r"hik|trail|walk", "🥾"),
    (r"beach|tide|ocean|surf", "🏖️"), (r"overlook|view|falls|bridge|sunset", "🌅"),
    (r"breakfast|coffee|caf[eé]", "☕"), (r"lunch|taco|food", "🌮"), (r"dinner|picnic|restaurant", "🍽️"),
    (r"shop", "🛍️"), (r"nap|downtime|relax|rest", "😌"),
]

# kind -> (icon, css class)
CHANGE_STYLE = {"feedback": ("🗣️", "fb"), "community": ("🌍", "co"), "private": ("🔒", "pr")}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stMarkdown, button, input, textarea { font-family: 'Inter', system-ui, sans-serif; }
h1, h2, h3, h4 { font-family: 'Fraunces', Georgia, serif !important; letter-spacing: -0.01em; }
.block-container { padding-top: 3.2rem; max-width: 1180px; }

/* hero */
.hero { position: relative; overflow: hidden; border-radius: 22px; padding: 24px 32px; margin-bottom: 14px;
  display: flex; align-items: center; justify-content: space-between; gap: 24px; flex-wrap: wrap;
  color: #fff; min-height: 200px; text-shadow: 0 1px 10px rgba(12, 38, 48, .45);
  background: linear-gradient(90deg, rgba(12, 38, 48, .62) 0%, rgba(12, 38, 48, .22) 55%, rgba(12, 38, 48, 0) 100%),
    url("__SCENE__") center bottom / cover no-repeat;
  box-shadow: 0 18px 40px -22px rgba(15, 76, 92, .8); }
.hero-kicker { font-size: .78rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; opacity: .92; }
.hero-title { font-family: 'Fraunces', Georgia, serif; font-size: 2.5rem; font-weight: 700; line-height: 1.05;
  margin: 4px 0 6px; }
.hero-sub { font-size: 1rem; max-width: 400px; opacity: .96; margin: 0; }
.stats { display: flex; gap: 10px; flex-wrap: wrap; position: relative; z-index: 1; }
.stat { background: rgba(12, 38, 48, .32); border: 1px solid rgba(255, 255, 255, .4); border-radius: 14px;
  padding: 10px 14px; min-width: 98px; backdrop-filter: blur(6px); }
.stat b { display: block; font-family: 'Fraunces', Georgia, serif; font-size: 1.75rem; line-height: 1.1; }
.stat span { font-size: .78rem; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; opacity: .92; }

/* tabs as pills */
.stTabs [role="tablist"] { gap: 4px; background: #f3ead9; padding: 6px; border-radius: 999px; width: fit-content;
  max-width: 100%; border: 0; box-shadow: none; margin-bottom: 10px; overflow-x: auto; scrollbar-width: none; }
.stTabs [role="tablist"]::-webkit-scrollbar { display: none; }
.stTabs [data-testid="stTab"] { flex: none; white-space: nowrap; }
.stTabs [role="tablist"]::before, .stTabs [role="tablist"]::after { display: none; }
.stTabs [data-testid="stTab"] { border-radius: 999px; padding: 7px 16px; height: auto; border: 0; color: #5b6472; }
.stTabs [data-testid="stTab"] p { font-weight: 600; font-size: .92rem; }
.stTabs [data-testid="stTab"][aria-selected="true"] { background: #fff; color: #e4572e;
  box-shadow: 0 2px 8px rgba(31, 42, 55, .12); }
.stTabs .react-aria-SelectionIndicator { display: none; }

/* the journey: four steps and what to do next */
.steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 4px 0 12px; }
.step { display: flex; gap: 10px; align-items: flex-start; background: #fff; border: 1px solid #eadfca;
  border-radius: 14px; padding: 11px 13px; }
.step-n { width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; flex: none;
  font-size: .82rem; font-weight: 700; background: #f3ead9; color: #6b7280; }
.step-t { font-weight: 700; font-size: .92rem; line-height: 1.25; }
.step-d { font-size: .8rem; color: #6b7280; margin-top: 2px; line-height: 1.3; }
.step.done .step-n { background: #16a34a; color: #fff; }
.step.done .step-t { color: #166534; }
.step.now { border: 2px solid #e4572e; box-shadow: 0 10px 22px -16px rgba(228, 87, 46, .9); }
.step.now .step-n { background: #e4572e; color: #fff; }
.step.todo { opacity: .62; }
.next { background: #fff7ed; border: 1px solid #fed7aa; border-radius: 14px; padding: 12px 16px; font-size: .96rem; }
.next b { color: #c2410c; }
@media (max-width: 900px) { .steps { grid-template-columns: repeat(2, 1fr); } }

/* small helpers */
.legend { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: .8rem; color: #5b6472; margin: 2px 0 12px; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
.hood { font-size: .78rem; color: #8a8f98; margin-top: 4px; }
.hood code { font-size: .74rem; background: #f3ead9; color: #6b7280; padding: 1px 5px; border-radius: 5px; }
.plan-head { font-family: 'Fraunces', Georgia, serif; font-weight: 700; font-size: 1.05rem; margin-bottom: 8px; }

/* buttons and inputs */
.stButton > button, .stFormSubmitButton > button, [data-testid="stPopover"] button { border-radius: 999px;
  font-weight: 600; border: 1px solid #e3d8c3; padding: .35rem 1.1rem; min-height: 42px;
  transition: transform .12s ease, box-shadow .12s ease; }
.stButton > button:hover, .stFormSubmitButton > button:hover { transform: translateY(-1px);
  box-shadow: 0 6px 16px -8px rgba(31, 42, 55, .45); }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"] { border: 0;
  color: #fff; background: linear-gradient(120deg, #e4572e, #f59e0b); }
.stTextInput input, .stTextArea textarea, .stNumberInput input { border-radius: 12px; background: #fff; }

/* sidebar */
[data-testid="stSidebar"] { background: linear-gradient(180deg, #fdf3e3 0%, #f3ead9 100%);
  border-right: 1px solid #eadfca; }
.status { display: flex; align-items: center; gap: 8px; background: #fff; border: 1px solid #eadfca;
  border-radius: 12px; padding: 8px 12px; margin-bottom: 8px; font-size: .86rem; }
.status b { font-weight: 600; }
.dot { width: 9px; height: 9px; border-radius: 50%; background: #9ca3af; flex: none; }
.dot.on { background: #16a34a; box-shadow: 0 0 0 4px rgba(22, 163, 74, .18); }

/* travelers */
.person { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.avatar { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; color: #fff;
  font-weight: 700; font-size: 1.05rem; flex: none; }
.person-name { font-family: 'Fraunces', Georgia, serif; font-size: 1.2rem; font-weight: 600; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 4px; }
.chip { background: #fff; border: 1px solid #eadfca; border-radius: 999px; padding: 4px 12px; font-size: .86rem; }
.chip.lock { background: #f5f3ff; border-color: #ddd6fe; color: #5b21b6; }
.chip.tip { background: #ecfdf5; border-color: #a7f3d0; color: #065f46; border-radius: 12px; padding: 8px 14px; }

/* itinerary */
.day { background: #fff; border: 1px solid #eadfca; border-radius: 18px; padding: 16px 20px 8px;
  margin-bottom: 14px; box-shadow: 0 8px 22px -18px rgba(31, 42, 55, .5); }
.day-title { font-family: 'Fraunces', Georgia, serif; font-weight: 700; font-size: 1.15rem; color: #e4572e;
  margin-bottom: 8px; }
.stop { display: grid; grid-template-columns: 82px 18px 1fr; align-items: start; padding-bottom: 12px;
  position: relative; }
.stop-time { font-size: .8rem; font-weight: 700; color: #6b7280; padding-top: 2px; }
.stop-dot { width: 10px; height: 10px; border-radius: 50%; background: #f59e0b; margin-top: 5px;
  box-shadow: 0 0 0 3px #fef3c7; z-index: 1; }
.stop:not(:last-child)::before { content: ""; position: absolute; left: 86px; top: 14px; bottom: -4px;
  width: 2px; background: #f3ead9; }
.stop-what { font-size: .95rem; }

/* why cards */
.why { background: #fff; border: 1px solid #eadfca; border-left: 5px solid #7c3aed; border-radius: 14px;
  padding: 11px 14px; margin-bottom: 10px; }
.why.fb { border-left-color: #e4572e; }
.why.co { border-left-color: #0f766e; }
.why.pr { border-left-color: #6b7280; background: #f9fafb; }
.why-action { font-weight: 700; }
.you { display: inline-block; background: #e4572e; color: #fff; border-radius: 999px; padding: 1px 9px;
  font-size: .7rem; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; margin-left: 6px;
  vertical-align: 2px; }
.why.mine { box-shadow: 0 0 0 2px #fed7aa; }

/* trip proposals */
.prop-title { font-family: 'Fraunces', Georgia, serif; font-weight: 700; font-size: 1.25rem; line-height: 1.2; }
.prop-tag { color: #5b6472; font-size: .92rem; margin: 2px 0 8px; }
.prop-why { margin: 8px 0 0; padding-left: 18px; font-size: .9rem; }
.prop-why li { margin-bottom: 3px; }
.prop-watch { background: #fff7ed; border: 1px solid #fed7aa; border-radius: 10px; padding: 6px 10px;
  font-size: .84rem; margin-top: 8px; color: #9a3412; }
.prop-votes { font-size: .86rem; color: #5b6472; margin-top: 8px; }
.prop-votes b { color: #e4572e; }

/* group members */
.members { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; margin: 8px 0; }
.member { background: #fff; border: 1px solid #eadfca; border-radius: 16px; padding: 14px 16px; }
.member .person { margin-bottom: 4px; }
.member-note { font-size: .82rem; color: #8a8f98; }
.me-line { font-size: .95rem; margin: 2px 0 10px; }
.me-line b { color: #e4572e; }
.invite { background: #fff; border: 1.5px dashed #f59e0b; border-radius: 14px; padding: 12px 16px; margin: 6px 0;
  font-size: .9rem; word-break: break-all; }
.invite b { display: block; font-size: .78rem; letter-spacing: .06em; text-transform: uppercase; color: #c2410c;
  margin-bottom: 2px; }
.why-because { font-size: .85rem; color: #5b6472; margin-top: 3px; }
.why-because i { color: #1f2a37; }
.empty { border: 1.5px dashed #e3d8c3; border-radius: 16px; padding: 22px; text-align: center; color: #6b7280; }

/* phones */
@media (max-width: 640px) {
  .block-container { padding: 3rem .9rem 4rem; }
  .hero { padding: 16px 18px; border-radius: 18px; gap: 12px; min-height: 0; }
  .hero-title { font-size: 1.9rem; }
  .hero-sub { font-size: .92rem; }
  .hero.in .hero-sub { display: none; }
  .stats { width: 100%; gap: 8px; }
  .stat { flex: 1; min-width: 0; padding: 8px 10px; }
  .stat b { font-size: 1.35rem; }
  .stat span { font-size: .64rem; }
  .steps { grid-template-columns: repeat(4, 1fr); gap: 6px; }
  .step { flex-direction: column; align-items: center; text-align: center; padding: 8px 4px; gap: 4px; }
  .step-t { font-size: .72rem; }
  .step-d { display: none; }
  .stTabs [role="tablist"] { border-radius: 16px; width: 100%; }
  .stButton > button, .stFormSubmitButton > button, [data-testid="stPopover"] button { width: 100%; }
  .stop { grid-template-columns: 66px 16px 1fr; }
  .stop:not(:last-child)::before { left: 70px; }
  .day { padding: 14px 14px 6px; }
  h2 { font-size: 1.45rem !important; }
  input, textarea { font-size: 16px !important; }  /* stops iOS zooming in on focus */
}
</style>
"""


def initial_avatar(name: str, index: int) -> str:
    color = AVATAR_COLORS[index % len(AVATAR_COLORS)]
    return (f'<div class="person"><div class="avatar" style="background:{color}">{escape(name[:1].upper())}</div>'
            f'<div class="person-name">{escape(name)}</div></div>')


def hero(stats: list[tuple[str, int]] | None = None, kicker: str = "Group trip planner") -> str:
    """With stats: the compact in-app header. Without: the welcome banner."""
    tiles = "".join(f'<div class="stat"><b>{value}</b><span>{escape(label)}</span></div>' for label, value in stats or [])
    return (f'<div class="hero{" in" if stats else ""}"><div>'
            f'<div class="hero-kicker">{escape(kicker)}</div>'
            '<div class="hero-title">WanderFolk</div>'
            '<p class="hero-sub">Plan trips with friends. WanderFolk remembers what everyone likes, '
            'and what went wrong last time.</p></div>'
            f'<div class="stats">{tiles}</div></div>')


def status(label: str, value: str, on: bool) -> str:
    return (f'<div class="status"><span class="dot{" on" if on else ""}"></span>'
            f'<span><b>{escape(label)}</b> · {escape(value)}</span></div>')


def chips(texts: list[str], kind: str = "") -> str:
    """kind '' picks the private style per chip from its 🔒 prefix; 'tip' is the community style."""
    out = []
    for t in texts:
        cls = kind or ("lock" if t.startswith("🔒") else "")
        out.append(f'<span class="chip {cls}">{escape(t)}</span>')
    return f'<div class="chips">{"".join(out)}</div>'


def activity_icon(activity: str) -> str:
    return next((icon for pattern, icon in ACTIVITY_ICONS if re.search(pattern, activity, re.I)), "📍")


def day_card(day: dict) -> str:
    stops = "".join(
        f'<div class="stop"><span class="stop-time">{escape(str(i.get("time", "")))}</span>'
        f'<span class="stop-dot"></span>'
        f'<span class="stop-what">{activity_icon(str(i.get("activity", "")))} {escape(str(i.get("activity", "")))}</span></div>'
        for i in day["items"])
    return f'<div class="day"><div class="day-title">Day {escape(str(day["day"]))}</div>{stops}</div>'


def why_card(change: dict, mine: bool = False) -> str:
    """mine: this change came from the person looking at the screen."""
    kind = "private" if change.get("private") else change.get("kind")
    icon, cls = CHANGE_STYLE.get(kind, ("💜", ""))
    who, because = escape(str(change.get("who") or "someone")), escape(str(change.get("because", "")))
    who = "you" if mine else who
    if kind == "private" and mine:
        reason = "Because of your private note. Only you can see that it was yours."
    elif kind == "private":
        reason = "Because of a private preference. The planner knows whose, the group doesn't."
    elif kind == "community":
        reason = f"Because another traveler reported: <i>“{because}”</i>"
    elif kind == "feedback":
        reason = f"Because {who} said after {escape(str(change.get('trip') or 'the last trip'))}: <i>“{because}”</i>"
    else:
        reason = f"Because {who} said: <i>“{because}”</i>"
    badge = '<span class="you">From you</span>' if mine else ""
    return (f'<div class="why {cls}{" mine" if mine else ""}"><div class="why-action">{icon} '
            f'{escape(str(change.get("action", "")))}{badge}</div><div class="why-because">{reason}</div></div>')


def member_card(name: str, index: int, notes: list[str], is_me: bool = False, waiting: str = "") -> str:
    body = chips(notes) if notes else f'<div class="member-note">{escape(waiting)}</div>'
    card = initial_avatar(name + (" (you)" if is_me else ""), index)
    return f'<div class="member">{card}{body}</div>'


def members(cards: list[str]) -> str:
    return f'<div class="members">{"".join(cards)}</div>'


def me_line(me: str, group: str) -> str:
    return f'<div class="me-line">You are <b>{escape(me)}</b> in <b>{escape(group)}</b></div>'


def invite(url: str) -> str:
    return f'<div class="invite"><b>Invite link</b>{escape(url)}</div>'


def empty(text: str) -> str:
    return f'<div class="empty">{escape(text)}</div>'


def steps(items: list[tuple[str, str, bool]]) -> str:
    """items: (title, description, done). The first one not done is highlighted as the current step."""
    current = next((i for i, (_, _, done) in enumerate(items) if not done), None)
    out = []
    for i, (title, desc, done) in enumerate(items):
        state = "done" if done else "now" if i == current else "todo"
        out.append(f'<div class="step {state}"><div class="step-n">{"✓" if done else i + 1}</div>'
                   f'<div><div class="step-t">{escape(title)}</div><div class="step-d">{escape(desc)}</div></div></div>')
    return f'<div class="steps">{"".join(out)}</div>'


def next_step(text: str, label: str = "Next step") -> str:
    return f'<div class="next"><b>{escape(label)}:</b> {escape(text)}</div>'


def legend() -> str:
    keys = [("#e4572e", "Learned from a past trip"), ("#0f766e", "Tip from other travelers"),
            ("#7c3aed", "Someone's preference"), ("#6b7280", "Private note")]
    return '<div class="legend">' + "".join(f'<span><i style="background:{c}"></i>{t}</span>' for c, t in keys) + "</div>"


def hood(html: str) -> str:
    """A quiet 'under the hood' line. Takes trusted HTML (our own text, with <code> for ids)."""
    return f'<div class="hood">⚙️ Under the hood: {html}</div>'


def plan_head(text: str) -> str:
    return f'<div class="plan-head">{escape(text)}</div>'


def count(n: int, noun: str) -> str:
    """count(1, 'tip') -> '1 tip', count(3, 'tip') -> '3 tips'."""
    return f"{n} {noun}{'' if n == 1 else 's'}"


# The header picture: mountains with snow caps, green hills and pines, and a lake in front.
SCENE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 320" preserveAspectRatio="xMidYMax slice">
<defs>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3b82b0"/><stop offset=".55" stop-color="#8fc7dc"/><stop offset="1" stop-color="#fde9c4"/></linearGradient>
<linearGradient id="lake" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7fd0dc"/><stop offset="1" stop-color="#1f7a8c"/></linearGradient>
</defs>
<rect width="1200" height="320" fill="url(#sky)"/>
<circle cx="960" cy="78" r="34" fill="#fff6d6" opacity=".9"/>
<g fill="#fff" opacity=".75"><ellipse cx="520" cy="62" rx="62" ry="12"/><ellipse cx="566" cy="52" rx="40" ry="11"/><ellipse cx="1090" cy="118" rx="56" ry="10"/></g>
<path d="M0 232 L150 120 L260 190 L400 84 L520 176 L640 110 L770 196 L900 96 L1030 180 L1120 128 L1200 176 V260 H0 Z" fill="#7b97ab"/>
<path d="M400 84 L436 112 L414 110 L398 124 L384 108 L366 110 Z M900 96 L934 122 L912 120 L898 134 L884 118 L868 120 Z M150 120 L178 141 L160 140 L148 151 L136 139 L122 141 Z M640 110 L668 132 L650 130 L640 142 L628 130 L612 132 Z" fill="#fff"/>
<path d="M0 250 L120 172 L250 222 L380 150 L520 226 L700 160 L840 220 L990 150 L1110 212 L1200 178 V270 H0 Z" fill="#4f7a82"/>
<path d="M0 236 C160 196 300 232 470 214 C640 196 760 236 920 212 C1040 196 1130 216 1200 206 V280 H0 Z" fill="#2f8f5b"/>
<path d="M0 252 C200 226 360 256 560 238 C760 220 940 256 1200 232 V290 H0 Z" fill="#3fa66a"/>
<path d="M70 196 l9 22 h-18 z M70 206 l12 22 h-23 z" fill="#14532d"/><path d="M104 202 l8 20 h-16 z M104 211 l10 20 h-21 z" fill="#166534"/><path d="M150 192 l10 24 h-20 z M150 203 l13 24 h-26 z" fill="#14532d"/><path d="M236 204 l8 20 h-16 z M236 213 l10 20 h-21 z" fill="#166534"/><path d="M330 198 l9 22 h-18 z M330 208 l12 22 h-23 z" fill="#14532d"/><path d="M372 206 l7 18 h-14 z M372 214 l9 18 h-18 z" fill="#166534"/><path d="M640 206 l8 20 h-16 z M640 215 l10 20 h-21 z" fill="#14532d"/><path d="M690 198 l9 23 h-18 z M690 208 l12 23 h-23 z" fill="#166534"/><path d="M735 204 l8 20 h-16 z M735 213 l10 20 h-21 z" fill="#14532d"/><path d="M905 196 l10 24 h-20 z M905 207 l13 24 h-26 z" fill="#14532d"/><path d="M950 202 l8 20 h-16 z M950 211 l10 20 h-21 z" fill="#166534"/><path d="M1010 194 l10 25 h-20 z M1010 205 l13 25 h-26 z" fill="#14532d"/><path d="M1060 202 l8 20 h-16 z M1060 211 l10 20 h-21 z" fill="#166534"/><path d="M1130 196 l9 23 h-18 z M1130 206 l12 23 h-23 z" fill="#14532d"/><path d="M1170 204 l8 19 h-16 z M1170 213 l10 19 h-21 z" fill="#166534"/>
<rect y="262" width="1200" height="58" fill="url(#lake)"/>
<path d="M0 262 C220 254 420 268 640 260 C860 252 1020 268 1200 258 V266 H0 Z" fill="#2f8f5b"/>
<g stroke="#fff" stroke-width="2" stroke-linecap="round" opacity=".5"><path d="M120 284 h70 M260 298 h110 M520 282 h90 M700 302 h80 M880 286 h120 M1060 300 h70"/></g>
</svg>"""

CSS = CSS.replace("__SCENE__", "data:image/svg+xml," + quote(SCENE.replace("\n", "")))


def proposal(number: int, prop: dict, voters: list[str], leading: bool = False) -> str:
    """One destination idea: what it is, why it fits this group, and who would go."""
    facts = [f"🚗 {prop['travel']}"] if prop.get("travel") else []
    facts += [f"💰 {prop['budget']}"] if prop.get("budget") else []
    facts += [f"✨ {h}" for h in prop.get("highlights", [])]
    why = "".join(f"<li>{escape(w)}</li>" for w in prop.get("why", []))
    watch = f'<div class="prop-watch">⚠️ {escape(prop["watch_out"])}</div>' if prop.get("watch_out") else ""
    votes = (f'<b>👍 {len(voters)}</b> · {escape(", ".join(voters))}' if voters else "No votes yet")
    crown = " 🏆" if leading else ""
    return (f'<div class="prop-title">{number}. {escape(prop["destination"])}{crown}</div>'
            f'<div class="prop-tag">{escape(prop.get("tagline", ""))}</div>{chips(facts)}'
            f'<ul class="prop-why">{why}</ul>{watch}<div class="prop-votes">{votes}</div>')
