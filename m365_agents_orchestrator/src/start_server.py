"""aiohttp web server for the M365 Agents SDK orchestrator.

Exposes a ``/api/messages`` endpoint that Azure Bot Service (and therefore
Teams, Outlook, Copilot, and other M365 channels) can send activities to.

Supports anonymous mode for local testing with the Bot Framework Emulator
(set ``USE_ANONYMOUS_MODE=True`` in ``.env``).
"""

from os import environ

from aiohttp.web import Application, Request, Response, run_app
from aiohttp.web_middlewares import middleware
from microsoft_agents.hosting.aiohttp import (
    CloudAdapter,
    jwt_authorization_middleware,
    start_agent_process,
)
from microsoft_agents.hosting.core import (
    AgentApplication,
    AgentAuthConfiguration,
    AuthenticationConstants,
    ClaimsIdentity,
)


def _build_anonymous_claims_middleware():
    """Middleware that injects anonymous claims so auth is bypassed locally."""

    @middleware
    async def anonymous_claims_middleware(request, handler):
        request["claims_identity"] = ClaimsIdentity(
            {
                AuthenticationConstants.AUDIENCE_CLAIM: "anonymous",
                AuthenticationConstants.APP_ID_CLAIM: "anonymous-app",
            },
            False,
            "Anonymous",
        )
        return await handler(request)

    return anonymous_claims_middleware


def start_server(
    agent_application: AgentApplication,
    auth_configuration: AgentAuthConfiguration,
    *,
    anonymous_mode: bool = False,
):
    """Start the aiohttp web server with JWT auth middleware."""

    async def entry_point(req: Request) -> Response:
        agent: AgentApplication = req.app["agent_app"]
        adapter: CloudAdapter = req.app["adapter"]
        return await start_agent_process(req, agent, adapter)

    if anonymous_mode:
        middlewares = [_build_anonymous_claims_middleware()]
    else:
        middlewares = [jwt_authorization_middleware]

    app = Application(middlewares=middlewares)
    app.router.add_post("/api/messages", entry_point)
    app["agent_configuration"] = auth_configuration
    app["agent_app"] = agent_application
    app["adapter"] = agent_application.adapter

    try:
        run_app(app, host="localhost", port=int(environ.get("PORT", 3978)))
    except Exception as error:
        raise error
