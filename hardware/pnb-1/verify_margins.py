"""Standalone entry point for the canonical schematic margin checks."""

import schematic


def main() -> None:
    problems = schematic.margins()
    assert not problems, "\n".join(problems)
    p = schematic.MARGIN_PARAMS
    peak_ma = sum(p["rail_peak_ma"].values())
    pd_w = (p["vbus"] - p["v3v3"]) * p["rail_sustained_ma"] / 1000
    junction_c = p["t_ambient_max"] + pd_w * p["ldo_theta_ja"]
    print(f"margins: peak={peak_ma} mA, sustained={p['rail_sustained_ma']} mA, "
          f"LDO Tj={junction_c:.1f} C, I2C={schematic._ohms('R5'):.0f} ohm")


if __name__ == "__main__":
    main()
