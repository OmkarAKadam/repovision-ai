import asyncio
from backend.mcp_server import mcp

async def check_tools():
    tools = await mcp.list_tools()
    print(f"MCP OK — {len(tools)} tools")

if __name__ == "__main__":
    asyncio.run(check_tools())
