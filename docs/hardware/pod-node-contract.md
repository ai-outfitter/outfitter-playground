# Pod-node interconnect contract

PNB-1 exposes the J3 footprint as a 2x6, 2.54 mm daughter-board interface. J3
is DNP in the assembly package and requires an exact separately sourced header
for hand installation.

| Pin | Signal | Direction from base | Limit |
| --- | --- | --- | --- |
| 1 | reserved | not connected | - |
| 2 | GND | - | - |
| 3 | 3V3 | output | 50 mA peak |
| 4 | GND | - | - |
| 5 | SDA | bidirectional | 3.3 V; pull-ups on base only |
| 6 | SCL | bidirectional | 3.3 V; pull-ups on base only |
| 7 | GPIO7 | bidirectional | - |
| 8 | GPIO8 | bidirectional | - |
| 9 | GPIO4 | input | ADC1, 0-3.1 V |
| 10 | GPIO9 | input | ADC1, 0-3.1 V |
| 11 | GPIO10 | bidirectional | - |
| 12 | GPIO1 | input | open-drain interrupt; base pull-up |

Daughters MUST NOT add I2C pull-ups, back-feed 3V3, use pin 1, or use ESP32
strapping pins. This USB-powered prototype does not provide a daughter-board
5 V rail; a larger load needs its own independently protected supply.
