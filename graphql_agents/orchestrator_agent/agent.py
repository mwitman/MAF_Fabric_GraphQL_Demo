"""GraphQL Agents Orchestrator — orchestrator with Sales, Customer, Product sub-agents.

Architecture:
    Orchestrator Agent
    ├── Sales Agent      → query_sales_data()      → Fabric GraphQL
    ├── Customer Agent   → query_customer_data()   → Fabric GraphQL
    └── Product Agent    → query_product_data()    → Fabric GraphQL

Each sub-agent is a full Agent Framework agent with its own instructions and
a Fabric GraphQL function tool.  The orchestrator delegates to the appropriate
sub-agent(s) based on the user's query via agent-as-tool conversion.

DevUI discovers this agent via the __init__.py that exports ``agent``.
"""

import os
from pathlib import Path

from azure.identity import DefaultAzureCredential
from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIResponsesClient
from dotenv import load_dotenv

from .graphql_client import FabricGraphQLClient
from .subagents.sales_agent import create_sales_agent
from .subagents.customer_agent import create_customer_agent
from .subagents.product_agent import create_product_agent

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

# ---------------------------------------------------------------------------
# Load orchestrator system prompt
# ---------------------------------------------------------------------------
_prompt_path = Path(__file__).resolve().parent / "prompts" / "orchestrator_agent.md"
_instructions = _prompt_path.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Entra ID authentication (DefaultAzureCredential — az login for local dev)
# ---------------------------------------------------------------------------
credential = DefaultAzureCredential()

# ---------------------------------------------------------------------------
# Azure OpenAI client
# ---------------------------------------------------------------------------
client = AzureOpenAIResponsesClient(
    endpoint=os.environ["AOAI_ENDPOINT"],
    api_key=os.environ["AOAI_KEY"],
    deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
)

# ---------------------------------------------------------------------------
# Fabric GraphQL client (shared across all sub-agents)
# ---------------------------------------------------------------------------
graphql_client = FabricGraphQLClient(credential=credential)

# ---------------------------------------------------------------------------
# Sub-agents — each is an Agent Framework agent with a GraphQL function tool
# ---------------------------------------------------------------------------
sales_agent = create_sales_agent(client, graphql_client)
customer_agent = create_customer_agent(client, graphql_client)
product_agent = create_product_agent(client, graphql_client)

# ---------------------------------------------------------------------------
# Convert sub-agents to tools for the orchestrator
# ---------------------------------------------------------------------------
sales_tool = sales_agent.as_tool(
    name="sales_agent",
    description=(
        "Delegate to the Sales Agent for sales-related queries — orders, "
        "order details, order totals, order status, and related sales data."
    ),
)

customer_tool = customer_agent.as_tool(
    name="customer_agent",
    description=(
        "Delegate to the Customer Agent for customer-related queries — "
        "customer identity, addresses (billing, shipping, main office), "
        "and related customer data."
    ),
)

product_tool = product_agent.as_tool(
    name="product_agent",
    description=(
        "Delegate to the Product Agent for product-related queries — "
        "products, product categories, models, descriptions, and related "
        "product data."
    ),
)

# ---------------------------------------------------------------------------
# Orchestrator agent
# ---------------------------------------------------------------------------
agent = ChatAgent(
    client,
    instructions=_instructions,
    name="GraphQL Agents Orchestrator",
    description=(
        "Orchestrates three Agent Framework sub-agents (Sales, Customer, Product) "
        "that use Fabric GraphQL APIs for data retrieval to answer business "
        "questions across orders, customers, addresses, products, categories, "
        "and more."
    ),
    tools=[sales_tool, customer_tool, product_tool],
)
