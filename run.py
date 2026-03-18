"""Launch DevUI with Fabric Data Agent.

Usage:
    python run.py

Or use the DevUI CLI directly (if devui is on PATH):
    devui ./agents --port 8080
"""

from agent_framework_devui._cli import main as devui_main
import sys

if __name__ == "__main__":
    sys.argv = ["devui", "./agents", "--port", "8080"]
    devui_main()
