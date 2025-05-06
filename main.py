import asyncio
from src.deepseek_client import MCPClient
import os
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
    if len(sys.argv) < 2:
        print("Usage: uv run main.py <path_to_server_script>")
        sys.exit(1)

    await animate_intro()
    client = MCPClient()
    try:
        server_path = os.path.expanduser(sys.argv[1])
        await client.connect_to_server(server_path=server_path)
        await client.chat_loop()
    finally:
        await client.cleanup()



if __name__ == "__main__":
    import sys
    asyncio.run(main())
