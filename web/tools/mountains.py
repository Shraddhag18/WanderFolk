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

layers = [
    # name, seed, base, peaks, amp, jag, rock colour, sunlit colour, snow colour, snow line
    # snow covers the top (1 - line) of each peak; the lit face is a solid colour between rock and rose
    ("far",  14, 600, 8, 380, 6, "#AFC6E3", "#E9C3D4", "#FFFFFF", 0.70),
    ("mid",  23, 700, 6, 360, 9, "#7393BD", "#C98EAA", "#F7FAFF", 0.72),
    ("near", 37, 805, 5, 330, 11, "#34496E", "#8E5A7C", "#EEF3FB", 0.76),
]
for name, seed, base, peaks, amp, jag, rock, lit, snowc, line in layers:
    pts, owner, pk = ridge(seed, base, peaks, amp, jag)
    body = f'<path d="{path(pts, H)}" fill="{rock}"/>'
    faces = "".join(f'<path d="{d}" fill="{lit}"/>' for d in sunlit(pts, owner, pk, base, seed + 1))
    caps = "".join(f'<path d="{d}" fill="{snowc}"/>' for d in snow(pts, owner, pk, base, line, seed + 2))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax slice" '
           f'aria-hidden="true">{body}{faces}{caps}</svg>')
    open(f"{OUT}/range-{name}.svg", "w").write(svg)

# the foreground: a dark pine ridge the page's ink colour, so the next section rises out of it
pts, _, _ = ridge(51, 880, 6, 120, 4)
fg = f'<path d="{path(pts, H)}" fill="#14213D"/>' + "".join(f'<path d="{d}" fill="#14213D"/>' for d in trees(pts, 52, 70, 46))
open(f"{OUT}/range-front.svg", "w").write(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax slice" aria-hidden="true">{fg}</svg>')
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
