#!/bin/bash
cd "$(dirname "$0")"
python3 -m venv venv
source venv/bin/activate
python app.py
