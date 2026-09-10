# Pod-node interconnect contract

PNB-1 exposes J3 as a 2x6, 2.54 mm daughter-board connector.

| Pin | Signal | Direction from base | Limit |
| --- | --- | --- | --- |
| 1 | 5V | output | 500 mA |
| 2 | GND | - | - |
| 3 | 3V3 | output | 150 mA |
| 4 | GND | - | - |
| 5 | SDA | bidirectional | 3.3 V; pull-ups on base only |
| 6 | SCL | bidirectional | 3.3 V; pull-ups on base only |
| 7 | GPIO7 | bidirectional | - |
| 8 | GPIO8 | bidirectional | - |
| 9 | GPIO4 | input | ADC1, 0-3.1 V |
| 10 | GPIO9 | input | ADC1, 0-3.1 V |
| 11 | GPIO10 | bidirectional | - |
| 12 | GPIO1 | input | open-drain interrupt; base pull-up |

Daughters MUST NOT add I2C pull-ups, back-feed either supply, or use ESP32
strapping pins. A daughter that exceeds the 3.3 V budget MUST regulate from
5 V itself.
