"""Regenerate src/kyrosSting.ts from the supplied animated mark."""
import json
svg = open("logos/kyros-sting-forest-mark-animated.svg", encoding="utf-8").read()
open("src/kyrosSting.ts", "w", encoding="utf-8").write(
    "/* AUTO-GENERATED — do not edit. Run scripts/gen_sting.py */\n"
    "export const KYROS_STING_SVG = " + json.dumps(svg) + ";\n")
print("wrote src/kyrosSting.ts")
