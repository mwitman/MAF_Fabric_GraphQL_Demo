"""Customer Agent — queries customer data via Fabric GraphQL.

This sub-agent is used by the orchestrator to answer customer-related questions
(customer identity, addresses, address types, etc.).
"""

import json
import os
from pathlib import Path

from agent_framework import ChatAgent, ai_function

_prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "customer_agent.md"
_instructions = _prompt_path.read_text(encoding="utf-8")


def create_customer_agent(client, graphql_client):
    """Create the Customer Agent with a Fabric GraphQL function tool.

    Args:
        client: ``AzureOpenAIResponsesClient`` instance.
        graphql_client: ``FabricGraphQLClient`` instance for Fabric auth.

    Returns:
        An Agent Framework agent configured for customer data queries.
    """
    endpoint_url = os.environ["FABRIC_CUSTOMER_GRAPHQL_URL"]

    @ai_function(
        name="query_customer_data",
        description=(
            "Execute a GraphQL query against the Customer data in Fabric. "
            "Use this to retrieve customer identity, addresses (billing, "
            "shipping, main office), and related customer information."
        ),
    )
    async def query_customer_data(query: str, variables: str = "{}") -> str:
        """Execute a GraphQL query against the Customer data endpoint in Fabric.

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
        name="Customer Agent",
        description="Queries customer data (identity, addresses, address types) via Fabric GraphQL.",
        tools=[query_customer_data],
    )
