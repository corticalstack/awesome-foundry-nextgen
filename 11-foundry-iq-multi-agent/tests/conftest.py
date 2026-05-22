"""pytest configuration for the multi-agent tests - adds the lab directory to sys.path."""
import sys
from pathlib import Path

# Ensure the lab root (11-foundry-iq-multi-agent/) is on sys.path so that
# `from agents import ...` works regardless of where pytest is invoked from.
LAB_DIR = Path(__file__).resolve().parents[1]
if str(LAB_DIR) not in sys.path:
    sys.path.insert(0, str(LAB_DIR))
