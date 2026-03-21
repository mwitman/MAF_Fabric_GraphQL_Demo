"""Entry point for the M365 Agents SDK Fabric Data Agents Orchestrator.

Usage:
    python -m src.main
"""

# Enable logging for the Microsoft Agents library
import logging

ms_agents_logger = logging.getLogger("microsoft_agents")
ms_agents_logger.addHandler(logging.StreamHandler())
ms_agents_logger.setLevel(logging.INFO)

from .agent import AGENT_APP, CONNECTION_MANAGER  # noqa: E402
from .start_server import start_server  # noqa: E402

start_server(
    agent_application=AGENT_APP,
    auth_configuration=CONNECTION_MANAGER.get_default_connection_configuration(),
)
