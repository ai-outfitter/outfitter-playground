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
complete `hardware-engineer` path against a real, orderable design.

## Requirements

- R1 MUST use an ESP32-S3-MINI-1-N8 module and expose native USB programming.
- R2 MUST use GPIO5 for SDA and GPIO6 for SCL on one 3.3 V I2C bus.
- R3 MUST put SCD41 address `0x62` and BH1750 address `0x23` on that bus with
  one pair of 4.7 kOhm pull-ups.
- R4 MUST be powered from USB-C 5 V with independent 5.1 kOhm CC resistors,
  USB data-line ESD protection, and a regulator rated for at least 800 mA.
- R5 MUST provide BOOT, RESET, UART0, a power LED, and a user LED.
- R6 MUST implement the daughter-header contract in `pod-node-contract.md`.
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

- The rail peak model is 350 mA for ESP32 Wi-Fi transmission, 175 mA for the
  SCD41, 1 mA for the BH1750, and 150 mA for the daughter connector. The total
  676 mA is below the AMS1117's 800 mA design requirement.
- Sustained bench load is limited to 400 mA. At 5.0 V input, 3.3 V output, and
  50 C/W with the committed copper and thermal-via treatment, estimated
  junction rise is 34 C. This MUST remain below a 125 C junction limit at a
  50 C ambient design point.
- The USB-C footprint requires a local 0.09 mm clearance between its own pads;
  all routed copper uses at least 0.15 mm width/space.
- J3 is through-hole and may be excluded from assembly for hand soldering if
  its exact LCSC part is unavailable. That substitution MUST be visible in the
  quote evidence.

Part identities and footprints are recorded in the generated netlist and
`fab/bom.csv`; the committed EasyEDA-derived symbols and footprints are the
reviewable sourcing record for this reproducibility fixture. Availability and
price are rechecked during an authenticated supplier dry run.
