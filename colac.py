#!/usr/bin/env python3
"""SMGCC COLA compiler CLI — compiles LW_OS COLA source to COLA-VM bytecode."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cola.driver import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
