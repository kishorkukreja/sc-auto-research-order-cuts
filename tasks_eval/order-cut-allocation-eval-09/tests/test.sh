#!/bin/bash
set -euo pipefail

python /tests/test.py || {
  mkdir -p /logs/verifier
  echo 0.0 > /logs/verifier/reward.txt
}
