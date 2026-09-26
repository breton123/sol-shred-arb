#!/usr/bin/env python3
import sys
sys.path.insert(0, "/home/louis/arb-cap")
sys.path.insert(0, "/home/louis/arb-cap/paper004")
import live001 as live
import paper004 as p4

W = "HHNzjTABPAbPY5uEXU7NTvfmcD9RYTdXtLntyKAtpXLX"
OUR = "38dsYLgtLkHKDMYNBemkEM3WkvZSUo3RvxZSm7eMDj4K"
KNOWN = [
    "3q6BM1m6EJkLVvXBbF8haSMnk6msVCY7U1awYoX96ufodD8byML3Nhct2k267cqsrxWafwTeFG2k1HWENbvDg2kr",
    "2sWq5TfJF1xpPFQsYa4bhT6n2iJ18AE5wBMWw3ECkAkeVzzTsYkA52UqdXnCFEHLHyjrBdfvvUZgjWUM7w5QKWax",
    "2AG2QyLuAtbwXZWU6W5G3ByzvD71P6QSjjHvxhXsVkvxmPhYy5vs5VhFKbe2KVSv5JrZX5Svy7XuU25LEEpy7WZY",
    "yn7yJjDa1SLChivbUyDY7J7Y3vZxkYs7ZGDb1wvUjXngAD53Cv5WqSGqKSN7KC1STNZ5mgKbKq7Xpf9NRwdyzfk",
]


def main():
    live.load_dotenv()
    for sig in KNOWN:
        tx = p4.fetch_tx(sig)
        st = p4.rpc("getSignatureStatuses", [[sig], {"searchTransactionHistory": True}])
        print({
            "sig": sig[:20],
            "slot": (tx or {}).get("slot"),
            "bt": (tx or {}).get("blockTime"),
            "err": ((tx or {}).get("meta") or {}).get("err") if tx else (st or {}).get("value"),
            "fee": ((tx or {}).get("meta") or {}).get("fee") if tx else None,
            "cu": ((tx or {}).get("meta") or {}).get("computeUnitsConsumed") if tx else None,
        })


if __name__ == "__main__":
    raise SystemExit(main() or 0)
