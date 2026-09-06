#!/usr/bin/env python3
import json
from pathlib import Path

matrix = json.loads(Path("compatibility.json").read_text(encoding="utf-8"))
columns = set(matrix["columns_after_migration"])
incompatible = [
    worker["version"]
    for worker in matrix["deployed_workers"]
    if not set(worker["reads"]) <= columns
]
if incompatible:
    print("FAIL incompatible deployed workers: " + ", ".join(incompatible))
    raise SystemExit(1)
print("PASS all deployed readers are compatible")
