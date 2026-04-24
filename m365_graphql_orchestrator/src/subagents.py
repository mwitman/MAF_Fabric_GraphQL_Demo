"""Sub-agent factory functions — Sales, Customer, and Product agents for Fabric GraphQL.

Each factory creates a ChatAgent with an @ai_function tool that executes GraphQL
queries against the corresponding Fabric endpoint.  The graphql_client is injected
per-call to support per-user Fabric tokens in M365 channels (SSO/OBO).
"""

import json
import os
from pathlib import Path

from agent_framework import ChatAgent, ai_function

_prompts_dir = Path(__file__).resolve().parent.parent / "prompts"


# ---------------------------------------------------------------------------
# Sales Agent
# ---------------------------------------------------------------------------

def create_sales_agent(client, graphql_client) -> ChatAgent:
    """Create the Sales Agent with a Fabric GraphQL function tool."""
    endpoint_url = os.environ["FABRIC_SALES_GRAPHQL_URL"]
    instructions = (_prompts_dir / "sales_agent.md").read_text(encoding="utf-8")

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
        instructions=instructions,
        name="Sales Agent",
        description="Queries sales data (orders, order details, totals, status) via Fabric GraphQL.",
        tools=[query_sales_data],
    )


# ---------------------------------------------------------------------------
# Customer Agent
# ---------------------------------------------------------------------------

def create_customer_agent(client, graphql_client) -> ChatAgent:
    """Create the Customer Agent with a Fabric GraphQL function tool."""
    endpoint_url = os.environ["FABRIC_CUSTOMER_GRAPHQL_URL"]
    instructions = (_prompts_dir / "customer_agent.md").read_text(encoding="utf-8")

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
        instructions=instructions,
        name="Customer Agent",
        description="Queries customer data (identity, addresses, address types) via Fabric GraphQL.",
        tools=[query_customer_data],
    )


# ---------------------------------------------------------------------------
# Product Agent
# ---------------------------------------------------------------------------

def create_product_agent(client, graphql_client) -> ChatAgent:
    """Create the Product Agent with a Fabric GraphQL function tool."""
    endpoint_url = os.environ["FABRIC_PRODUCT_GRAPHQL_URL"]
    instructions = (_prompts_dir / "product_agent.md").read_text(encoding="utf-8")

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
        instructions=instructions,
        name="Product Agent",
        description="Queries product data (products, categories, models, descriptions) via Fabric GraphQL.",
        tools=[query_product_data],
    )
