"""aiohttp web server for the M365 Agents SDK orchestrator.

Exposes a ``/api/messages`` endpoint that Azure Bot Service (and therefore
Teams, Outlook, Copilot, and other M365 channels) can send activities to.
"""

from os import environ

from microsoft_agents.hosting.core import AgentApplication, AgentAuthConfiguration
from microsoft_agents.hosting.aiohttp import (
    start_agent_process,
    jwt_authorization_middleware,
    CloudAdapter,
)
from aiohttp.web import Request, Response, Application, run_app


def start_server(
    agent_application: AgentApplication,
    auth_configuration: AgentAuthConfiguration,
):
    """Start the aiohttp web server with JWT auth middleware."""

    async def entry_point(req: Request) -> Response:
        agent: AgentApplication = req.app["agent_app"]
        adapter: CloudAdapter = req.app["adapter"]
        return await start_agent_process(req, agent, adapter)

    app = Application(middlewares=[jwt_authorization_middleware])
    app.router.add_post("/api/messages", entry_point)
    app["agent_configuration"] = auth_configuration
    app["agent_app"] = agent_application
    app["adapter"] = agent_application.adapter

    try:
        run_app(app, host="localhost", port=int(environ.get("PORT", 3978)))
    except Exception as error:
        raise error
