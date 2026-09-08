#!/usr/bin/env bash
# ==========================================================================
# Dew's Furniture — run every check on the variant-aware spec blocks.
#
#   ./tools/run-tests.sh
#
# 1. liquid_lint.py            structure of every .liquid file (balanced tags)
# 2. schema validation         every {% schema %} block must be valid JSON
# 3. test-dews-spec-block.py   renders the REAL snippets and asserts on output
# 4. test-dews-pdp.js          the REAL assets/dews-pdp.js in jsdom
# 5. test-e2e.py               Liquid output -> jsdom -> shopper clicks a size
# ==========================================================================
set -uo pipefail
cd "$(dirname "$0")/.."

pass=0; fail=0
step() { echo; echo "════════════════════════════════════════════════════════════"; echo "  $1"; echo "════════════════════════════════════════════════════════════"; }
run()  { if "$@"; then pass=$((pass+1)); else fail=$((fail+1)); echo "  !! FAILED: $*"; fi }

step "1/5  Liquid structure (all .liquid files)"
run python3 tools/liquid_lint.py sections snippets layout templates

step "2/5  {% schema %} blocks are valid JSON"
run python3 - <<'PY'
import json, re, glob, sys
bad = 0; n = 0
for f in sorted(glob.glob('sections/*.liquid')) + sorted(glob.glob('templates/*.liquid')):
    m = re.search(r'{% schema %}(.*?){% endschema %}', open(f, encoding='utf-8').read(), re.DOTALL)
    if not m: continue
    n += 1
    try: json.loads(m.group(1))
    except Exception as e: bad += 1; print('  x', f, e)
print(f'  {n} schema(s) checked, {bad} invalid')
sys.exit(1 if bad else 0)
PY

step "3/5  Liquid render — snippets/dews-spec-block.liquid"
run python3 tools/test-dews-spec-block.py

step "4/5  JS unit — assets/dews-pdp.js in jsdom"
run node --check assets/dews-pdp.js
run node tools/test-dews-pdp.js

step "5/5  END TO END — Liquid output + real JS + simulated shopper"
run python3 tools/test-e2e.py

echo
echo "════════════════════════════════════════════════════════════"
if [ "$fail" -eq 0 ]; then
  echo "  ALL $pass SUITES PASSED"
else
  echo "  $pass passed, $fail FAILED"
fi
echo "════════════════════════════════════════════════════════════"
exit $((fail > 0))
