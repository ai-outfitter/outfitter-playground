"""Numerical checks whose inputs are documented in docs/hardware/pnb-1.md."""

PEAK_MA = {
    "esp32_wifi_tx": 350,
    "scd41": 175,
    "bh1750": 1,
    "daughter_3v3": 150,
}


def main() -> None:
    peak_ma = sum(PEAK_MA.values())
    assert peak_ma <= 800, f"3V3 peak {peak_ma} mA exceeds 800 mA design limit"

    ambient_c = 50
    sustained_a = 0.400
    theta_c_per_w = 50
    junction_c = ambient_c + (5.0 - 3.3) * sustained_a * theta_c_per_w
    assert junction_c <= 125, f"estimated LDO junction {junction_c:.1f} C exceeds 125 C"

    pullup_ohms = 4700
    assert 2200 <= pullup_ohms <= 10000, "I2C pull-up outside declared range"
    print(f"margins: peak={peak_ma} mA, LDO Tj={junction_c:.1f} C, I2C={pullup_ohms} ohm")


if __name__ == "__main__":
    main()
