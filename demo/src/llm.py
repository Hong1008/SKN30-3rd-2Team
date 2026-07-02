from openai import OpenAI
from config import app_env, WORKSHIELD_MCP_URL

client = OpenAI()
workshield = {
    "type": "mcp",
    "server_label": "workshield",
    "server_description": "WorkShield MCP server to assist with ",
    "server_url": WORKSHIELD_MCP_URL,
    "require_approval": "never",
}

tools = [workshield]

def invoke_workshield(user_message: str) -> str:
    resp = client.responses.create(
        model="gpt-5.5",
        tools=tools,
    )
    return resp.output_text