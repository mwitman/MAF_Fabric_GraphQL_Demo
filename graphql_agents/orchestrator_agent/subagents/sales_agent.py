"""Sales Agent — queries sales data via Fabric GraphQL.

This sub-agent is used by the orchestrator to answer sales-related questions
(orders, order details, totals, status, etc.).
"""

import json
import os
from pathlib import Path

from agent_framework import ChatAgent, ai_function

_prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "sales_agent.md"
_instructions = _prompt_path.read_text(encoding="utf-8")


def create_sales_agent(client, graphql_client):
    """Create the Sales Agent with a Fabric GraphQL function tool.

    Args:
        client: ``AzureOpenAIResponsesClient`` instance.
        graphql_client: ``FabricGraphQLClient`` instance for Fabric auth.

    Returns:
        An Agent Framework agent configured for sales data queries.
    """
    endpoint_url = os.environ["FABRIC_SALES_GRAPHQL_URL"]

    @ai_function(
        name="query_sales_data",
        description=(
            "Execute a GraphQL query against the Sales data in Fabric. "
            "Use this to retrieve orders, order details, order totals, "
            "order status, and related sales information."
        ),
    )
    async def query_sales_data(query: str, variables: str = "{}") -> str:
        """Execute a GraphQL query against the Sales data endpoint in Fabric.

        Args:
            query: The GraphQL query string to execute.
            variables: JSON-encoded variables for the GraphQL query.

        Returns:
            JSON string with the query results.
        """
        parsed_vars = json.loads(variables) if variables and variables != "{}" else None
        result = await graphql_client.execute(
            endpoint_url=endpoint_url,
            query=query,
            variables=parsed_vars,
        )
        return json.dumps(result, indent=2)

    return ChatAgent(
        client,
        instructions=_instructions,
        name="Sales Agent",
        description="Queries sales data (orders, order details, totals, status) via Fabric GraphQL.",
        tools=[query_sales_data],
    )
