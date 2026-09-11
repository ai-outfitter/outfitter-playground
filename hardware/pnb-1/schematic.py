"""PNB-1 Pod Node Base — schematic as code.

Parts, nets and the electrical rule checks live here. `build.py` turns this
into a KiCad board; `release.py` turns the board into a fab package.
Requirements: docs/hardware/pnb-1.md. Contract:
docs/hardware/pod-node-contract.md.
"""
from collections import defaultdict

BOARD = "PNB-1"
REV = "A"
LIB = "artera"  # lib/artera.pretty, pulled from LCSC with easyeda2kicad

# ref: (footprint, value, LCSC, MPN, description)
PARTS = {
    "U1": ("BULETM-SMD_ESP32-S3-MINI-1-N8", "ESP32-S3-MINI-1-N8", "C2913206", "ESP32-S3-MINI-1-N8", "Wi-Fi/BLE module, 8 MB flash, PCB antenna"),
    "U2": ("SOT-223-3_L6.5-W3.4-P2.30-LS7.0-BR", "AMS1117-3.3", "C6186", "AMS1117-3.3", "3.3 V 1 A LDO"),
    "U3": ("LGA-20_L10.1-W10.1-P1.25-TL_SCD41-D-R2", "SCD41-D-R2", "C3659294", "SCD41-D-R2", "CO2/T/RH sensor, I2C 0x62"),
    "U4": ("WSOF-6_L2.6-W1.6-P0.50-TL-EP", "BH1750FVI-TR", "C78960", "BH1750FVI-TR", "ambient light sensor, I2C 0x23"),
    "D1": ("SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL", "USBLC6-2SC6", "C2687116", "USBLC6-2SC6", "USB ESD array"),
    "J1": ("USB-C_SMD-TYPE-C-31-M-12_1", "USB-C 16P", "C165948", "TYPE-C-31-M-12", "USB-C receptacle USB 2.0"),
    "J3": ("HDR-TH_12P-P2.54-V-M-R2-C6-S2.54", "DTR 2x6 DNP", "DNP", "DNP", "optional hand-installed daughter header (contract J3)"),
    "J4": ("HDR-TH_4P-P2.54-V-M", "UART 1x4", "C124378", "B-2100S04P-A110", "UART0 header 3V3/TX/RX/GND"),
    "SW1": ("SW-SMD_L3.9-W3.0-P4.45", "BOOT", "C720477", "TS-1088-AR02016", "tactile"),
    "SW2": ("SW-SMD_L3.9-W3.0-P4.45", "RESET", "C720477", "TS-1088-AR02016", "tactile"),
    "R1": ("R0603", "10k", "C25804", "0603WAF1002T5E", "EN pull-up"),
    "R2": ("R0603", "10k", "C25804", "0603WAF1002T5E", "IO0 pull-up"),
    "R3": ("R0603", "5.1k", "C23186", "0603WAF5101T5E", "CC1 Rd"),
    "R4": ("R0603", "5.1k", "C23186", "0603WAF5101T5E", "CC2 Rd"),
    "R5": ("R0603", "4.7k", "C23162", "0603WAF4701T5E", "SDA pull-up"),
    "R6": ("R0603", "4.7k", "C23162", "0603WAF4701T5E", "SCL pull-up"),
    "R7": ("R0603", "1k", "C21190", "0603WAF1001T5E", "BH1750 DVI"),
    "R8": ("R0603", "330R", "C23138", "0603WAF3300T5E", "power LED (red, Vf 2 V, ~4 mA)"),
    "R9": ("R0603", "330R", "C23138", "0603WAF3300T5E", "user LED"),
    "R10": ("R0603", "10k", "C25804", "0603WAF1002T5E", "DTR_INT pull-up (contract: open-drain)"),
    "C1": ("C0603", "100nF", "C14663", "CC0603KRX7R9BB104", "U1 3V3 decoupling"),
    "C2": ("C0603", "100nF", "C14663", "CC0603KRX7R9BB104", "U2 VIN decoupling"),
    "C3": ("C0603", "100nF", "C14663", "CC0603KRX7R9BB104", "U2 VOUT decoupling"),
    "C4": ("C0603", "100nF", "C14663", "CC0603KRX7R9BB104", "U3 VDD decoupling"),
    "C5": ("C0603", "100nF", "C14663", "CC0603KRX7R9BB104", "U4 VCC decoupling"),
    "C6": ("C0603", "1uF", "C15849", "CL10A105KB8NNNC", "EN RC"),
    "C7": ("C0603", "1uF", "C15849", "CL10A105KB8NNNC", "BH1750 DVI"),
    "C8": ("C0805", "10uF", "C15850", "CL21A106KAYNNNE", "VBUS bulk"),
    "C9": ("CASE-A_3216", "22uF tantalum", "C11366", "TAJA226K010RNJ", "U2 VOUT stability capacitor, 10 V, 3 ohm ESR"),
    "C11": ("C0805", "10uF", "C15850", "CL21A106KAYNNNE", "U1 3V3 bulk at the module"),
    "C10": ("C0805", "10uF", "C15850", "CL21A106KAYNNNE", "U3 VDD bulk (205 mA maximum)"),
    "LED1": ("LED-SMD_L1.6-W0.8-R-RD", "PWR", "C2286", "KT-0603R", "red 0603, 3V3 present"),
    "LED2": ("LED-SMD_L1.6-W0.8-R-RD", "USER", "C2286", "KT-0603R", "red 0603, GPIO21"),
}
DNP = {"J3"}

# Symbol pin numbers (from lib/artera.kicad_sym, verified against datasheets):
# U1 ESP32-S3-MINI-1: GND 1,2,42,43,46-60,+paddle 'GND'; 3V3 3; IO0 4; IO1 5; IO2 6; IO3 7;
#   IO4 8; IO5 9; IO6 10; IO7 11; IO8 12; IO9 13; IO10 14; ... IO19 23; IO20 24; IO21 25;
#   TXD0 39; RXD0 40; IO45 41; IO46 44; EN 45
# U2 AMS1117: GND 1, VOUT 2, VIN 3, VOUT(tab) 4
# U3 SCD41: VDD 7, VDDH 19, SCL 9, SDA 10, GND 6,20; DNC 1-5,8,11-18
# U4 BH1750: VCC 1, ADDR 2, GND 3, SDA 4, DVI 5, SCL 6, EP 7
# D1 USBLC6: I/O1 1&6, GND 2, I/O2 3&4, VBUS 5
# J1 USB-C: A1B12/B1A12 GND, A4B9/B4A9 VBUS, A5 CC1, B5 CC2, A6/B6 D+, A7/B7 D-, A8/B8 SBU, 1-4 + '' shell
# LED KT-0603R: A 1, K 2  (the green C72043 it replaced was A 2, C 1)

ESP_GND = ["1", "2", "42", "43"] + [str(n) for n in range(46, 61)] + ["GND"]

NETS = {
    "GND": [("U1", p) for p in ESP_GND] + [
        ("U2", "1"), ("U3", "6"), ("U3", "20"), ("U4", "3"), ("U4", "2"), ("U4", "7"),
        ("D1", "2"), ("J1", "A1B12"), ("J1", "B1A12"), ("J1", "1"), ("J1", "2"), ("J1", "3"), ("J1", "4"),
        ("J3", "2"), ("J3", "4"), ("J4", "4"), ("SW1", "2"), ("SW2", "2"),
        ("R3", "2"), ("R4", "2"),
        ("C1", "2"), ("C2", "2"), ("C3", "2"), ("C4", "2"), ("C5", "2"), ("C6", "2"), ("C7", "2"),
        ("C8", "2"), ("C9", "2"), ("C10", "2"), ("C11", "2"), ("LED1", "2"), ("LED2", "2"),
    ],
    "VBUS": [("J1", "A4B9"), ("J1", "B4A9"), ("U2", "3"), ("C8", "1"), ("C2", "1"), ("D1", "5")],
    "3V3": [("U2", "2"), ("U2", "4"), ("C3", "1"), ("C9", "1"), ("U1", "3"), ("C1", "1"), ("C11", "1"),
            ("R1", "1"), ("R2", "1"), ("R5", "1"), ("R6", "1"), ("R7", "1"), ("R8", "1"), ("R10", "1"),
            ("U3", "7"), ("U3", "19"), ("C4", "1"), ("C10", "1"), ("U4", "1"), ("C5", "1"),
            ("J3", "3"), ("J4", "1")],
    "USB_DP": [("J1", "A6"), ("J1", "B6"), ("D1", "1"), ("D1", "6"), ("U1", "24")],
    "USB_DN": [("J1", "A7"), ("J1", "B7"), ("D1", "3"), ("D1", "4"), ("U1", "23")],
    "CC1": [("J1", "A5"), ("R3", "1")],
    "CC2": [("J1", "B5"), ("R4", "1")],
    "EN": [("U1", "45"), ("R1", "2"), ("C6", "1"), ("SW2", "1")],
    "IO0": [("U1", "4"), ("R2", "2"), ("SW1", "1")],
    "SDA": [("U1", "9"), ("R5", "2"), ("U3", "10"), ("U4", "4"), ("J3", "5")],
    "SCL": [("U1", "10"), ("R6", "2"), ("U3", "9"), ("U4", "6"), ("J3", "6")],
    "DVI": [("U4", "5"), ("R7", "2"), ("C7", "1")],
    "LED_PWR": [("R8", "2"), ("LED1", "1")],
    "IO21": [("U1", "25"), ("R9", "1")],
    "LED_USER": [("R9", "2"), ("LED2", "1")],
    "TXD0": [("U1", "39"), ("J4", "2")],
    "RXD0": [("U1", "40"), ("J4", "3")],
    "DTR_GPIOA": [("U1", "11"), ("J3", "7")],   # IO7
    "DTR_GPIOB": [("U1", "12"), ("J3", "8")],   # IO8
    "DTR_ADCA": [("U1", "8"), ("J3", "9")],     # IO4
    "DTR_ADCB": [("U1", "13"), ("J3", "10")],   # IO9
    "DTR_GPIOC": [("U1", "14"), ("J3", "11")],  # IO10
    "DTR_INT": [("U1", "5"), ("J3", "12"), ("R10", "2")],  # IO1, pulled up on the base
}

# Deliberately unconnected pins (reason).
NC = {
    ("U1", "6"): "IO2 spare", ("U1", "7"): "IO3 strapping (JTAG sel) — float",
    ("U1", "41"): "IO45 strapping (VDD_SPI) — float", ("U1", "44"): "IO46 strapping — float",
    ("J1", "A8"): "SBU1 unused", ("J1", "B8"): "SBU2 unused", ("J1", "PEG"): "USB-C locating pegs, NPTH",
    ("J3", "1"): "reserved; raw USB VBUS is not exported by this revision",
}
for n in list(range(15, 23)) + list(range(26, 39)):
    NC[("U1", str(n))] = "spare GPIO"
for n in [1, 2, 3, 4, 5, 8] + list(range(11, 19)):
    NC[("U3", str(n))] = "SCD41 DNC"

I2C_ADDRESSES = {"U3": 0x62, "U4": 0x23}


def erc(pad_names):
    """pad_names: {ref: [pad numbers from the footprint]}. Returns list of problems."""
    problems = []
    used = defaultdict(list)
    for net, pins in NETS.items():
        if len(pins) < 2:
            problems.append(f"net {net} has {len(pins)} pin(s)")
        for ref, pad in pins:
            if ref not in PARTS:
                problems.append(f"{net}: unknown ref {ref}")
            elif pad not in pad_names[ref]:
                problems.append(f"{net}: {ref} has no pad '{pad}'")
            used[(ref, pad)].append(net)
    for key, nets in used.items():
        if len(nets) > 1:
            problems.append(f"{key} in several nets: {nets}")
    for ref, pads in pad_names.items():
        for pad in pads:
            if (ref, pad) not in used and (ref, pad) not in NC:
                problems.append(f"{ref}.{pad} unconnected and not in NC")
    for key in NC:
        if key in used:
            problems.append(f"{key} listed NC but connected to {used[key]}")
    addrs = list(I2C_ADDRESSES.values())
    if len(set(addrs)) != len(addrs):
        problems.append("duplicate I2C address")
    return problems


def bom_rows():
    groups = defaultdict(list)
    for ref, (fp, val, lcsc, mpn, desc) in PARTS.items():
        if ref in DNP:
            continue
        groups[(val, fp, lcsc, mpn)].append(ref)
    rows = []
    for (val, fp, lcsc, mpn), refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
        rows.append({"Comment": val, "Designator": ",".join(sorted(refs, key=lambda r: (r.rstrip("0123456789"), int(r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))))),
                     "Footprint": fp, "LCSC Part #": lcsc, "MPN": mpn, "Qty": len(refs)})
    return rows


def net_table():
    lines = ["| net | pins |", "| --- | --- |"]
    for net, pins in NETS.items():
        lines.append(f"| {net} | " + ", ".join(f"{r}.{p or 'shell'}" for r, p in pins) + " |")
    lines += ["", "## Not connected", "", "| pin | reason |", "| --- | --- |"]
    for (r, p), why in sorted(NC.items()):
        lines.append(f"| {r}.{p} | {why} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Verification data (consumed by verify.py). Three independence layers:
#   1. self-consistency  — erc() + KiCad ERC over NETS/PIN_TYPES (same author)
#   2. independent       — EXPECT: pad numbers vs EasyEDA's pin names in the lib
#   3. numeric margins   — margins(): plain-Python asserts over MARGIN_PARAMS
# None of this is proof; it is what open-source tooling can check mechanically.

# ref -> symbol name in lib/<LIB>.kicad_sym (easyeda2kicad names symbols by MPN
# or by its own catalog name; check with grep '(symbol "').
SYMBOLS = {
    "U1": "ESP32-S3-MINI-1-N8", "U2": "AMS1117-3.3", "U3": "SCD41-D-R2", "U4": "BH1750FVI-TR",
    "D1": "USBLC6-2SC6_C2687116", "J1": "TYPE-C-31-M-12", "J3": "Header-Male-2.54_2x6",
    "J4": "Header-Male-2.54_1x4", "SW1": "TS-1088-AR02016", "SW2": "TS-1088-AR02016",
    "LED1": "KT-0603R", "LED2": "KT-0603R",
    "C9": "TAJA226K010RNJ",
}
for _r, (_fp, _v, _lcsc, _mpn, _d) in PARTS.items():
    SYMBOLS.setdefault(_r, _mpn)

# KiCad electrical pin types by (ref, pad). easyeda2kicad symbols are almost all
# "unspecified", which makes KiCad ERC blind — so the designer declares them.
# Unlisted pads are "passive". Ganged pins (LDO tab, USB-C paired pads) get one
# power_out and the rest passive, or ERC flags power_out↔power_out.
PIN_TYPES = {
    "U1": {**{p: "power_in" for p in ESP_GND}, "3": "power_in", "45": "input",
           "39": "output", "40": "input", "23": "bidirectional", "24": "bidirectional",
           **{str(n): "bidirectional" for n in range(4, 39)}},
    "U2": {"1": "power_in", "2": "power_out", "3": "power_in", "4": "passive"},
    "U3": {"7": "power_in", "19": "power_in", "9": "input", "10": "bidirectional",
           "6": "power_in", "20": "power_in"},
    "U4": {"1": "power_in", "2": "input", "3": "power_in", "4": "bidirectional",
           "5": "input", "6": "input", "7": "power_in"},
    "D1": {"2": "power_in", "5": "power_in"},
    "J1": {"A4B9": "power_out", "B4A9": "passive", "A1B12": "power_out", "B1A12": "passive"},
    "C9": {"1": "passive", "2": "passive"},
}

# Independent cross-check: for each net, the pin NAME the lib symbol must carry
# on the pad we connected (regex). Only ICs/connectors carry meaningful names.
EXPECT = {
    "3V3": {"U1": r"3V3|VDD|VCC", "U2": r"VOUT", "U3": r"VDD", "U4": r"VCC", "C9": r"^1$"},
    "GND": {"U1": r"GND", "U2": r"GND", "U3": r"GND", "U4": r"GND|ADDR|EP", "D1": r"GND",
            "J1": r"GND|^EH$", "C9": r"^2$"},  # EH = USB-C shell pads, legitimately on GND
    "VBUS": {"U2": r"VIN", "D1": r"VBUS", "J1": r"VBUS"},
    "USB_DP": {"U1": r"IO20|D\+", "D1": r"I/?O1", "J1": r"D\+|DP"},
    "USB_DN": {"U1": r"IO19|D-", "D1": r"I/?O2", "J1": r"D-|DN"},
    "SDA": {"U1": r"IO5", "U3": r"SDA", "U4": r"SDA"}, "SCL": {"U1": r"IO6", "U3": r"SCL", "U4": r"SCL"},
    "EN": {"U1": r"^EN"}, "IO0": {"U1": r"IO0$"}, "TXD0": {"U1": r"TXD0|IO43"}, "RXD0": {"U1": r"RXD0|IO44"},
    "IO21": {"U1": r"IO21"}, "DVI": {"U4": r"DVI"}, "CC1": {"J1": r"CC1"}, "CC2": {"J1": r"CC2"},
    "DTR_GPIOA": {"U1": r"IO7$"}, "DTR_GPIOB": {"U1": r"IO8$"}, "DTR_ADCA": {"U1": r"IO4$"},
    "DTR_ADCB": {"U1": r"IO9$"}, "DTR_GPIOC": {"U1": r"IO10$"}, "DTR_INT": {"U1": r"IO1$"},
}

# Numeric margins — the tier ERC cannot see. Values from datasheets / requirements.
MARGIN_PARAMS = {
    "vbus": 5.0, "vbus_min": 4.75, "v3v3": 3.3,       # USB 2.0 spec: 4.75–5.25 V at the device
    "ldo_dropout": 1.1,            # AMS1117 max at 1 A
    "ldo_theta_ja": 136.0,         # °C/W conservative no-heatsink bound; copper and vias may only improve it
    "t_ambient_max": 50.0, "t_junction_max": 125.0,
    "rail_peak_ma": {"U1": 350, "U3": 205, "U4": 1, "LED1": 4, "LED2": 4, "pullups": 3, "J3": 50},
    "ldo_i_max_ma": 1000,
    # Thermal is computed at the controlled SUSTAINED current, not coincident
    # peaks. At 617 mA this model gives 193 C and explicitly fails; firmware must
    # prevent sustained coincidence until prototype measurement replaces the
    # assumed theta-JA bound.
    "rail_sustained_ma": 200,
    "led": {"LED1": ("R8", 2.0, 1, 20), "LED2": ("R9", 2.0, 1, 20)},  # (series R, Vf, Imin mA, Imax mA)
    "i2c": {"pullups": ("R5", "R6"), "min_ohm": 1000, "max_ohm": 10000},   # 400 kHz, ~100 pF bus
    "esp_strap_pullup_max": 100e3,
}

# Parameters whose value comes from an accepted waiver, not a datasheet.
WAIVERS = {
    "ldo_theta_ja": "136 C/W pre-prototype engineering bound; retire with thermocouple measurement at 5 V, 200 mA, and 50 C ambient",
    "rail_sustained_ma": "firmware-enforced 200 mA sustained limit; verify on the assembled prototype before functional release",
}

def _ohms(ref):
    v = PARTS[ref][1].lower().replace("ω", "").replace("r", "")
    return float(v.replace("k", "")) * (1e3 if "k" in v else 1)

def margins(p=MARGIN_PARAMS):
    """Plain-Python asserts in the atopile style. Returns problems (empty = pass)."""
    out = []
    i_rail = sum(p["rail_peak_ma"].values())
    if i_rail > p["ldo_i_max_ma"]:
        out.append(f"3V3 peak {i_rail} mA exceeds LDO {p['ldo_i_max_ma']} mA")
    if p["vbus_min"] - p["ldo_dropout"] < p["v3v3"]:
        out.append(f"LDO dropout: VBUS_min {p['vbus_min']} − {p['ldo_dropout']} < 3V3")
    pd = (p["vbus"] - p["v3v3"]) * p["rail_sustained_ma"] / 1000
    tj = p["t_ambient_max"] + pd * p["ldo_theta_ja"]
    if tj > p["t_junction_max"]:
        out.append(f"LDO Tj {tj:.0f} °C at {pd:.2f} W (sustained {p['rail_sustained_ma']} mA) exceeds {p['t_junction_max']} °C")
    for led, (r, vf, imin, imax) in p["led"].items():
        i = (p["v3v3"] - vf) / _ohms(r) * 1000
        if not imin <= i <= imax:
            out.append(f"{led}: {i:.1f} mA through {r} outside {imin}–{imax} mA")
    for r in p["i2c"]["pullups"]:
        if not p["i2c"]["min_ohm"] <= _ohms(r) <= p["i2c"]["max_ohm"]:
            out.append(f"I2C pull-up {r} = {_ohms(r):.0f} Ω outside range")
    for r in ("R1", "R2", "R10"):
        if _ohms(r) > p["esp_strap_pullup_max"]:
            out.append(f"{r} pull-up too weak for a strap/INT line")
    return out


def thermal_cases(p=MARGIN_PARAMS):
    """Return the explicitly modeled sustained and coincident-peak LDO cases."""
    def junction(current_ma):
        watts = (p["vbus"] - p["v3v3"]) * current_ma / 1000
        return watts, p["t_ambient_max"] + watts * p["ldo_theta_ja"]
    peak_ma = sum(p["rail_peak_ma"].values())
    sustained_w, sustained_tj = junction(p["rail_sustained_ma"])
    peak_w, peak_tj = junction(peak_ma)
    return {
        "sustained": (p["rail_sustained_ma"], sustained_w, sustained_tj),
        "coincident_peak": (peak_ma, peak_w, peak_tj),
    }
