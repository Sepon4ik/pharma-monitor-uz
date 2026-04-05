"""Entry point for Streamlit Cloud deployment."""
import subprocess
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

# Re-export the dashboard app
from src.pharma_monitor.dashboard.app import *
