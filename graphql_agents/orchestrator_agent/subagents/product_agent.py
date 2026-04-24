"""Product Agent — queries product data via Fabric GraphQL.

This sub-agent is used by the orchestrator to answer product-related questions
(products, categories, models, descriptions, etc.).
"""

import json
import os
from pathlib import Path

from agent_framework import ChatAgent, ai_function

_prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "product_agent.md"
_instructions = _prompt_path.read_text(encoding="utf-8")


def create_product_agent(client, graphql_client):
    """Create the Product Agent with a Fabric GraphQL function tool.

    Args:
        client: ``AzureOpenAIResponsesClient`` instance.
        graphql_client: ``FabricGraphQLClient`` instance for Fabric auth.

    Returns:
        An Agent Framework agent configured for product data queries.
    """
    endpoint_url = os.environ["FABRIC_PRODUCT_GRAPHQL_URL"]

    @ai_function(
        name="query_product_data",
        description=(
            "Execute a GraphQL query against the Product data in Fabric. "
            "Use this to retrieve products, product categories, product models, "
            "product descriptions, and related product information."
        ),
    )
    async def query_product_data(query: str, variables: str = "{}") -> str:
        """Execute a GraphQL query against the Product data endpoint in Fabric.

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
        name="Product Agent",
        description="Queries product data (products, categories, models, descriptions) via Fabric GraphQL.",
        tools=[query_product_data],
    )
