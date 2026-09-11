"""Standalone entry point for the canonical schematic margin checks."""

import schematic


def main() -> None:
    problems = schematic.margins()
    assert not problems, "\n".join(problems)
    p = schematic.MARGIN_PARAMS
    peak_ma = sum(p["rail_peak_ma"].values())
    cases = schematic.thermal_cases(p)
    _, sustained_w, junction_c = cases["sustained"]
    _, peak_w, peak_junction_c = cases["coincident_peak"]
    print(f"margins: peak={peak_ma} mA, sustained={p['rail_sustained_ma']} mA, "
          f"LDO sustained={sustained_w:.2f} W/{junction_c:.1f} C, "
          f"coincident peak={peak_w:.2f} W/{peak_junction_c:.1f} C, "
          f"I2C={schematic._ohms('R5'):.0f} ohm; waivers: "
          f"theta-JA={schematic.WAIVERS['ldo_theta_ja']}; "
          f"sustained-current={schematic.WAIVERS['rail_sustained_ma']}")


if __name__ == "__main__":
    main()
