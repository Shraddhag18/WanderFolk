"""Draws WanderFolk's snow-capped ranges as layered SVGs (one file per layer, for parallax)."""
import math, random, sys
OUT = sys.argv[1]
W, H = 1600, 900

def ridge(seed, base, peaks, amp, jag, width=W):
    """A mountain ridge: pointy peaks plus rocky noise. Each point remembers which peak it belongs to."""
    r = random.Random(seed)
    centers = sorted(r.uniform(-60, width + 60) for _ in range(peaks))
    heights = [amp * r.uniform(0.55, 1.0) for _ in centers]
    spreads = [r.uniform(150, 260) for _ in centers]
    pts, owner = [], []
    for x in range(-40, width + 41, 8):
        best, who = 0, 0
        for i, (c, a, s) in enumerate(zip(centers, heights, spreads)):
            h = a * max(0, 1 - (abs(x - c) / s) ** 1.15)
            if h > best:
                best, who = h, i
        best += r.uniform(-jag, jag) * (0.3 + best / amp)
        pts.append((x, base - max(best, 0)))
        owner.append(who)
    return pts, owner, list(zip(centers, heights, spreads))

def path(points, close_to=None):
    d = "M" + " L".join(f"{x:.0f},{y:.0f}" for x, y in points)
    if close_to is not None:
        d += f" L{points[-1][0]:.0f},{close_to} L{points[0][0]:.0f},{close_to} Z"
    return d

def runs(flags):
    """Index runs where flags are true."""
    out, cur = [], []
    for i, f in enumerate(flags):
        if f:
            cur.append(i)
        elif cur:
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out

def snow(pts, owner, peaks, base, line, seed):
    """Each peak gets its own cap: the top part of the peak, with a ragged lower edge."""
    r = random.Random(seed)
    caps = []
    for k, (c, a, s) in enumerate(peaks):
        top = base - a
        snowline = top + a * (1 - line)
        flags = [owner[i] == k and pts[i][1] < snowline for i in range(len(pts))]
        mine = [i for i in range(len(pts)) if owner[i] == k]
        summit = min(mine, key=lambda i: pts[i][1]) if mine else -1
        for run in runs(flags):
            # only the cap that holds this peak's own summit: no slivers where two peaks meet
            if len(run) < 4 or summit not in run:
                continue
            upper = [pts[i] for i in run]
            lower = []
            for x, y in reversed(upper):
                drip = r.uniform(4, 30) if r.random() < 0.5 else r.uniform(0, 10)
                lower.append((x, min(snowline + drip, y + 60)))
            caps.append(path(upper + lower) + " Z")
    return caps

def sunlit(pts, owner, peaks, base, seed):
    """The rose-lit left face of each peak (the sun is low on the left), down to about half its height."""
    r = random.Random(seed)
    faces = []
    for k, (c, a, s) in enumerate(peaks):
        idx = [i for i in range(len(pts)) if owner[i] == k]
        if len(idx) < 4:
            continue
        summit = min(idx, key=lambda i: pts[i][1])
        sx, sy = pts[summit]
        if sy > base - a * 0.6:          # a minor bump, not a summit
            continue
        depth = sy + (base - sy) * r.uniform(0.42, 0.55)
        foot = sy + (base - sy) * r.uniform(0.7, 0.82)
        left = [pts[i] for i in idx if i <= summit and pts[i][1] <= foot]
        if len(left) < 4:
            continue
        # summit -> a point inside the mountain -> back to the slope lower down: a slanted lower edge
        faces.append(path(left + [(sx + r.uniform(4, 14), depth)]) + " Z")
    return faces

def trees(base_pts, seed, count, size):
    r = random.Random(seed)
    out = []
    for _ in range(count):
        i = r.randrange(len(base_pts)); x, y = base_pts[i]
        s = size * r.uniform(0.6, 1.25)
        out.append(f"M{x:.0f},{y - s:.0f} L{x + s * 0.32:.0f},{y + 2:.0f} L{x - s * 0.32:.0f},{y + 2:.0f} Z")
    return out

def lake(pts, base, width, seed):
    """Still water below the near range: sunset colours, the range's reflection, a far-shore tree line and a sun glint."""
    r = random.Random(seed)
    mirror = path([(x, 2 * base - y) for x, y in pts], None)
    out = [f'<defs><linearGradient id="water" x1="0" y1="0" x2="0" y2="1">'
           f'<stop offset="0" stop-color="#F6C4A8"/><stop offset=".35" stop-color="#D99AAE"/>'
           f'<stop offset="1" stop-color="#5F5C93"/></linearGradient>'
           f'<clipPath id="lk"><rect x="-40" y="{base}" width="{width + 80}" height="{H - base}"/></clipPath></defs>',
           f'<rect x="-40" y="{base}" width="{width + 80}" height="{H - base}" fill="url(#water)"/>',
           # the range upside down in the water, fading as it comes towards you
           f'<g clip-path="url(#lk)" opacity=".42"><path d="{mirror} L{width + 40},{base} L-40,{base} Z" fill="#6B5F97"/></g>']
    # long, thin ripples of light
    for _ in range(int(width / 26)):
        y = r.uniform(base + 14, H - 20); x = r.uniform(-20, width); l = r.uniform(30, 140) * (0.6 + (y - base) / (H - base))
        out.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{l:.0f}" height="2" rx="1" fill="#FFF3E2" opacity="{r.uniform(.18, .45):.2f}"/>')
    # the setting sun's glint, a broken column of gold under it
    sx = width * 0.42
    for i in range(16):
        y = base + 10 + i * (H - base - 40) / 16; half = 50 + i * 5 + r.uniform(-14, 14)
        out.append(f'<rect x="{sx - half + r.uniform(-18, 18):.0f}" y="{y:.0f}" width="{2 * half:.0f}" height="3" rx="1.5" fill="#FFD27A" opacity="{.75 - i * .035:.2f}"/>')
    # a dark line of pines along the far shore, where the mountains meet the water
    shore = [(x, base - r.uniform(2, 6)) for x in range(-40, width + 41, 20)]
    out.append(f'<path d="{path(shore, base + 3)}" fill="#3D3F6A"/>')
    out += [f'<path d="{d}" fill="#3D3F6A"/>' for d in trees([(x, base) for x, _ in shore], seed + 1, int(width / 9), 22)]
    return "".join(out)

def bank(width, seed):
    """The near shore: a grassy bank along the water, reeds, and a few pines at the ends, fading into the page's ink."""
    r = random.Random(seed)
    top = []
    for x in range(-40, width + 41, 20):
        t = x / width
        # the bank rises at both ends and dips low in the middle so the lake shows through
        top.append((x, 842 - 70 * (abs(t - 0.5) * 2) ** 2.2 + r.uniform(-4, 4)))
    out = ['<defs><linearGradient id="bank" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2F4D43"/>'
           '<stop offset=".55" stop-color="#1B2C42"/><stop offset="1" stop-color="#14213D"/></linearGradient></defs>',
           f'<path d="{path(top, H)}" fill="url(#bank)"/>']
    def at(x):
        for (x0, y0), (x1, y1) in zip(top, top[1:]):
            if x0 <= x <= x1:
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
        return top[-1][1]
    # grass: thin, slightly bent blades along the top of the bank, tips catching the low sun
    blades = []
    for _ in range(int(width * 0.55)):
        x = r.uniform(-30, width + 30); y = at(x) + r.uniform(-1, 8); h = r.uniform(10, 34); lean = r.uniform(-9, 9); w = r.uniform(1.6, 3.2)
        col = r.choice(["#3E6650", "#4C7556", "#355A49", "#5B7F57"])
        blades.append(f'<path d="M{x - w:.1f},{y:.1f} Q{x + lean * .4:.1f},{y - h * .6:.1f} {x + lean:.1f},{y - h:.1f} Q{x + lean * .4 + w * .4:.1f},{y - h * .55:.1f} {x + w:.1f},{y:.1f} Z" fill="{col}"/>')
        if r.random() < 0.18:
            blades.append(f'<circle cx="{x + lean:.1f}" cy="{y - h:.1f}" r="1.3" fill="#E8B872" opacity=".8"/>')
    out += blades
    # a few cattails at the water's edge
    for _ in range(int(width / 180)):
        x = r.uniform(width * .15, width * .85); y = at(x) + 4; h = r.uniform(40, 62)
        out.append(f'<path d="M{x:.0f},{y:.0f} Q{x + 3:.0f},{y - h / 2:.0f} {x + 2:.0f},{y - h:.0f}" stroke="#2F4D43" stroke-width="2" fill="none"/>'
                   f'<rect x="{x - 0.5:.0f}" y="{y - h + 6:.0f}" width="5" height="14" rx="2.5" fill="#6B4A3A"/>')
    # pines only at the two ends, framing the lake
    for side in (0, 1):
        for _ in range(7):
            x = r.uniform(-30, width * .12) if side == 0 else r.uniform(width * .88, width + 30)
            s = r.uniform(70, 150); y = at(x) + 6
            out.append(f'<path d="M{x:.0f},{y - s:.0f} L{x + s * .3:.0f},{y:.0f} L{x - s * .3:.0f},{y:.0f} Z" fill="#1A2A3E"/>')
    return "".join(out)

# Sunset alpenglow: two ranges, a few broad peaks each (name, seed, base, peaks narrow/wide, amp, jag, spread, colours, snow line)
layers = [
    ("far",  14, 560, (4, 6), 360, 5, (260, 380), "#C3A2C6", "#F4C3B6", "#FFF3EA", 0.70),
    ("near", 37, 640, (3, 5), 300, 8, (240, 340), "#6C6599", "#D88994", "#FBE6E4", 0.74),
]

def ridge2(seed, base, peaks, amp, jag, spread, width):
    """Like ridge(), with broader peaks spaced evenly so a few of them still fill the width."""
    r = random.Random(seed)
    step = (width + 120) / peaks
    centers = [-60 + step * (i + 0.5) + r.uniform(-step * .25, step * .25) for i in range(peaks)]
    heights = [amp * r.uniform(0.6, 1.0) for _ in centers]
    spreads = [r.uniform(*spread) for _ in centers]
    pts, owner = [], []
    for x in range(-40, width + 41, 8):
        best, who = 0, 0
        for i, (c, a, s) in enumerate(zip(centers, heights, spreads)):
            h = a * max(0, 1 - (abs(x - c) / s) ** 1.15)
            if h > best:
                best, who = h, i
        best += r.uniform(-jag, jag) * (0.3 + best / amp)
        pts.append((x, base - max(best, 0)))
        owner.append(who)
    return pts, owner, list(zip(centers, heights, spreads))

# Two widths of every layer: 16:9 for phones and tall windows, and a wider panorama (8:3) for laptops, so a wide,
# short window never has to crop the summits off to fill its width.
for suffix, width, k in (("", W, 0), ("-wide", 2400, 1)):
    for name, seed, base, peaks, amp, jag, spread, rock, lit, snowc, line in layers:
        pts, owner, pk = ridge2(seed + 100 * k, base, peaks[k], amp, jag, spread, width)
        body = f'<path d="{path(pts, H)}" fill="{rock}"/>'
        faces = "".join(f'<path d="{d}" fill="{lit}"/>' for d in sunlit(pts, owner, pk, base, seed + 1))
        caps = "".join(f'<path d="{d}" fill="{snowc}"/>' for d in snow(pts, owner, pk, base, line, seed + 2))
        water = lake(pts, base, width, seed + 3) if name == "near" else ""
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {H}" preserveAspectRatio="xMidYMax slice" '
               f'aria-hidden="true">{body}{faces}{caps}{water}</svg>')
        open(f"{OUT}/range-{name}{suffix}.svg", "w").write(svg)
    open(f"{OUT}/range-front{suffix}.svg", "w").write(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {H}" preserveAspectRatio="xMidYMax slice" aria-hidden="true">{bank(width, 51 + k)}</svg>')
print("ok")

# ---- a wide, short banner for the trip page: two ranges in one file, peaks inside a 1600x400 box ----
BW, BH = 1600, 400
parts = []
for seed, base, peaks, amp, jag, rock, lit, snowc, line in [
    (14, 390, 6, 230, 2, "#AFC6E3", "#E9C3D4", "#FFFFFF", 0.70),
    (41, 425, 5, 140, 2, "#34496E", "#8E5A7C", "#EEF3FB", 0.82),
]:
    pts, owner, pk = ridge(seed, base, peaks, amp, jag, width=BW)
    parts.append(f'<path d="{path(pts, BH)}" fill="{rock}"/>')
    parts += [f'<path d="{d}" fill="{lit}"/>' for d in sunlit(pts, owner, pk, base, seed + 1)]
    parts += [f'<path d="{d}" fill="{snowc}"/>' for d in snow(pts, owner, pk, base, line, seed + 2)]
open(f"{OUT}/banner.svg", "w").write(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {BW} {BH}" preserveAspectRatio="xMidYMax slice" aria-hidden="true">{"".join(parts)}</svg>')
