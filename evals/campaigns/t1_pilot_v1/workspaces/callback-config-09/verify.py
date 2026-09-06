#!/usr/bin/env python3
import json
from pathlib import Path
from urllib.parse import urlparse

config = json.loads(Path("config.json").read_text(encoding="utf-8"))
scheme = urlparse(config["callback_url"]).scheme
if config["environment"] == "production" and scheme != "https":
    print("FAIL production callback_url must use https")
    raise SystemExit(1)
print("PASS callback transport policy")
