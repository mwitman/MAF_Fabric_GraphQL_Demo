"""Probe Fabric GraphQL endpoint — fetch one row from each known entity.

Fabric disables introspection, so we query each entity with all known
fields and report what comes back (and what errors).
"""

import json
import requests
from azure.identity import DefaultAzureCredential

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
GRAPHQL_URL = "https://3e84e2ea9eb64fe8be951b26823c983e.z3e.graphql.fabric.microsoft.com/v1/workspaces/3e84e2ea-9eb6-4fe8-be95-1b26823c983e/graphqlapis/5d5ccd2a-2153-4f10-9152-bd512aa30d22/graphql"

# Each entry: (query_name, fields_to_try)
PROBES = [
    ("salesOrderHeaders", "SalesOrderID RevisionNumber OrderDate DueDate ShipDate Status CustomerID ShipToAddressID BillToAddressID ShipMethod CreditCardApprovalCode SubTotal TaxAmt Freight Comment rowguid ModifiedDate"),
    ("salesOrderDetails", "SalesOrderID SalesOrderDetailID OrderQty ProductID UnitPrice UnitPriceDiscount rowguid ModifiedDate"),
    ("customers", "CustomerID Title Suffix CompanyName SalesPerson EmailAddress PasswordHash PasswordSalt rowguid ModifiedDate"),
    ("addresses", "AddressID AddressLine1 AddressLine2 City PostalCode rowguid ModifiedDate"),
    ("customerAddresses", "CustomerID AddressID rowguid ModifiedDate"),
    ("products", "ProductID ProductNumber Color StandardCost ListPrice Size Weight ProductCategoryID ProductModelID SellStartDate SellEndDate DiscontinuedDate ThumbnailPhotoFileName rowguid ModifiedDate"),
    ("productCategories", "ProductCategoryID ParentProductCategoryID rowguid ModifiedDate"),
    ("productModels", "ProductModelID rowguid ModifiedDate"),
    ("productDescriptions", "ProductDescriptionID Description rowguid ModifiedDate"),
    ("productModelProductDescriptions", "ProductModelID ProductDescriptionID Culture rowguid ModifiedDate"),
]

credential = DefaultAzureCredential()
token = credential.get_token(FABRIC_SCOPE).token
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

results = {}
for entity, fields in PROBES:
    query = f"{{ {entity}(first: 1) {{ items {{ {fields} }} }} }}"
    resp = requests.post(GRAPHQL_URL, json={"query": query}, headers=headers, timeout=30)
    data = resp.json()

    if "errors" in data:
        results[entity] = {"status": "ERROR", "errors": [e["message"] for e in data["errors"]]}
    else:
        items = data.get("data", {}).get(entity, {}).get("items", [])
        if items:
            results[entity] = {"status": "OK", "fields": list(items[0].keys()), "sample": items[0]}
        else:
            results[entity] = {"status": "OK (empty)", "fields": fields.split()}

print(json.dumps(results, indent=2, default=str))
