"""Entry point for the Streamlit evaluation dashboard.

Usage:
    uv run music-dashboard
"""
import subprocess
import sys
import os


def main():
    app = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streamlit_app.py")
    cmd = [sys.executable, "-m", "streamlit", "run", app] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
