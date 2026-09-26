#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, "/home/louis/arb-cap")
import live001 as live
import record_dlmm as d
live.load_dotenv()
bal = d.rpc("getBalance", ["HHNzjTABPAbPY5uEXU7NTvfmcD9RYTdXtLntyKAtpXLX"])
print("rpc_ok", 1)
print("bal", bal)
