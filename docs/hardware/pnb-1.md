---
title: PNB-1 environmental sensor node
design_kind: pcb
design_status: layout
layers: 2
---

# PNB-1 environmental sensor node

PNB-1 is the playground's golden PCB exercise. It is a USB-powered ESP32-S3
sensor node with one shared I2C bus connecting an SCD41 CO2/temperature/
humidity sensor and a BH1750 ambient-light sensor. Its purpose is to prove the
complete `hardware-engineer` path against a real fabrication-package candidate.

## Requirements

- R1 MUST use an ESP32-S3-MINI-1-N8 module and expose native USB programming.
- R2 MUST use GPIO5 for SDA and GPIO6 for SCL on one 3.3 V I2C bus.
- R3 MUST put SCD41 address `0x62` and BH1750 address `0x23` on that bus with
  one pair of 4.7 kOhm pull-ups.
- R4 MUST be powered from a qualified USB-C 5 V / 1 A source with independent
  5.1 kOhm CC resistors, USB data-line ESD protection, and a regulator rated
  for at least 800 mA. A legacy USB data host is programming-only until
  firmware proves the <=500 mA operating state; full-load tests use the
  qualified supply.
- R5 MUST provide BOOT, RESET, UART0, a power LED, and a user LED.
- R6 MUST implement the daughter-header footprint and electrical contract in
  `pod-node-contract.md`; J3 itself is DNP for assembly and hand-installed only.
- R7 MUST be a two-layer board no larger than 60 x 45 mm with four M2.5 holes.
- R8 MUST attach an MPN and LCSC identifier to every populated BOM line.
- R9 MUST generate a JLCPCB-compatible Gerber archive, BOM, CPL, and board
  renders, but MUST NOT place or pay for an order.

## Pin map

| Signal | ESP32-S3 pin | Device/address |
| --- | --- | --- |
| SDA | GPIO5 | SCD41 `0x62`, BH1750 `0x23` |
| SCL | GPIO6 | SCD41 `0x62`, BH1750 `0x23` |
| USB D- / D+ | GPIO19 / GPIO20 | native USB |
| BOOT | GPIO0 | 10 kOhm pull-up and button |
| UART0 TX / RX | GPIO43 / GPIO44 | J4 |
| user LED | GPIO21 | LED2 |

## Electrical limits and waivers

- The 3V3 peak model is 350 mA for ESP32 Wi-Fi transmission, the SCD41
  datasheet-v1.7 maximum of 205 mA, 1 mA for BH1750, 11 mA for indicators and
  pull-ups, and 50 mA for J3. The 617 mA total is below the 1 A regulator
  rating. The linear-regulator thermal model gives 192.7 C at that coincident
  peak, so firmware MUST NOT sustain that state even on the qualified source.
- Sustained 3V3 load is limited to 200 mA until prototype thermal measurement.
  At 5.0 V input, 3.3 V output, the pre-prototype 136 C/W engineering bound,
  and 50 C ambient, the model gives 96.2 C junction, below the 125 C limit.
  The 136 C/W bound and 200 mA firmware limit are explicit waivers; both retire
  only after thermocouple measurement at those conditions on an assembled PCB.
- C9 is the AMS1117-supported 22 uF solid-tantalum stability configuration:
  TAJA226K010RNJ, 10 V, 3 ohm ESR. Its polarity MUST be checked at assembly.
- J3 pin 1 is deliberately unconnected; raw USB VBUS is not exported.
- The SCD41 footprint follows the Sensirion SCD4x land pattern: 20 electrical
  lands, a 4.8 x 4.8 mm central all-copper keep-free area, and a 0.25 mm NPTH
  relief hole with 0.6 mm solder/flux keep-free diameter between lands 10/11.
  Lands 10/11 are shortened from the recommended 1.50 mm to 1.44 mm, within
  Sensirion's instruction to adapt the recommended land pattern to the
  soldering process, so the hole-to-copper clearance exceeds JLCPCB's 0.20 mm
  minimum.
  Source: [Sensirion SCD4x datasheet v1.7, section 4.2](https://sensirion.com/media/documents/48C4B7FB/67FE0194/CD_DS_SCD4x_Datasheet_D1.pdf).
  Fabrication constraint: [JLCPCB PCB capabilities, NPTH to Track](https://jlcpcb.com/capabilities/pcb-capabilities/).
- The USB-C footprint requires a local 0.09 mm clearance between its own pads.
  Routed copper and GND pours otherwise use at least 0.15 mm width/space;
  NPTH-to-copper clearance is at least 0.20 mm.
- J3 is excluded from the assembly BOM and CPL. Its footprint remains for an
  exact, separately sourced 2x6 header to be hand-installed after assembly.

Part identities and footprints are recorded in the generated netlist and
`fab/bom.csv`; the committed EasyEDA-derived symbols and footprints are the
reviewable sourcing record for this reproducibility fixture. Availability and
price are rechecked during an authenticated supplier dry run.

## Evidence boundary

The generated Gerbers, drill files, BOM, CPL, renders, manifest, all-severity
ERC/DRC, and KiCad MCP checks establish a digitally uploadable package. They do
not establish supplier stock, quote acceptance, USB firmware current behavior,
thermal performance, RF performance, sensor accuracy, assembly yield, or
physical acceptance. Those gates require an authenticated supplier dry run and
assembled prototypes; this workflow does not place or pay for an order.
