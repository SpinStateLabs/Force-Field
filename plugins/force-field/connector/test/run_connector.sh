#!/usr/bin/env bash
# Estate connector tests (stdlib only):  bash plugins/force-field/connector/test/run_connector.sh
set -eu
cd "$(dirname "$0")"
python3 -m unittest -v test_estate_connector 2>&1
