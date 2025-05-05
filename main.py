import asyncio
from src.deepseek_client import MCPClient
import os

async def main():
    client = MCPClient()
    try:
        server_path = os.path.expanduser("~/code/JARVIS/src/mcp_server.py")
        await client.connect_to_server(server_path=server_path)
        await client.chat_loop()
    finally:
        await client.cleanup()



if __name__ == "__main__":
    asyncio.run(main())
