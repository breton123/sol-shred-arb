#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python pred_hour.py
python classify_pred.py
python group_corpus.py
python universe_required.py
