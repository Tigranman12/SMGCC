#!/usr/bin/env python3
"""Entry point for the SMGCC Stage 1 playground. See smgcc/repl.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smgcc.repl import run

if __name__ == "__main__":
    raise SystemExit(run(sys.argv))
