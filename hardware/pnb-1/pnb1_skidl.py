"""PNB-1 Pod Node Base — canonical schematic in SKiDL, wired by NAMED pins.

This is the playground rev A source of truth. Parts come from lib/artera.kicad_sym
(easyeda2kicad, LCSC); every connection references the symbol's pin NAME, so a
wrong pad number in the library is a name lookup failure here, not a silent
mis-wire. Requirements: docs/hardware/pnb-1.md. Contract:
docs/hardware/pod-node-contract.md.

Run:  ../.venv/bin/python pnb1_skidl.py
  → SKiDL ERC (typed pins) and pnb-1.net (standard KiCad netlist).
    verify.py supplies the independent pad-map and KiCad ERC gates.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# point skidl's default lib search at our lib/ before import so it does not
# warn about the missing stock-KiCad environment variables
for _v in ("KICAD_SYMBOL_DIR", "KICAD5_SYMBOL_DIR", "KICAD6_SYMBOL_DIR",
           "KICAD7_SYMBOL_DIR", "KICAD8_SYMBOL_DIR", "KICAD9_SYMBOL_DIR",
           "KICAD10_SYMBOL_DIR"):
    os.environ.setdefault(_v, os.path.join(_HERE, "lib"))

from skidl import ERC, Net, Part, Pin, generate_netlist, lib_search_paths, KICAD10
# skidl injects NC and default_circuit into builtins on import

HERE = os.path.dirname(os.path.abspath(__file__))
lib_search_paths[KICAD10].append(os.path.join(HERE, "lib"))

LIBNAME = "artera"
FP = lambda name: f"artera:{name}"

# easyeda2kicad symbols carry no electrical types ("unspecified"), which blinds
# any ERC — so the designer declares them, by pin NAME, and they are applied to
# the parts below. Ganged pins that share a name get one declaration.
PIN_TYPES = {
    "U1": {"GND": Pin.types.PWRIN, "3V3": Pin.types.PWRIN, "EN": Pin.types.INPUT,
           "TXD0": Pin.types.OUTPUT, "RXD0": Pin.types.INPUT},  # IOx stay bidirectional below
    "U2": {"GND": Pin.types.PWRIN, "VOUT": Pin.types.PWROUT, "VIN": Pin.types.PWRIN},
    "U3": {"VDD": Pin.types.PWRIN, "VDDH": Pin.types.PWRIN, "GND": Pin.types.PWRIN,
           "SCL": Pin.types.INPUT, "SDA": Pin.types.BIDIR},
    "U4": {"VCC": Pin.types.PWRIN, "GND": Pin.types.PWRIN, "ADDR": Pin.types.INPUT,
           "SDA": Pin.types.BIDIR, "SCL": Pin.types.INPUT, "DVI": Pin.types.INPUT,
           "EP": Pin.types.PWRIN},
    "D1": {"GND": Pin.types.PWRIN, "VBUS": Pin.types.PWRIN},
    "J1": {"VBUS": Pin.types.PWROUT, "GND": Pin.types.PWROUT,  # upstream side sources power
           "DP1": Pin.types.BIDIR, "DP2": Pin.types.BIDIR,
           "DN1": Pin.types.BIDIR, "DN2": Pin.types.BIDIR},
}


def pins_named(p, name):
    """All pins with this NAME (bracket lookup matches pin numbers first, so a
    pad literally numbered 'GND' would shadow the 19 other GND pins)."""
    pins = [pin for pin in p.pins if pin.name == name]
    assert pins, f"{p.ref}: no pin named {name}"
    return pins


def part(ref, symbol, value, fp, lcsc, mpn, desc):
    p = Part(LIBNAME, symbol, ref=ref, value=value, footprint=FP(fp), tag=ref)
    p.fields["LCSC Part #"] = lcsc
    p.fields["MPN"] = mpn
    p.fields["Description"] = desc
    for name, func in PIN_TYPES.get(ref, {}).items():
        pins = pins_named(p, name)
        for i, pin in enumerate(pins):
            # ganged pins (LDO tab, USB-C paired pads): one power_out drives,
            # siblings go passive, or ERC flags power_out <-> power_out
            if func == Pin.types.PWROUT and i > 0:
                pin.func = Pin.types.PASSIVE
            else:
                pin.func = func
    if ref == "U1":
        for pin in p.pins:
            if pin.name.startswith("IO"):
                pin.func = Pin.types.BIDIR
    # easyeda2kicad leaves everything else "unspecified", which ERC treats as
    # conflict-with-anything noise; the rev A rule was: unlisted pads = passive
    for pin in p.pins:
        if pin.func == Pin.types.UNSPEC:
            pin.func = Pin.types.PASSIVE
    return p


# ---------------------------------------------------------------- parts
u1 = part("U1", "ESP32-S3-MINI-1-N8", "ESP32-S3-MINI-1-N8",
          "BULETM-SMD_ESP32-S3-MINI-1-N8", "C2913206", "ESP32-S3-MINI-1-N8",
          "Wi-Fi/BLE module, 8 MB flash, PCB antenna")
u2 = part("U2", "AMS1117-3.3", "AMS1117-3.3",
          "SOT-223-3_L6.5-W3.4-P2.30-LS7.0-BR", "C6186", "AMS1117-3.3", "3.3 V 1 A LDO")
u3 = part("U3", "SCD41-D-R2", "SCD41-D-R2",
          "LGA-20_L10.1-W10.1-P1.25-TL_SCD41-D-R2", "C3659294", "SCD41-D-R2",
          "CO2/T/RH sensor, I2C 0x62")
u4 = part("U4", "BH1750FVI-TR", "BH1750FVI-TR",
          "WSOF-6_L2.6-W1.6-P0.50-TL-EP", "C78960", "BH1750FVI-TR",
          "ambient light sensor, I2C 0x23")
d1 = part("D1", "USBLC6-2SC6_C2687116", "USBLC6-2SC6",
          "SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL", "C2687116", "USBLC6-2SC6", "USB ESD array")
j1 = part("J1", "TYPE-C-31-M-12", "USB-C 16P",
          "USB-C_SMD-TYPE-C-31-M-12_1", "C165948", "TYPE-C-31-M-12",
          "USB-C receptacle USB 2.0")
j3 = part("J3", "Header-Male-2.54_2x6", "DTR 2x6",
          "HDR-TH_12P-P2.54-V-M-R2-C6-S2.54", "C66689", "Dual Row Pin Header2.54mm2*6Pin Header",
          "daughter header (contract J3)")
j4 = part("J4", "Header-Male-2.54_1x4", "UART 1x4",
          "HDR-TH_4P-P2.54-V-M", "C124378", "B-2100S04P-A110", "UART0 header 3V3/TX/RX/GND")
sw1 = part("SW1", "TS-1088-AR02016", "BOOT", "SW-SMD_L3.9-W3.0-P4.45", "C720477",
           "TS-1088-AR02016", "tactile")
sw2 = part("SW2", "TS-1088-AR02016", "RESET", "SW-SMD_L3.9-W3.0-P4.45", "C720477",
           "TS-1088-AR02016", "tactile")

RES = {  # ref: (value, lcsc, symbol/mpn, desc)
    "R1": ("10k", "C25804", "0603WAF1002T5E", "EN pull-up"),
    "R2": ("10k", "C25804", "0603WAF1002T5E", "IO0 pull-up"),
    "R3": ("5.1k", "C23186", "0603WAF5101T5E", "CC1 Rd"),
    "R4": ("5.1k", "C23186", "0603WAF5101T5E", "CC2 Rd"),
    "R5": ("4.7k", "C23162", "0603WAF4701T5E", "SDA pull-up"),
    "R6": ("4.7k", "C23162", "0603WAF4701T5E", "SCL pull-up"),
    "R7": ("1k", "C21190", "0603WAF1001T5E", "BH1750 DVI"),
    "R8": ("330R", "C23138", "0603WAF3300T5E", "power LED (red, Vf 2 V, ~4 mA)"),
    "R9": ("330R", "C23138", "0603WAF3300T5E", "user LED"),
    "R10": ("10k", "C25804", "0603WAF1002T5E", "DTR_INT pull-up (contract: open-drain)"),
}
R = {ref: part(ref, mpn, val, "R0603", lcsc, mpn, desc)
     for ref, (val, lcsc, mpn, desc) in RES.items()}

CAPS = {  # ref: (value, fp, lcsc, symbol/mpn, desc)
    "C1": ("100nF", "C0603", "C14663", "CC0603KRX7R9BB104", "U1 3V3 decoupling"),
    "C2": ("100nF", "C0603", "C14663", "CC0603KRX7R9BB104", "U2 VIN decoupling"),
    "C3": ("100nF", "C0603", "C14663", "CC0603KRX7R9BB104", "U2 VOUT decoupling"),
    "C4": ("100nF", "C0603", "C14663", "CC0603KRX7R9BB104", "U3 VDD decoupling"),
    "C5": ("100nF", "C0603", "C14663", "CC0603KRX7R9BB104", "U4 VCC decoupling"),
    "C6": ("1uF", "C0603", "C15849", "CL10A105KB8NNNC", "EN RC"),
    "C7": ("1uF", "C0603", "C15849", "CL10A105KB8NNNC", "BH1750 DVI"),
    "C8": ("10uF", "C0805", "C15850", "CL21A106KAYNNNE", "VBUS bulk"),
    "C9": ("22uF tantalum", "CASE-A_3216", "C11366", "TAJA226K010RNJ", "U2 VOUT stability capacitor, 10 V, 3 ohm ESR"),
    "C10": ("10uF", "C0805", "C15850", "CL21A106KAYNNNE", "U3 VDD bulk (205 mA maximum)"),
    "C11": ("10uF", "C0805", "C15850", "CL21A106KAYNNNE", "U1 3V3 bulk at the module"),
}
C = {ref: part(ref, "CL21A226MAQNNNE" if ref == "C9" else mpn, val, fp, lcsc, mpn, desc)
     for ref, (val, fp, lcsc, mpn, desc) in CAPS.items()}

led1 = part("LED1", "KT-0603R", "PWR", "LED-SMD_L1.6-W0.8-R-RD", "C2286", "KT-0603R",
            "red 0603, 3V3 present")
led2 = part("LED2", "KT-0603R", "USER", "LED-SMD_L1.6-W0.8-R-RD", "C2286", "KT-0603R",
            "red 0603, GPIO21")

# Pull resistors: type the signal-side pin so ERC knows the net is held at a
# level (silences "no driver" the honest way instead of waiving the net).
for _r in ("R1", "R2", "R5", "R6", "R7", "R10"):   # pull-ups to 3V3
    R[_r][2].func = Pin.types.PULLUP
for _r in ("R3", "R4"):                            # CC Rd pull-downs
    R[_r][1].func = Pin.types.PULLDN
R["R8"][2].func = Pin.types.PULLUP                 # LED_PWR: tied to 3V3 via R8

# ---------------------------------------------------------------- nets
# Every connection below is by symbol pin NAME (passives/headers/switches have
# their pad number as the name — the only names those parts carry).
gnd = Net("GND")
vbus = Net("VBUS")
v3v3 = Net("3V3")

gnd += (*pins_named(u1, "GND"), u2["GND"], *pins_named(u3, "GND"), u4["GND"], u4["ADDR"], u4["EP"],
        d1["GND"], *pins_named(j1, "GND"), *pins_named(j1, "EH"),          # EH = USB-C shell pads 1-4
        j3[2], j3[4], j4[4], sw1[2], sw2[2],
        R["R3"][2], R["R4"][2],
        *[C[c][2] for c in CAPS], led1["K"], led2["K"])

vbus += j1["VBUS"], u2["VIN"], d1["VBUS"], C["C8"][1], C["C2"][1]

v3v3 += (u2["VOUT"], C["C3"][1], C["C9"][1],
         u1["3V3"], C["C1"][1], C["C11"][1],
         R["R1"][1], R["R2"][1], R["R5"][1], R["R6"][1], R["R7"][1], R["R8"][1], R["R10"][1],
         u3["VDD"], u3["VDDH"], C["C4"][1], C["C10"][1],
         u4["VCC"], C["C5"][1],
         j3[3], j4[1])

n_usb_dp = Net("USB_DP"); n_usb_dp += j1["DP1"], j1["DP2"], d1["I/O1"], u1["IO20"]
n_usb_dn = Net("USB_DN"); n_usb_dn += j1["DN1"], j1["DN2"], d1["I/O2"], u1["IO19"]
n_cc1 = Net("CC1"); n_cc1 += j1["CC1"], R["R3"][1]
n_cc2 = Net("CC2"); n_cc2 += j1["CC2"], R["R4"][1]

n_en = Net("EN"); n_en += u1["EN"], R["R1"][2], C["C6"][1], sw2[1]
n_io0 = Net("IO0"); n_io0 += u1["IO0"], R["R2"][2], sw1[1]

n_sda = Net("SDA"); n_sda += u1["IO5"], R["R5"][2], u3["SDA"], u4["SDA"], j3[5]
n_scl = Net("SCL"); n_scl += u1["IO6"], R["R6"][2], u3["SCL"], u4["SCL"], j3[6]
n_dvi = Net("DVI"); n_dvi += u4["DVI"], R["R7"][2], C["C7"][1]

n_led_pwr = Net("LED_PWR"); n_led_pwr += R["R8"][2], led1["A"]
n_io21 = Net("IO21"); n_io21 += u1["IO21"], R["R9"][1]
n_led_user = Net("LED_USER"); n_led_user += R["R9"][2], led2["A"]

n_txd0 = Net("TXD0"); n_txd0 += u1["TXD0"], j4[2]
n_rxd0 = Net("RXD0"); n_rxd0 += u1["RXD0"], j4[3]

n_dtr_gpioa = Net("DTR_GPIOA"); n_dtr_gpioa += u1["IO7"], j3[7]
n_dtr_gpiob = Net("DTR_GPIOB"); n_dtr_gpiob += u1["IO8"], j3[8]
n_dtr_adca = Net("DTR_ADCA"); n_dtr_adca += u1["IO4"], j3[9]
n_dtr_adcb = Net("DTR_ADCB"); n_dtr_adcb += u1["IO9"], j3[10]
n_dtr_gpioc = Net("DTR_GPIOC"); n_dtr_gpioc += u1["IO10"], j3[11]
n_dtr_int = Net("DTR_INT"); n_dtr_int += u1["IO1"], j3[12], R["R10"][2]

# The acceptance harness sets this only for an expected-failure run. Joining a
# power output to SDA must make typed ERC fail.
if os.environ.get("PNB_FAULT") == "short-3v3-to-sda":
    n_sda += u2["VOUT"]

# Deliberately unconnected (reason) — everything else left open is an ERC error.
NC += u1["IO2"]   # spare
NC += u1["IO3"]   # strapping (JTAG sel) — float
NC += u1["IO45"]  # strapping (VDD_SPI) — float
NC += u1["IO46"]  # strapping — float
for name in (["IO11", "IO12", "IO13", "IO14", "IO15", "IO16", "IO17", "IO18",
              "IO26", "IO47", "IO33", "IO34", "IO48", "IO35", "IO36", "IO37",
              "IO38", "IO39", "IO40", "IO41", "IO42"]):
    NC += u1[name]  # spare GPIO
NC += u3["DNC"]   # SCD41 DNC pads (datasheet: do not connect)
NC += j1["SBU1"], j1["SBU2"]  # SBU unused
NC += j3[1]  # reserved: this USB-powered revision does not export raw VBUS


if __name__ == "__main__":
    default_circuit.tag = "pnb-1"
    ERC()
    from skidl.logger import erc_logger
    erc_fail = erc_logger.error.count or erc_logger.warning.count
    generate_netlist(file_=os.path.join(HERE, "pnb-1.net"))

    print("skidl typed ERC and netlist generation: PASS")
    if erc_fail:
        print(f"SKiDL ERC not clean: {erc_logger.error.count} errors, "
              f"{erc_logger.warning.count} warnings")
        sys.exit(1)
