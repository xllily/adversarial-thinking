#!/usr/bin/env python3
import json
from pathlib import Path

result = json.loads(Path("rehearsal.json").read_text(encoding="utf-8"))
complete = set(result["deployed_worker_versions"]) == set(result["rehearsed_worker_versions"])
if complete and result["dual_write_gap_count"] == 0:
    print("PASS complete mixed-version rehearsal; zero dual-write gaps")
    raise SystemExit(0)
print("FAIL rehearsal does not defeat the legacy-worker countermodel")
raise SystemExit(1)
