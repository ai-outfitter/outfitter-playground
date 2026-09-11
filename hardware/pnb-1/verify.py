"""Schematic verification gates for PNB-1. Every gate is binary and a failure
is a hard stop (SystemExit). Run standalone (`python3 verify.py`) or from
build.py before the board is generated.

  1. erc()          self-consistency of NETS/NC against the real footprint pads
                    (needs pad_names from the footprints; build.py and release.py
                    supply it — standalone runs report the gate as SKIPPED)
  2. pad map        pad numbers vs the pin NAMES in lib/<LIB>.kicad_sym (EasyEDA,
                    an independent source) per schematic.EXPECT — 0 mismatches
  3. KiCad ERC      generate sch/<board>.kicad_sch (pin types from PIN_TYPES) and
                    run `kicad-cli sch erc --severity-all` — 0 violations of ANY
                    severity (the faults this catches are reported as warnings)
  4. margins()      numeric asserts (LED current, LDO thermal, rail budget, pull-ups)

Outputs: sch/ (openable in KiCad), review/erc.json, review/verify.md.
"""
import json, os, re, subprocess, sys, uuid
import schematic as S

HERE = os.path.dirname(os.path.abspath(__file__))
SLUG = S.BOARD.lower()
LIBSYM = os.path.join(HERE, "lib", f"{S.LIB}.kicad_sym")
SCH_DIR = os.path.join(HERE, "sch")
REVIEW = os.path.join(HERE, "review")


# ---------------------------------------------------------------- symbol lib
def _top_level_symbols(txt):
    """{name: block text} for every top-level (symbol "…") in a .kicad_sym."""
    out, i = {}, 0
    while True:
        m = re.compile(r'^[ \t]*\(symbol "([^"]+)"', re.M).search(txt, i)
        if not m:
            return out
        if re.search(r"_\d+_\d+$", m.group(1)):      # a unit/style sub-symbol, skip
            i = m.end(); continue
        depth, j = 0, m.start()
        while True:
            c = txt[j]
            if c == "(": depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0: break
            j += 1
        out[m.group(1)] = txt[m.start():j + 1]
        i = j + 1


def _pins(block):
    """[(number, name, x, y)] with x,y = the connection point in symbol coords."""
    return [(m.group(5), m.group(4), float(m.group(1)), float(m.group(2)))
            for m in re.finditer(r'\(pin \w+ \w+\n\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)\n\s*\(length [\d.]+\)\n'
                                 r'\s*\(name "([^"]*)"[^\n]*\n\s*\(number "([^"]*)"', block)]


def _retype(block, types):
    def one(m):
        num = re.search(r'\(number "([^"]*)"', m.group(0)).group(1)
        return re.sub(r'\(pin \w+', f'(pin {types.get(num, "passive")}', m.group(0), count=1)
    return re.sub(r'\(pin \w+ \w+\n(?:[^\n]*\n){4}', one, block)


# ------------------------------------------------------------------ gates
def check_padmap(symbols):
    problems, checked = [], 0
    for net, pins in S.NETS.items():
        for ref, pad in pins:
            exp = S.EXPECT.get(net, {}).get(ref)
            if exp is None:
                if ref in S.PIN_TYPES:   # coverage floor: every typed part needs an expectation on every net it touches
                    problems.append(f"{net}: no EXPECT entry for {ref} (typed part) — add one, don't skip")
                continue
            checked += 1
            names = {n: nm for n, nm, _, _ in _pins(symbols[S.SYMBOLS[ref]])}
            nm = names.get(pad)
            if nm is None or not re.search(exp, nm, re.I):
                problems.append(f"{net}: {ref}.{pad} is named {nm!r} in the symbol, expected /{exp}/")
    return checked, problems


def write_schematic(symbols):
    """A real .kicad_sch: every part placed on a grid, a global label on every
    connected pin, a no-connect on every NC pin. Not pretty — but ERC-complete
    and openable in KiCad."""
    os.makedirs(SCH_DIR, exist_ok=True)
    root = str(uuid.uuid4())
    used = {S.SYMBOLS[r] for r in S.PARTS}
    lib_symbols = []
    for name in sorted(used):
        types = {}
        for r, sym in S.SYMBOLS.items():
            if sym == name and r in S.PARTS:
                types.update(S.PIN_TYPES.get(r, {}))
        blk = _retype(symbols[name], types)
        blk = blk.replace(f'(symbol "{name}"', f'(symbol "{S.LIB}:{name}"', 1)
        lib_symbols.append(blk)
    body, labels, ncs = [], [], []
    x = y = 50.8            # multiples of 1.27 mm, or KiCad ERC reports endpoint_off_grid
    for ref, (fp, val, lcsc, mpn, desc) in S.PARTS.items():
        sym = S.SYMBOLS[ref]
        pins = _pins(symbols[sym])
        pin_xy = {n: (x + px, y - py) for n, _, px, py in pins}   # sheet y is down
        pin_uuids = "".join(f'\n\t\t(pin "{n}" (uuid "{uuid.uuid4()}"))' for n, *_ in pins)
        is_dnp = ref in S.DNP
        body.append(f'''\t(symbol (lib_id "{S.LIB}:{sym}") (at {x:.2f} {y:.2f} 0) (unit 1)
\t\t(exclude_from_sim no) (in_bom {'no' if is_dnp else 'yes'}) (on_board yes) (dnp {'yes' if is_dnp else 'no'}) (uuid "{uuid.uuid4()}")
\t\t(property "Reference" "{ref}" (at {x:.2f} {y + 8:.2f} 0) (effects (font (size 1.27 1.27))))
\t\t(property "Value" "{val}" (at {x:.2f} {y - 8:.2f} 0) (effects (font (size 1.27 1.27))))
\t\t(property "Footprint" "{S.LIB}:{fp}" (at {x:.2f} {y:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes))){pin_uuids}
\t\t(instances (project "{SLUG}" (path "/{root}" (reference "{ref}") (unit 1))))
\t)''')
        for net, npins in S.NETS.items():
            for r, pad in npins:
                if r == ref:
                    if pad not in pin_xy:
                        sys.exit(f"{ref}.{pad} is in NETS but not in symbol {sym}")
                    lx, ly = pin_xy[pad]
                    labels.append(f'\t(global_label "{net}" (shape input) (at {lx:.2f} {ly:.2f} 0) '
                                  f'(effects (font (size 1.27 1.27))) (uuid "{uuid.uuid4()}"))')
        for (r, pad), why in S.NC.items():
            if r == ref and pad in pin_xy:       # pads that exist only on the footprint (pegs) have no symbol pin
                lx, ly = pin_xy[pad]
                ncs.append(f'\t(no_connect (at {lx:.2f} {ly:.2f}) (uuid "{uuid.uuid4()}"))')
        x += 127.0
        if x > 900:
            x, y = 50.8, y + 127.0
    sch = "\n".join([
        f'(kicad_sch (version 20250114) (generator "verify.py") (generator_version "10.0") (uuid "{root}") (paper "A0")',
        f'\t(title_block (title "{S.BOARD} rev {S.REV}"))',
        "\t(lib_symbols", *["\t" + b.replace("\n", "\n\t") for b in lib_symbols], "\t)",
        *body, *labels, *ncs,
        f'\t(sheet_instances (path "/" (page "1")))', ")", ""])
    open(os.path.join(SCH_DIR, f"{SLUG}.kicad_sch"), "w").write(sch)
    lib = "${KIPRJMOD}/../lib" if os.path.abspath(SCH_DIR).startswith(HERE) else os.path.join(HERE, "lib")
    open(os.path.join(SCH_DIR, "sym-lib-table"), "w").write(
        f'(sym_lib_table (version 7)\n (lib (name "{S.LIB}")(type "KiCad")(uri "{lib}/{S.LIB}.kicad_sym")(options "")(descr ""))\n)\n')
    open(os.path.join(SCH_DIR, "fp-lib-table"), "w").write(   # without this every part is a footprint_link_issues warning
        f'(fp_lib_table (version 7)\n (lib (name "{S.LIB}")(type "KiCad")(uri "{lib}/{S.LIB}.pretty")(options "")(descr ""))\n)\n')
    # Always reset the project file: a GUI save could store ERC severity overrides.
    open(os.path.join(SCH_DIR, f"{SLUG}.kicad_pro"), "w").write("{}\n")
    # Vacuous-pass guards: every part placed, every declared pin type applied.
    assert sch.count("(lib_id ") == len(S.PARTS), "not every part was placed"
    declared = sum(1 for r, t in S.PIN_TYPES.items() if r in S.PARTS for _ in t)
    applied = sum(len(re.findall(r'\(pin (?!passive|unspecified)\w+ ', b)) for b in lib_symbols)
    assert applied >= len({(S.SYMBOLS[r], p) for r, t in S.PIN_TYPES.items() if r in S.PARTS for p, k in t.items() if k != "passive"}), \
        f"pin types not applied: {applied} in lib_symbols"
    return os.path.join(SCH_DIR, f"{SLUG}.kicad_sch")


def kicad_erc(sch_path):
    os.makedirs(REVIEW, exist_ok=True)
    out = os.path.join(REVIEW, "erc.json")
    r = subprocess.run(["kicad-cli", "sch", "erc", "--format", "json", "--severity-all", "-o", out, sch_path],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        sys.exit(f"kicad-cli sch erc failed:\n{r.stdout}{r.stderr}")
    j = json.load(open(out))
    assert len(j["sheets"]) == 1, f"ERC report has {len(j['sheets'])} sheets"
    return [v for s in j["sheets"] for v in s["violations"]]


def run(pad_names=None):
    symbols = _top_level_symbols(open(LIBSYM).read())
    report = [f"# {S.BOARD} rev {S.REV} — verify.py\n"]
    failed = False

    def gate(name, problems, detail):
        nonlocal failed
        status = "PASS" if not problems else "FAIL"
        failed |= bool(problems)
        report.append(f"## {name}: {status} — {detail}\n")
        for p in problems:
            report.append(f"- {p}")
        report.append("")
        print(f"[{status}] {name}: {detail}")
        for p in problems:
            print("   -", p)

    if pad_names is not None:
        gate("erc() vs footprint pads", S.erc(pad_names), f"{sum(map(len, pad_names.values()))} pads, {len(S.NETS)} nets")
    else:
        report.append("## erc() vs footprint pads: SKIPPED — no pad_names (standalone run; build.py/release.py supply them)\n")
        print("[SKIP] erc() vs footprint pads: standalone run — build.py/release.py run it against the footprints")
    checked, probs = check_padmap(symbols)
    gate("pad map vs EasyEDA pin names (independent)", probs, f"{checked} IC/connector pads checked")
    sch = write_schematic(symbols)
    v = kicad_erc(sch)
    gate("KiCad ERC, all severities", [f"{x['severity']} {x['type']}: " + "; ".join(i["description"] for i in x["items"]) for x in v],
         f"{len(v)} violations in sch/{os.path.basename(sch)}")
    thermal = S.thermal_cases()
    thermal_detail = "; ".join(
        f"{name}={ma} mA/{watts:.2f} W/{tj:.1f} C"
        for name, (ma, watts, tj) in thermal.items())
    gate("numeric margins", S.margins(), ", ".join(
        f"{k}={v}" + (f" (waiver: {S.WAIVERS[k]})" if k in S.WAIVERS else "")
        for k, v in S.MARGIN_PARAMS.items() if not isinstance(v, dict)) + f"; thermal cases: {thermal_detail}")
    open(os.path.join(REVIEW, "verify.md"), "w").write("\n".join(report))
    if failed:
        sys.exit("verify: FAILED — see review/verify.md")
    print("verify: all gates green")


def selftest():
    """Prove the gates bite: inject a short, bad resistor, and absent U3 pad."""
    import copy, tempfile, shutil
    global SCH_DIR, REVIEW
    SCH_DIR, REVIEW = tempfile.mkdtemp(), tempfile.mkdtemp()
    nets, parts = S.NETS, S.PARTS
    S.NETS = copy.deepcopy(nets); S.NETS["SCL"].append(("U2", "2"))
    S.PARTS = dict(parts); S.PARTS["R8"] = ("R0603", "10R", "C0", "x", "bad LED resistor")
    pad_names = {ref: sorted({pad for pins in S.NETS.values() for r, pad in pins if r == ref} |
                             {pad for r, pad in S.NC if r == ref})
                 for ref in S.PARTS}
    pad_names["U3"].remove("9")
    try:
        run(pad_names)
    except SystemExit as e:
        v = json.load(open(os.path.join(REVIEW, "erc.json")))
        kinds = {x["type"] for s_ in v["sheets"] for x in s_["violations"]}
        assert "pin_to_pin" in kinds, kinds
        assert any("LED1" in p for p in S.margins()), S.margins()
        assert "SCL: U3 has no pad '9'" in S.erc(pad_names), S.erc(pad_names)
        print("selftest: injected faults were caught (footprint pad: U3.9; KiCad ERC:",
              ", ".join(sorted(kinds)), "; margins: LED1)")
    else:
        sys.exit("selftest FAILED: injected faults passed the gates")
    finally:
        S.NETS, S.PARTS = nets, parts
        shutil.rmtree(SCH_DIR); shutil.rmtree(REVIEW)


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else run()
