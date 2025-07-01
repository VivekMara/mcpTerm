import asyncio
from mcp_client import MCPClient
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

async def animate_intro():
    frames = [
        "Loading JARVIS.",
        "Loading JARVIS..",
        "Loading JARVIS...",
    ]
    with Live(Panel("Loading JARVIS"), refresh_per_second=4) as live:
        for _ in range(2):  # 2 loops through the animation
            for frame in frames:
                live.update(Panel(Text(frame, justify="center")))
                await asyncio.sleep(0.3)

async def main():
    await animate_intro()
    client = MCPClient()
    await client.chat_loop()

if __name__ == "__main__":
    asyncio.run(main())
