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
| setup | `npm run pcb:setup` | pinned tool availability and versions |
| schematic | `$V pnb1_skidl.py && $V build.py` | typed ERC, independent vendor pad-map check, generated KiCad schematic, and all-severity KiCad ERC |
| fault test | `PNB_FAULT=short-3v3-to-sda $V pnb1_skidl.py` | required nonzero exit |
| margins | `$V verify_margins.py` | peak-current, thermal, and pull-up checks |
| build | `$V build.py` | footprints, placement, outline, and BOM |
| route | `$V route.py` | validated committed routed seed and zero-error/unconnected DRC |
| reroute | `PNB_ROUTE_REGENERATE=1 $V route.py` | bounded freerouting regeneration for layout iteration |
| release | `$V -m kibot -b pnb-1.kicad_pcb -c pnb-1.kibot.yaml -d fab` | Gerbers, drill files, CPL, ZIP, and DRC reports |
| package | `npm run pcb:verify-package` | BOM/CPL agreement and checksummed manifest |

`schematic.py` is the independent connectivity and numeric model; `verify.py`
cross-checks it against the vendor-derived library and generates
`sch/pnb-1.kicad_sch`. The committed DRC-clean routed seed makes normal builds
reproducible; an explicit regeneration reruns freerouting and replaces the seed
only after the corrected result passes DRC.
The fabrication package is ready to upload for an authenticated supplier dry
run; it does not prove quote acceptance, authorize an order, or claim physical
acceptance. J3 is deliberately DNP in the assembly package and remains as a
hand-installable daughter-header footprint.
