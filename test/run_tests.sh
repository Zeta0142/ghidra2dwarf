#!/bin/sh
set -e

cd "$(dirname "$0")"
./generate_dbg.py
python3 -m pytest .
