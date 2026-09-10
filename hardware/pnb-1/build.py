"""Build pnb-1.kicad_pcb from the standard KiCad netlist (pnb-1.net).

Standardized flow: pnb1_skidl.py (SKiDL, named pins, typed ERC) exports the
netlist and proves equivalence vs reference/revA; this script instantiates the
board through KiCad's official pcbnew API (kinet2pcb's parser reads the
netlist), applies the PLACE table, outline, holes, zones and silk. Routing:
route.py (freerouting). Gates + fab outputs: kibot (pnb-1.kibot.yaml).

Run from hardware/pnb-1:  ../.venv/bin/python build.py
"""
import csv
import os
import subprocess
import sys
from collections import defaultdict

import pcbnew
from pcbnew import FromMM as mm
from kinet2pcb import parse_netlist
from simp_sexp import Sexp

HERE = os.path.dirname(os.path.abspath(__file__))
LIBDIR = os.path.join(HERE, "lib", "artera.pretty")
NET = os.path.join(HERE, "pnb-1.net")
OUT = os.path.join(HERE, "pnb-1.kicad_pcb")
BOARD, REV = "PNB-1", "A"
W, H = 58.0, 42.0  # mm

def P(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))

# ref: (x, y, rotation deg)  — origin top-left, y down. Data, not a format:
# consumed only by the official SetPosition/SetOrientationDegrees calls below.
PLACE = {
    "J1": (11.0, 37.9, 0), "D1": (11.0, 31.5, 0), "R3": (5.5, 34.0, 90), "R4": (15.2, 31.6, 0),
    "C8": (19.5, 37.0, 90), "C2": (22.5, 37.0, 90), "U2": (27.5, 35.5, 0), "C3": (32.5, 37.0, 90), "C9": (35.5, 37.0, 90),
    "U1": (45.5, 15.0, 270), "C1": (49.75, 5.2, 90), "C11": (47.4, 4.9, 90), "R1": (35.5, 15.5, 90), "C6": (35.5, 19.5, 90), "R2": (35.5, 25.5, 90), "R10": (38.5, 29.0, 90),
    "U3": (12.0, 12.0, 0), "C4": (8.9, 18.7, 270), "C10": (12.9, 5.3, 90),
    "U4": (27.0, 5.5, 0), "C5": (23.5, 5.0, 90), "R7": (30.5, 5.0, 90), "C7": (30.5, 9.0, 90),
    "R5": (25.0, 13.0, 90), "R6": (28.0, 13.0, 90),
    "J4": (3.0, 24.0, 90), "SW1": (23.0, 23.5, 0), "SW2": (31.0, 23.5, 0),
    "J3": (44.0, 37.5, 0), "R8": (30.0, 29.0, 0), "LED1": (34.0, 29.0, 0), "R9": (30.0, 32.0, 0), "LED2": (34.0, 32.0, 0),
}
HOLES = [(3, 3), (W - 3, 3), (3, H - 3), (W - 3, H - 3)]


def comp_fields(net_path):
    """{ref: {field name: value}} from the netlist's (fields ...) blocks."""
    out = {}
    for comp in Sexp(open(net_path).read()).search("export/components/comp"):
        ref = comp.search("ref").value
        out[ref] = {f[1][1]: (f[2] if len(f) > 2 else "")
                    for f in comp.search("fields/field")}
    return out


def main():
    # Gate 1: regenerate the netlist from the canonical SKiDL source — its ERC
    # and rev A netlist-equivalence check must pass or we stop here.
    r = subprocess.run([sys.executable, os.path.join(HERE, "pnb1_skidl.py")], cwd=HERE)
    if r.returncode:
        sys.exit("pnb1_skidl.py failed (ERC or netlist equivalence) — not building")

    netlist = parse_netlist(NET)
    fields = comp_fields(NET)

    board = pcbnew.BOARD()
    keep = []  # python refs to objects the board now owns (else SWIG frees them -> segfault)

    def add(item):
        board.Add(item); item.thisown = False; keep.append(item); return item
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(mm(0.2)); nc.SetTrackWidth(mm(0.25)); nc.SetViaDiameter(mm(0.6)); nc.SetViaDrill(mm(0.3))
    power = pcbnew.NETCLASS("power"); power.SetClearance(mm(0.2)); power.SetTrackWidth(mm(0.5)); power.SetViaDiameter(mm(0.8)); power.SetViaDrill(mm(0.4))
    ds.m_NetSettings.GetNetclasses()["power"] = power
    for net in ("3V3", "VBUS"):
        ds.m_NetSettings.SetNetclassPatternAssignment(net, "power")
    ds.m_MinClearance = mm(0.09)  # USB-C receptacle pad pitch; JLC makes this part on 2-layer boards; ds.m_TrackMinWidth = mm(0.15); ds.m_ViasMinSize = mm(0.5); ds.m_MinThroughDrill = mm(0.3)

    # footprints from the netlist
    fps = {}
    for part in netlist.parts:
        ref = part.ref
        libname, fpname = part.footprint.split(":")
        fp = pcbnew.FootprintLoad(LIBDIR, fpname)
        if fp is None:
            sys.exit(f"footprint {fpname} not found for {ref}")
        fp.SetReference(ref); fp.SetValue(part.value)
        fp.Value().SetVisible(False)
        fp.Reference().SetLayer(pcbnew.F_Fab); fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.7), mm(0.7)))
        for item in list(fp.GraphicalItems()):  # easyeda footprints carry value/name texts on silk
            if item.Type() == pcbnew.PCB_TEXT_T and item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                fp.Remove(item)
            elif item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and item.GetWidth() < mm(0.15):
                item.SetWidth(mm(0.15))  # JLCPCB drops silk thinner than 0.153 mm
        for field in fp.GetFields():
            if field.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and field is not fp.Reference():
                field.SetVisible(False)
        if ref == "J1":
            for p in fp.Pads():
                if p.GetNumber() == "":
                    p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); p.SetNumber("PEG")
                p.SetLocalClearance(mm(0.09))  # receptacle pad pitch is tighter than the board rule; JLC basic part
        for fname in ("LCSC Part #", "MPN", "Description"):
            if fields.get(ref, {}).get(fname):
                fp.SetField(fname, fields[ref][fname])
        for f in fp.GetFields():  # new fields default to visible on silk
            if f.GetName() in ("LCSC Part #", "MPN", "Description"):
                f.SetVisible(False); f.SetLayer(pcbnew.F_Fab)
        add(fp); fps[ref] = fp

    # nets from the netlist
    for net in netlist.nets:
        ni = add(pcbnew.NETINFO_ITEM(board, net.name))
        for pin in net.pins:
            for p in fps[pin.ref].Pads():
                if p.GetNumber() == pin.num:
                    p.SetNet(ni)

    # outline
    corners = [(0, 0), (W, 0), (W, H), (0, H)]
    for i in range(4):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*corners[i])); s.SetEnd(P(*corners[(i + 1) % 4])); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); add(s)

    # mounting holes (NPTH 2.7 mm for M2.5)
    for i, (x, y) in enumerate(HOLES):
        fp = pcbnew.FOOTPRINT(board); fp.SetReference(f"H{i+1}"); fp.SetValue("M2.5")
        fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        pad = pcbnew.PAD(fp); pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH); pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetSize(pcbnew.VECTOR2I(mm(2.7), mm(2.7))); pad.SetDrillSize(pcbnew.VECTOR2I(mm(2.7), mm(2.7)))
        ls = pcbnew.LSET()
        for L in (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.F_Mask, pcbnew.B_Mask):
            ls.addLayer(L)
        pad.SetLayerSet(ls)
        fp.Add(pad); pad.thisown = False; add(fp); fp.SetPosition(P(x, y))
        fp.Reference().SetVisible(False)

    # placement
    for ref, (x, y, rot) in PLACE.items():
        fps[ref].SetPosition(P(x, y)); fps[ref].SetOrientationDegrees(rot)
    missing = set(fps) - set(PLACE)
    if missing:
        sys.exit(f"unplaced: {missing}")

    def silk(text, x, y, size=0.8, rot=0):
        t = pcbnew.PCB_TEXT(board); t.SetText(text); t.SetPosition(P(x, y)); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(0.15)); t.SetTextAngleDegrees(rot); add(t)
    silk("BOOT", 23.0, 20.6); silk("RESET", 31.0, 20.6); silk("UART 3V3 TX RX GND", 6.5, 24.0, 0.8, 90)
    silk("J3: 5V G 3V3 G SDA SCL A B AD1 AD2 C INT", 44.0, 33.6, 0.8)
    silk("USB-C", 11.0, 33.9, 0.8); silk("SCD41", 12.0, 18.2, 0.8); silk("BH1750", 27.0, 2.2, 0.8)
    # silkscreen title
    t = pcbnew.PCB_TEXT(board); t.SetText(f"{BOARD} rev {REV} artera.space"); t.SetPosition(P(29, 27.5))
    t.SetLayer(pcbnew.F_SilkS); t.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0))); t.SetTextThickness(mm(0.15)); add(t)

    # GND pours both layers, with an antenna keep-out on the module's antenna end (x > W-4.5)
    gnd = board.FindNet("GND")
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNet(gnd)
        z.Outline().NewOutline()
        for (x, y) in [(0.5, 0.5), (W - 5.2, 0.5), (W - 5.2, H - 0.5), (0.5, H - 0.5)]:
            z.Outline().Append(mm(x), mm(y))
        z.SetLocalClearance(mm(0.25)); z.SetMinThickness(mm(0.25)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)  # reflow assembly; solid ties keep GND pads out of pour islands
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)  # GND is routed as copper; pours only add area
        z.SetIsFilled(True); add(z)
    # LDO thermal: 3V3 copper on both layers around U2's tab (pad 4 at 24.5/35.5), tied with vias in route.py
    v3 = board.FindNet("3V3")
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNet(v3); z.Outline().NewOutline()
        for (x, y) in [(17.5, 30.0), (28.0, 30.0), (28.0, 41.2), (17.5, 41.2)]:
            z.Outline().Append(mm(x), mm(y))
        z.SetLocalClearance(mm(0.25)); z.SetMinThickness(mm(0.25)); z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS); z.SetAssignedPriority(1); z.SetIsFilled(True); add(z)
    ko = pcbnew.ZONE(board); ko.SetIsRuleArea(True); ko.SetDoNotAllowZoneFills(True); ko.SetDoNotAllowTracks(True); ko.SetDoNotAllowVias(True)
    ko.SetLayerSet(pcbnew.LSET.AllCuMask()); ko.Outline().NewOutline()
    for (x, y) in [(W - 4.6, 5), (W + 3, 5), (W + 3, 25), (W - 4.6, 25)]:
        ko.Outline().Append(mm(x), mm(y))
    add(ko)
    board.Save(OUT)
    # zone fill segfaults on a fresh BOARD(); reload the saved file and fill there
    b2 = pcbnew.LoadBoard(OUT)
    pcbnew.ZONE_FILLER(b2).Fill(b2.Zones())
    b2.Save(OUT)
    print("saved", os.path.basename(OUT))

    # JLCPCB BOM, grouped from the netlist's own fields (KiBot's bom output
    # needs a schematic, which this flow does not have)
    groups = defaultdict(list)
    for part in netlist.parts:
        f = fields.get(part.ref, {})
        groups[(part.value, part.footprint.split(":")[1], f.get("LCSC Part #", ""))].append(part.ref)
    os.makedirs(os.path.join(HERE, "fab"), exist_ok=True)
    with open(os.path.join(HERE, "fab", "bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (val, fpname, lcsc), refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
            refs.sort(key=lambda r: (r.rstrip("0123456789"), int(r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ") or 0)))
            w.writerow([val, ",".join(refs), fpname, lcsc])
    print("wrote fab/bom.csv")


if __name__ == "__main__":
    main()
