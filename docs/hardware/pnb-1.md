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
- R4 MUST be powered from a qualified USB-C 5 V / 1 A source with independent
  5.1 kOhm CC resistors, USB data-line ESD protection, and a regulator rated
  for at least 800 mA. Firmware MUST enumerate at no more than 500 mA when
  connected to a legacy USB host; full-load tests use the qualified supply.
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

- The 3V3 peak model is 350 mA for ESP32 Wi-Fi transmission, the SCD41
  datasheet-v1.7 maximum of 205 mA, 1 mA for BH1750, 11 mA for indicators and
  pull-ups, and 50 mA for J3. The 617 mA total is below the 1 A regulator
  rating; coincident peaks are supplied only from the qualified 1 A source.
- Sustained 3V3 load is limited to 200 mA until prototype thermal measurement.
  At 5.0 V input, 3.3 V output, 136 C/W (a conservative no-heatsink bound),
  and 50 C ambient, the model gives 96.2 C junction, below the 125 C limit.
- C9 is the AMS1117-supported 22 uF solid-tantalum stability configuration:
  TAJA226K010RNJ, 10 V, 3 ohm ESR. Its polarity MUST be checked at assembly.
- J3 pin 1 is deliberately unconnected; raw USB VBUS is not exported.
- The USB-C footprint requires a local 0.09 mm clearance between its own pads;
  all routed copper uses at least 0.15 mm width/space.
- J3 is through-hole and may be excluded from assembly for hand soldering if
  its exact LCSC part is unavailable. That substitution MUST be visible in the
  quote evidence.

Part identities and footprints are recorded in the generated netlist and
`fab/bom.csv`; the committed EasyEDA-derived symbols and footprints are the
reviewable sourcing record for this reproducibility fixture. Availability and
price are rechecked during an authenticated supplier dry run.
