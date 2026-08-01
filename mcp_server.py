import csv
import json
import os
from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server
mcp = FastMCP("SuitabilityDataServer")

# Resolve the absolute path to the data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def validate_client_id(client_id: str):
    """Enforce security access control by ensuring queries are scoped to a single valid client_id."""
    if not client_id or not isinstance(client_id, str):
        raise ValueError("Security Violation: Client ID must be a non-empty string.")
    
    # Strip any potential whitespace
    client_id = client_id.strip()
    
    # Basic format validation to prevent SQL-like injection or path traversal attempts
    if not (client_id.startswith("C") and client_id[1:].isdigit()):
        raise ValueError(f"Security Violation: Invalid client_id format '{client_id}'. Must be C followed by digits.")

@mcp.tool()
def get_client(client_id: str) -> str:
    """Fetch client profile for a specific client_id.
    
    Access is strictly scoped to a single client_id to prevent bulk data access.
    """
    validate_client_id(client_id)
    clients_path = os.path.join(DATA_DIR, "clients.csv")
    
    if not os.path.exists(clients_path):
        raise FileNotFoundError(f"Clients database file not found at {clients_path}")
        
    with open(clients_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["client_id"].strip() == client_id.strip():
                return json.dumps(row, indent=2)
                
    raise KeyError(f"Client {client_id} not found in database.")

@mcp.tool()
def get_holdings(client_id: str) -> str:
    """Fetch holding records for a specific client_id.
    
    Access is strictly scoped to a single client_id to prevent bulk data access.
    """
    validate_client_id(client_id)
    holdings_path = os.path.join(DATA_DIR, "holdings.csv")
    
    if not os.path.exists(holdings_path):
        raise FileNotFoundError(f"Holdings database file not found at {holdings_path}")
        
    client_holdings = []
    with open(holdings_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["client_id"].strip() == client_id.strip():
                # Convert numeric values to correct type if needed (or keep as string for downstream parsing)
                client_holdings.append(row)
                
    return json.dumps(client_holdings, indent=2)

@mcp.tool()
def get_suitability_rules() -> str:
    """Fetch compliance/suitability rules configuration."""
    rules_path = os.path.join(DATA_DIR, "suitability_rules.json")
    
    if not os.path.exists(rules_path):
        raise FileNotFoundError(f"Suitability rules file not found at {rules_path}")
        
    with open(rules_path, mode="r", encoding="utf-8") as f:
        rules = json.load(f)
        
    return json.dumps(rules, indent=2)

@mcp.tool()
def get_age_allocation_norms() -> str:
    """Fetch age-bracket allocation norms benchmark configuration."""
    norms_path = os.path.join(DATA_DIR, "age_allocation_norms.json")
    
    if not os.path.exists(norms_path):
        raise FileNotFoundError(f"Age allocation norms file not found at {norms_path}")
        
    with open(norms_path, mode="r", encoding="utf-8") as f:
        norms = json.load(f)
        
    return json.dumps(norms, indent=2)

@mcp.tool()
def get_ticker_reference() -> str:
    """Fetch ticker classifications and mapping data."""
    ticker_path = os.path.join(DATA_DIR, "ticker_reference.json")
    
    if not os.path.exists(ticker_path):
        raise FileNotFoundError(f"Ticker reference file not found at {ticker_path}")
        
    with open(ticker_path, mode="r", encoding="utf-8") as f:
        ref = json.load(f)
        
    return json.dumps(ref, indent=2)

if __name__ == "__main__":
    mcp.run()
