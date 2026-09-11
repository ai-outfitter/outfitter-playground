# PNB-1 correction review

Reviewed commit: `6b8905922612fd2e91e1ca8a7fbedf8db5887762`

Three read-only, cold-context lanes reviewed the committed design before the
next correction was applied:

- schematic/BOM lane: resident review task `pnb_schematic_review`
- PCB/layout lane: resident review task `pnb_layout_review`
- repository/gate lane: Claude Code session
  `446d7c7d-e094-491c-a0d8-33b40d1cce62` in a detached snapshot

## Accepted findings

1. **Blocker — incorrect SCD41 land pattern.** The footprint modeled a
   fictitious central pad 21. Sensirion specifies 20 perimeter lands, a central
   4.8 x 4.8 mm keep-free area, and a 0.25 mm NPTH relief hole between lands 10
   and 11. This requires symbol, footprint, net, route, ERC, DRC, and fabrication
   regeneration.
2. **Blocker — C9 identity mismatch.** The BOM named TAJA226K010RNJ/C11366, but
   the canonical SKiDL source and generated schematic instantiated the former
   non-polarized MLCC symbol. The exact polarized symbol, pad map, model, and
   assembly polarity evidence are required.
3. **Blocker — thermal evidence was materially wrong.** The comment claimed
   approximately 149 C at 680 mA; the actual declared 617 mA peak evaluates to
   192.7 C under the same model. The assumed theta-JA and firmware-enforced
   sustained-current limit must be visible waivers, not an unconditional pass.
4. **Major — the footprint-pad self-test was vacuous.** `verify.py --selftest`
   did not supply a pad map and therefore skipped that gate.
5. **Major — KiCad MCP board validation did not gate exit status.** The result
   was recorded but not asserted.
6. **Major — J3 was not an exact orderable assembly part.** Preserve the
   electrical/mechanical footprint but mark it DNP and exclude it from BOM/CPL
   until an exact header is sourced.
7. **Major — USB audit drifted.** Restore the under-30 mm limit and report the
   asymmetric layer changes instead of hiding them behind a loosened threshold.
8. **Major — C9 used a transient `/tmp` 3D-model path.** Commit the exact vendor
   WRL and use a project-relative reference.

## Evidence limits

This review covers digital source and generated artifacts only. It does not
prove authenticated supplier acceptance, component stock, assembled thermal or
RF behavior, firmware USB-current behavior, sensor accuracy, or physical yield.
