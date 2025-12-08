#!/usr/bin/env python3
"""
OLT Manager - Server Entry Point
This file is compiled to binary for distribution
"""
import uvicorn
import sys
import os

# Set working directory to where the executable is
if getattr(sys, 'frozen', False):
    # Running as compiled
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

from main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
