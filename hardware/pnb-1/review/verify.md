# PNB-1 rev A — verify.py

## erc() vs footprint pads: PASS — 192 pads, 23 nets


## pad map vs EasyEDA pin names (independent): PASS — 75 IC/connector pads checked


## KiCad ERC, all severities: PASS — 0 violations in sch/pnb-1.kicad_sch


## numeric margins: PASS — vbus=5.0, vbus_min=4.75, v3v3=3.3, ldo_dropout=1.1, ldo_theta_ja=136.0 (waiver: 136 C/W pre-prototype engineering bound; retire with thermocouple measurement at 5 V, 200 mA, and 50 C ambient), t_ambient_max=50.0, t_junction_max=125.0, ldo_i_max_ma=1000, rail_sustained_ma=200 (waiver: firmware-enforced 200 mA sustained limit; verify on the assembled prototype before functional release), esp_strap_pullup_max=100000.0; thermal cases: sustained=200 mA/0.34 W/96.2 C; coincident_peak=617 mA/1.05 W/192.7 C

