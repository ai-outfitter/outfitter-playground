# PNB-1 environmental sensor node

PNB-1 is an ESP32-S3-MINI-1 board with USB-C, an SCD41 CO2/temperature/
humidity sensor at I2C address `0x62`, and a BH1750 light sensor at address
`0x23`. It is the real PCB fixture exercised by the playground's
`hardware-engineer` profile.

Requirements live in `docs/hardware/pnb-1.md`; the daughter connector is
defined by `docs/hardware/pod-node-contract.md`.

## Reproducible flow

SKiDL -> standard KiCad netlist -> pcbnew -> freerouting -> KiBot. The root
devenv provides KiCad, pcbnew, freerouting, EasyEDA import, and ngspice;
`hardware/.venv` provides the pinned Python tools. Set
`V=../.venv/bin/python` while working in this directory.

| Stage | Source or command | Evidence |
| --- | --- | --- |
| setup | `npm run pcb:setup` | version and KiCad MCP inventory report |
| schematic | `$V pnb1_skidl.py` | typed ERC and connectivity-baseline match |
| fault test | `PNB_FAULT=short-3v3-to-sda $V pnb1_skidl.py` | required nonzero exit |
| margins | `$V verify_margins.py` | peak-current, thermal, and pull-up checks |
| build | `$V build.py` | footprints, placement, outline, and BOM |
| route | `$V route.py` | bounded freerouting and zero-error/unconnected DRC |
| release | `$V -m kibot -b pnb-1.kicad_pcb -c pnb-1.kibot.yaml -d fab` | Gerbers, drill files, CPL, ZIP, and DRC reports |
| package | `npm run pcb:verify-package` | BOM/CPL agreement and checksummed manifest |

The committed `reference/revA/netlist.json` is a connectivity regression
oracle from the proven design. It does not replace schematic or layout review.
The fabrication package is ready for a supplier dry run; it does not authorize
an order or claim physical acceptance.
