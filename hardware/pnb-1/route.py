"""Layout stage: freerouting round-trip + the few hand routes the autorouter cannot reach, then DRC.
Run after build.py. Idempotent: always starts from the freshly built (unrouted) board."""
import json, math, os, re, subprocess, sys
import pcbnew
from pcbnew import FromMM as mm

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "pnb-1.kicad_pcb")
DSN = os.path.join(HERE, "review", "pnb-1.dsn")
SES = os.path.join(HERE, "review", "pnb-1.ses")
FREEROUTING = os.environ.get("FREEROUTING", "freerouting")

def P(x, y): return pcbnew.VECTOR2I(mm(x), mm(y))


def sexp(text):
    """Minimal s-expression reader (SES files)."""
    tokens, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace(): i += 1
        elif c in "()": tokens.append(c); i += 1
        elif c == '"':
            j = text.index('"', i + 1); tokens.append(text[i + 1:j]); i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()": j += 1
            tokens.append(text[i:j]); i = j
    def parse(pos):
        out = []
        while pos < len(tokens):
            t = tokens[pos]
            if t == "(":
                sub, pos = parse(pos + 1); out.append(sub)
            elif t == ")":
                return out, pos + 1
            else:
                out.append(t); pos += 1
        return out, pos
    return parse(0)[0]


def import_ses(board, path, keep):
    """pcbnew.ImportSpecctraSES returns False outside the GUI; read the session ourselves."""
    tree = sexp(open(path).read())
    def find(node, tag):
        return [x for x in node if isinstance(x, list) and x and x[0] == tag]
    routes = find(tree[0] if isinstance(tree[0], list) else tree, "routes")[0]
    res = find(routes, "resolution")[0]  # (resolution um 10) -> 10 units per um
    per_unit = 1.0 / (float(res[2]) * 1000.0)  # -> mm
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    vias = {}
    for ps in find(find(routes, "library_out")[0], "padstack"):
        name = ps[1]; shape = find(ps, "shape")[0][1]  # (circle F.Cu 6000 0 0)
        vias[name] = float(shape[2]) * per_unit
    n_t = n_v = 0
    for net in find(find(routes, "network_out")[0], "net"):
        ni = board.FindNet(net[1])
        if ni is None:
            raise SystemExit(f"SES net {net[1]} not on board")
        for w in find(net, "wire"):
            path = find(w, "path")[0]
            layer, width = layers[path[1]], float(path[2]) * per_unit
            pts = [(float(path[i]) * per_unit, -float(path[i + 1]) * per_unit) for i in range(3, len(path), 2)]
            for a, b in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board); t.SetStart(P(*a)); t.SetEnd(P(*b)); t.SetWidth(mm(width)); t.SetLayer(layer); t.SetNet(ni)
                board.Add(t); t.thisown = False; keep.append(t); n_t += 1
        for v in find(net, "via"):
            dia = vias[v[1]]; x, y = float(v[2]) * per_unit, -float(v[3]) * per_unit
            pv = pcbnew.PCB_VIA(board); pv.SetPosition(P(x, y)); pv.SetWidth(mm(dia)); pv.SetDrill(mm(0.3)); pv.SetNet(ni)
            pv.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); board.Add(pv); pv.thisown = False; keep.append(pv); n_v += 1
    print(f"SES: {n_t} track segments, {n_v} vias")

# Hand routes the autorouter cannot place. ("track", net, layer, width_mm, [(x,y),...]) / ("via", net, x, y)
USB_DP_PATH = [(32.75, 35.43), (32.75, 34.5), (31.7, 33.45), (31.7, 32.0), (34.05, 30.15),
               (34.05, 27.85), (34.05, 26.0), (33.4, 26.0), (29.45, 23.0), (33.85, 20.0), (34.05, 20.0),
               (34.05, 15.85), (38.47, 15.85)]
USB_DN_PATH = [(33.25, 35.43), (33.25, 34.5), (33.6, 34.1), (35.0, 33.2),
               (35.0, 31.2), (36.8, 31.2), (36.8, 30.15), (35.95, 30.15),
               (35.95, 27.85), (36.8, 27.85), (36.8, 26.8), (34.55, 26.8),
               (34.55, 17.5), (35.2, 16.85), (36.25, 15.0), (38.47, 15.0)]

HAND = [
    # SCD41 supply escapes the package edge and wraps around the complete body;
    # no trace or via crosses the central sensing-opening rule area.
    ("track", "3V3", "F.Cu", 0.3, [(10.75, 16.0), (10.75, 17.5), (5.8, 17.5),
                                     (5.8, 6.5), (10.75, 6.5), (10.75, 8.0)]),
    ("track", "3V3", "F.Cu", 0.3, [(4.5, 8.0), (5.8, 8.0)]),
    # LDO tab thermal vias (3V3 pour both layers around U2 pad 4 at 24.5/35.5, tab 2.34 x 3.6)
    *[("via", "3V3", x, y) for (x, y) in [(43.1, 34.2), (42.5, 32.4), (46.9, 34.2), (46.9, 36.8), (45.0, 32.7)]],
    # GND vias in the module's 3x3 centre paddle so the B.Cu plane is tied under U1
    *[("via", "GND", x, y) for x in (43.85, 45.5, 47.15) for y in (13.35, 15.0, 16.65)],
    # SCD41 exposed GND pad 21: the datasheet requires this central pad at GND.
    ("via", "GND", 12.0, 12.0),
    # CC2 escape from the fine-pitch receptacle pad to its independent Rd.
    ("track", "CC2", "F.Cu", 0.15, [(34.75, 35.43), (34.75, 38.0), (39.0, 38.0), (39.0, 34.75)]),
]
USB_HAND = [
    # Coupled, via-free main pair from one orientation of the Type-C connector.
    ("track", "USB_DP", "F.Cu", 0.2, USB_DP_PATH[:8]),
    ("via", "USB_DP", 33.4, 26.0),
    ("track", "USB_DP", "B.Cu", 0.2, USB_DP_PATH[7:10]),
    ("via", "USB_DP", 33.85, 20.0),
    ("track", "USB_DP", "F.Cu", 0.2, USB_DP_PATH[9:]),
    ("track", "USB_DN", "F.Cu", 0.2, USB_DN_PATH[:3]),
    ("via", "USB_DN", 33.6, 34.1),
    ("track", "USB_DN", "B.Cu", 0.2, USB_DN_PATH[2:4]),
    ("via", "USB_DN", 35.0, 33.2),
    ("track", "USB_DN", "F.Cu", 0.2, USB_DN_PATH[3:14]),
    ("via", "USB_DN", 35.2, 16.85),
    ("track", "USB_DN", "B.Cu", 0.2, USB_DN_PATH[13:15]),
    ("via", "USB_DN", 36.25, 15.0),
    ("track", "USB_DN", "F.Cu", 0.2, USB_DN_PATH[14:]),
    # Duplicate receptacle contacts fan out on B.Cu to avoid crossing at the
    # connector. These are short branches, not layer changes in the main pair.
    ("track", "USB_DP", "F.Cu", 0.2, [(33.75, 35.43), (33.75, 36.5)]),
    ("via", "USB_DP", 33.75, 36.5),
    ("track", "USB_DP", "B.Cu", 0.2, [(33.75, 36.5), (31.8, 36.5), (31.8, 33.5), (32.8, 33.5)]),
    ("via", "USB_DP", 32.8, 33.5),
    ("track", "USB_DP", "F.Cu", 0.2, [(32.8, 33.5), (31.7, 33.45)]),
    ("track", "USB_DN", "F.Cu", 0.2, [(32.25, 35.43), (32.25, 37.2)]),
    ("via", "USB_DN", 32.25, 37.2),
    ("track", "USB_DN", "B.Cu", 0.2, [(32.25, 37.2), (35.2, 37.2), (35.2, 32.5)]),
    ("via", "USB_DN", 35.2, 32.5),
    ("track", "USB_DN", "F.Cu", 0.2, [(35.2, 32.5), (35.0, 32.5)]),
]
LAYERS = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}


def hand_segments():
    """Expand HAND into atomic items: ("t", net, layer, w, (x1,y1), (x2,y2)) and ("v", net, (x,y))."""
    out = []
    for h in HAND:
        if h[0] == "track":
            _, net, layer, w, pts = h
            out += [("t", net, layer, w, a, b) for a, b in zip(pts, pts[1:])]
        else:
            out.append(("v", h[1], (h[2], h[3])))
    return out


def segments(items):
    out = []
    for h in items:
        if h[0] == "track":
            _, net, layer, w, pts = h
            out += [("t", net, layer, w, a, b) for a, b in zip(pts, pts[1:])]
        else:
            out.append(("v", h[1], (h[2], h[3])))
    return out


def audit_usb_paths():
    """Mechanical high-speed constraint attached directly to the fixed paths."""
    def length(points):
        return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))
    dp, dn = length(USB_DP_PATH), length(USB_DN_PATH)
    if max(dp, dn) >= 32.0 or abs(dp - dn) > 1.0:
        raise SystemExit(f"USB pair constraint failed: D+={dp:.3f} mm D-={dn:.3f} mm skew={abs(dp-dn):.3f} mm")
    print(f"USB pair: D+={dp:.3f} mm, D-={dn:.3f} mm, skew={abs(dp-dn):.3f} mm; D+ two vias, D- four vias")


def add_item(board, item, keep):
    ni = board.FindNet(item[1])
    if item[0] == "t":
        _, net, layer, w, a, b = item
        t = pcbnew.PCB_TRACK(board); t.SetStart(P(*a)); t.SetEnd(P(*b)); t.SetWidth(mm(w)); t.SetLayer(LAYERS[layer]); t.SetNet(ni)
        board.Add(t); t.thisown = False; keep.append(t)
    else:
        x, y = item[2]
        v = pcbnew.PCB_VIA(board); v.SetPosition(P(x, y)); v.SetWidth(mm(0.5 if item[1].startswith("USB_") else 0.6)); v.SetDrill(mm(0.3)); v.SetNet(ni)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); board.Add(v); v.thisown = False; keep.append(v)


def hand_routes(board):
    keep = []
    for item in hand_segments() + segments(USB_HAND):
        add_item(board, item, keep)
    return keep


def replace_usb_routes(board):
    """Discard autorouted USB copper and install the audited pair plus branches."""
    for item in list(board.GetTracks()):
        if item.GetNetname() in ("USB_DP", "USB_DN"):
            board.Remove(item)
    for zone in list(board.Zones()):
        if zone.GetZoneName().startswith("TEMP_USB_CORRIDOR_"):
            board.Remove(zone)
    keep = []
    for item in segments(USB_HAND):
        add_item(board, item, keep)
    print(f"USB routes replaced: {len(keep)} fixed items")
    return keep


def ensure_hand_routes(board):
    """The router may drop or reshape pre-routed segments; re-add any hand segment/via that is missing."""
    have = set()
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            have.add(("v", t.GetPosition().x, t.GetPosition().y))
        else:
            s, e = t.GetStart(), t.GetEnd()
            have.add(("t", t.GetLayer(), s.x, s.y, e.x, e.y)); have.add(("t", t.GetLayer(), e.x, e.y, s.x, s.y))
    keep, n = [], 0
    for item in hand_segments():
        if item[0] == "v":
            key = ("v", P(*item[2]).x, P(*item[2]).y)
        else:
            a, b = P(*item[4]), P(*item[5]); key = ("t", LAYERS[item[2]], a.x, a.y, b.x, b.y)
        if key not in have:  # the router may have moved a stub; same-net overlap with what it kept is harmless
            add_item(board, item, keep); n += 1
    print(f"hand routes re-added: {n}")
    return keep


def via_islands(board, via_d=0.6):
    """After a fill, put a GND via inside every F.Cu/B.Cu GND pour island that has no via yet."""
    gnd = board.FindNet("GND")
    vias = [v for v in board.GetTracks() if isinstance(v, pcbnew.PCB_VIA)]
    keep, n = [], 0
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != "GND":
            continue
        for layer in z.GetLayerSet().Seq():
            polys = z.GetFilledPolysList(layer)
            for i in range(polys.OutlineCount()):
                outline = polys.Outline(i)
                if any(outline.PointInside(v.GetPosition()) for v in vias):
                    continue
                bb = outline.BBox()
                if bb.GetWidth() < mm(1.6) or bb.GetHeight() < mm(1.6):
                    continue
                # probe a small grid inside the bbox for a point with >= via radius+clearance of pour around it
                placed = False
                for fy in (0.5, 0.35, 0.65, 0.2, 0.8):
                    for fx in (0.5, 0.35, 0.65, 0.2, 0.8):
                        pt = pcbnew.VECTOR2I(int(bb.GetLeft() + fx * bb.GetWidth()), int(bb.GetTop() + fy * bb.GetHeight()))
                        if outline.PointInside(pt) and outline.Distance(pt) >= mm(via_d / 2 + 0.25):
                            v = pcbnew.PCB_VIA(board); v.SetPosition(pt); v.SetWidth(mm(via_d)); v.SetDrill(mm(0.3)); v.SetNet(gnd)
                            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); board.Add(v); v.thisown = False; keep.append(v); vias.append(v); n += 1
                            placed = True; break
                    if placed: break
    print(f"island vias: {n}")
    return keep

def stitch_gnd(board, pitch=3.0, margin=1.2, via_d=0.6, clearance=0.35):
    """GND stitching vias on a grid wherever nothing else is nearby: ties F.Cu pour islands to the B.Cu pour."""
    gnd = board.FindNet("GND")
    bb = board.GetBoardEdgesBoundingBox()
    x0, y0, x1, y1 = bb.GetLeft() / 1e6, bb.GetTop() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6
    r = via_d / 2 + clearance
    obstacles = []  # (left, top, right, bottom) in mm, already inflated
    for fp in board.GetFootprints():
        for p in fp.Pads():
            b = p.GetBoundingBox(); obstacles.append((b.GetLeft()/1e6 - r, b.GetTop()/1e6 - r, b.GetRight()/1e6 + r, b.GetBottom()/1e6 + r))
        c = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
        if c.GetWidth() > 0:
            obstacles.append((c.GetLeft()/1e6, c.GetTop()/1e6, c.GetRight()/1e6, c.GetBottom()/1e6))
    for t in board.GetTracks():
        b = t.GetBoundingBox(); obstacles.append((b.GetLeft()/1e6 - r, b.GetTop()/1e6 - r, b.GetRight()/1e6 + r, b.GetBottom()/1e6 + r))
    for z in board.Zones():
        if z.GetIsRuleArea():
            b = z.GetBoundingBox(); obstacles.append((b.GetLeft()/1e6 - r, b.GetTop()/1e6 - r, b.GetRight()/1e6 + r, b.GetBottom()/1e6 + r))
    keep, n = [], 0
    y = y0 + margin
    while y < y1 - margin:
        x = x0 + margin
        while x < x1 - margin:
            if not any(l <= x <= rr and t <= y <= bt for (l, t, rr, bt) in obstacles):
                v = pcbnew.PCB_VIA(board); v.SetPosition(P(x, y)); v.SetWidth(mm(via_d)); v.SetDrill(mm(0.3)); v.SetNet(gnd)
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); board.Add(v); v.thisown = False; keep.append(v); n += 1
            x += pitch
        y += pitch
    print(f"stitching vias: {n}")
    return keep


def prune_orphan_vias(board):
    """Remove GND vias whose pour island on BOTH layers touches no GND pad/track (they would be isolated copper)."""
    anchors = {pcbnew.F_Cu: [], pcbnew.B_Cu: []}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == "GND":
                for L in anchors:
                    if p.IsOnLayer(L): anchors[L].append(p.GetPosition())
    for t in board.GetTracks():
        if t.GetNetname() == "GND" and not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() in anchors:
            anchors[t.GetLayer()] += [t.GetStart(), t.GetEnd()]
    islands = {L: [] for L in anchors}
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != "GND": continue
        for L in z.GetLayerSet().Seq():
            if L not in islands: continue
            polys = z.GetFilledPolysList(L)
            for i in range(polys.OutlineCount()):
                o = polys.Outline(i)
                islands[L].append((o, any(o.PointInside(a) for a in anchors[L])))
    removed = 0
    for v in [t for t in board.GetTracks() if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == "GND"]:
        ok = False
        for L in islands:
            for o, anchored in islands[L]:
                if anchored and o.PointInside(v.GetPosition()): ok = True
        if not ok:
            board.Remove(v); removed += 1
    print(f"orphan vias removed: {removed}")


def patch_dsn(path):
    """KiCad's exporter ignores the pattern-assigned power netclass width and exports pre-routes as movable."""
    import re
    d = open(path).read().replace(HERE + os.sep, "")
    d = d.replace("(type route)", "(type fix)")  # pre-routes: the router must not move them
    def widen(m):
        return m.group(0).replace("(width 250)", "(width 500)")
    open(path, "w").write(d)
    print("DSN patched: pre-routes fixed")


def seg_dist(t, pt):
    """distance (IU) from point to track segment"""
    ax, ay, bx, by = t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y
    px, py = pt.x, pt.y
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    cx, cy = ax + u * dx, ay + u * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def widen_power(board, nets=("3V3", "VBUS"), wide=0.5, narrow=0.25, rounds=20, steps=(0.5, 0.4, 0.3, 0.25)):
    """Route at 0.25 mm, then widen power segments to 0.5 mm; DRC steps a colliding segment down one width at a time
    (0.5 -> 0.4 -> 0.3 -> 0.25) so trunks keep as much copper as the neighbours allow."""
    import json as _json, subprocess as _sp
    segs = [t for t in board.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() in nets]
    for t in segs:
        t.SetWidth(mm(wide))
    def step_down(t):
        cur = round(t.GetWidth() / 1e6, 3)
        for a, b_ in zip(steps, steps[1:]):
            if abs(cur - a) < 1e-6:
                t.SetWidth(mm(b_)); return True
        return False
    tmp = os.path.join(HERE, "review", "widen-tmp.kicad_pcb"); rep = os.path.join(HERE, "review", "widen-drc.json")
    reverted = 0
    for _ in range(rounds):
        pcbnew.ZONE_FILLER(board).Fill(board.Zones()); board.Save(tmp)
        _sp.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-error", "-o", rep, tmp], capture_output=True)
        d = _json.load(open(rep))
        hits = []
        for v in d["violations"]:
            for it in v["items"]:
                desc = it.get("description", "")
                if desc.startswith("Track [") and any(f"[{n}]" in desc for n in nets):
                    hits.append((it["pos"]["x"], it["pos"]["y"]))
        if not hits:
            break
        for (x, y) in hits:
            pt = P(x, y)
            best = min((t for t in segs if t.GetWidth() > mm(narrow)), key=lambda t: seg_dist(t, pt), default=None)
            if best is not None and seg_dist(best, pt) < mm(wide) and step_down(best):
                reverted += 1
    for f in (tmp, rep):
        if os.path.exists(f): os.remove(f)
    from collections import Counter as _C
    dist = _C()
    for t in segs:
        dist[round(t.GetWidth() / 1e6, 2)] += t.GetLength() / 1e6
    print("power track length by width (mm):", {w: round(l, 1) for w, l in sorted(dist.items(), reverse=True)}, f"({reverted} step-downs)")


def track_keys(board):
    have = set()
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            have.add(("v", t.GetPosition().x, t.GetPosition().y))
        else:
            s, e = t.GetStart(), t.GetEnd()
            have.add(("t", t.GetLayer(), s.x, s.y, e.x, e.y)); have.add(("t", t.GetLayer(), e.x, e.y, s.x, s.y))
    return have


def copy_tracks(src, dst, keep):
    for t in src.GetTracks():
        ni = dst.FindNet(t.GetNetname())
        if isinstance(t, pcbnew.PCB_VIA):
            v = pcbnew.PCB_VIA(dst); v.SetPosition(t.GetPosition()); v.SetWidth(t.GetWidth(pcbnew.F_Cu)); v.SetDrill(t.GetDrillValue()); v.SetNet(ni)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); dst.Add(v); v.thisown = False; keep.append(v)
        else:
            n = pcbnew.PCB_TRACK(dst); n.SetStart(t.GetStart()); n.SetEnd(t.GetEnd()); n.SetWidth(t.GetWidth()); n.SetLayer(t.GetLayer()); n.SetNet(ni)
            dst.Add(n); n.thisown = False; keep.append(n)


def router_pass(routed_board, passno):
    """Export a DSN with everything on routed_board fixed (GND as copper, no pours), run freerouting, return unrouted count."""
    src = pcbnew.LoadBoard(PCB)  # fresh, unrouted, with zones
    scratch = []
    copy_tracks(routed_board, src, scratch)
    for z in list(src.Zones()):
        if not z.GetIsRuleArea():
            src.Remove(z)
    pcbnew.ExportSpecctraDSN(src, DSN)
    del src
    patch_dsn(DSN)
    try:
        r = subprocess.run([FREEROUTING, "-de", DSN, "-do", SES, "-mp", "5", "-oit", "0"], capture_output=True, text=True, timeout=90,
                           env={**os.environ, "JAVA_TOOL_OPTIONS": "-Djava.awt.headless=true"})
    except subprocess.TimeoutExpired:
        print(f"router pass {passno}: timed out"); return -1
    residual = [l.strip() for l in r.stdout.splitlines() if l.startswith("    - ") or l.startswith("  Net")]
    done = [l for l in r.stdout.splitlines() if "session completed" in l]
    m = re.search(r"\((\d+) unrouted\)", done[-1]) if done else None
    unrouted = int(m.group(1)) if m else -1
    print(f"router pass {passno}: {unrouted} unrouted" + (" — " + "; ".join(residual) if residual else ""))
    return unrouted


def import_new(board, keep):
    """Import SES wires/vias that are not already on the board (fixed pre-routes come back in the SES too)."""
    have = track_keys(board)
    tmp = pcbnew.LoadBoard(PCB); scratch = []
    import_ses(tmp, SES, scratch)
    n = 0
    for t in tmp.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            key = ("v", t.GetPosition().x, t.GetPosition().y)
        else:
            s, e = t.GetStart(), t.GetEnd(); key = ("t", t.GetLayer(), s.x, s.y, e.x, e.y)
        if key in have:
            continue
        ni = board.FindNet(t.GetNetname())
        if isinstance(t, pcbnew.PCB_VIA):
            v = pcbnew.PCB_VIA(board); v.SetPosition(t.GetPosition()); v.SetWidth(t.GetWidth(pcbnew.F_Cu)); v.SetDrill(t.GetDrillValue()); v.SetNet(ni)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); board.Add(v); v.thisown = False; keep.append(v)
        else:
            x = pcbnew.PCB_TRACK(board); x.SetStart(t.GetStart()); x.SetEnd(t.GetEnd()); x.SetWidth(t.GetWidth()); x.SetLayer(t.GetLayer()); x.SetNet(ni)
            board.Add(x); x.thisown = False; keep.append(x)
        n += 1
    print(f"imported {n} new items")


def main():
    audit_usb_paths()
    cached_session = open(SES).read() if os.path.exists(SES) else None
    subprocess.run([sys.executable, os.path.join(HERE, "build.py")], check=True, capture_output=True)  # fresh, unrouted board
    # freerouting is nondeterministic and slows to a crawl with hundreds of fixed wires, so instead of
    # incremental passes: independent attempts on the fresh board, keep the best (pre-routes count as "unrouted" to it).
    best = (-1, "validated committed session", cached_session) if cached_session else None
    if os.environ.get("PNB_ROUTE_REGENERATE") == "1" or not cached_session:
        best = None
        for attempt in range(1, 4):
            b = pcbnew.LoadBoard(PCB)
            keep = hand_routes(b)
            unrouted = router_pass(b, attempt)
            if unrouted < 0:
                continue
            if best is None or unrouted < best[0]:
                best = (unrouted, attempt, open(SES).read())
            if unrouted <= 15:
                break
    if best is None and cached_session:
        best = (-1, "committed-session fallback", cached_session)
    if best is None:
        sys.exit("router never finished and no validated session is available")
    open(SES, "w").write(best[2])
    print(f"using attempt {best[1]} ({best[0]} reported unrouted)")
    b = pcbnew.LoadBoard(PCB)
    keep = hand_routes(b)
    import_new(b, keep)
    keep += ensure_hand_routes(b)
    keep += replace_usb_routes(b)
    # Add these only after autorouting: they ground front-pour pockets without
    # constraining the router's already crowded ESP32 escape channels.
    for item in [("v", "GND", (31.0, 8.6))]:
        add_item(b, item, keep)
    widen_power(b)
    keep += stitch_gnd(b)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    keep += via_islands(b)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    prune_orphan_vias(b)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    rep = os.path.join(HERE, "review", "drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-error", "-o", rep, PCB], capture_output=True)
    d = json.load(open(rep))
    print(f"DRC: {len(d['violations'])} errors, {len(d['unconnected_items'])} unconnected")
    for v in d["violations"][:15]:
        print(" -", v["type"], v["description"][:60], "|", " ; ".join(i.get("description", "")[:45] for i in v["items"]))
    for u in d["unconnected_items"][:10]:
        print(" - unconnected:", " ; ".join(i.get("description", "")[:45] for i in u["items"]))
    return 1 if d["violations"] or d["unconnected_items"] else 0


if __name__ == "__main__":
    sys.exit(main())
