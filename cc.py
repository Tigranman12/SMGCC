#!/usr/bin/env python3
"""SMGCC C compiler CLI. See smgcc/driver.py for usage."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smgcc.driver import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
