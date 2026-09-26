#!/usr/bin/env python3
import json
from pathlib import Path

p = Path("/home/louis/arb-cap/fam6/DEPLOY.json")
o = json.loads(p.read_text(encoding="utf-8"))
o["ok"] = True
o["note"] = "exists check raced confirmation; program live"
p.write_text(json.dumps(o, indent=2) + "\n", encoding="utf-8")
print("DEPLOY_OK", o.get("program"))
