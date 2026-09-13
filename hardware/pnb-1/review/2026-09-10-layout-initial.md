# Independent layout/release review — initial pass

- Reviewed commit: `9daa079e50586a9bcbd0dd9489d5f4d6239e6178`
- Verdict: **not ready**

## Findings

1. USB D+/D- were about 41/52 mm, mismatched by about 11 mm, and not routed as
   a coupled pair.
2. Local decouplers missed the 2 mm placement target, especially at the LDO.
3. A 3V3 route crossed beneath the SCD41 body/opening region.
4. H2's installed-hardware envelope intruded into the ESP32 antenna keep-out.
5. The fabrication BOM omitted MPNs.
6. Class-wide DRC warning filters could hide new warnings.
7. Required silkscreen was clipped and the board date was absent.

This report records the cold-context gate that drove the correction pass. It
is not a verdict on later commits.
