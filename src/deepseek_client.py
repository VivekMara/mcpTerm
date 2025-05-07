from contextlib import AsyncExitStack
import json
from openai import OpenAI
from dotenv import load_dotenv
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console
from rich.markdown import Markdown

load_dotenv()
apiKey = os.getenv("deepseek-api-key")

class MCPClient:
    def __init__(self):
        self.deepseek = OpenAI(api_key=apiKey, base_url="https://api.deepseek.com")
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.console = Console()

    async def connect_to_server(self, server_path:str):
        server_params = StdioServerParameters(command="python", args=[server_path], env=None)

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        self.console.print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str):
            msgs = [
            {
                "role": "system",
                "content": "You are JARVIS, a helpful AI personal assistant who is willing to serve his master by all means necessary. Always look how the user's query can be solved using the available tools. If the user's query doesn't need any tool calls, only then resort to solve the query using your own intelligence. "
            },
            {
                "role": "user",
                "content": query
            }
            ]
            final_text = []
            assistant_message_content = []
            response = await self.session.list_tools()

            available_tools = []
            for tool in response.tools:
                tool_desc = {
                    "type":"function",
                    "function":{
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                }
                available_tools.append(tool_desc)

            with self.console.status("[bold green] Processing...", spinner="dots"):
                resp1 = self.deepseek.chat.completions.create(
                    model="deepseek-chat",
                    max_tokens=1000,
                    messages=msgs,
                    tools=available_tools
                )

            if resp1.choices[0].message.tool_calls == None:
                final_text.append(resp1.choices[0].message.content)
                assistant_message_content.append(resp1.choices[0].message.content)
                self.console.print(final_text[0])
            else:
                with self.console.status("[bold green] Processing your request...", spinner="dots"):
                    for i in resp1.choices[0].message.tool_calls:
                        tool_name = i.function.name
                        tool_args = json.loads(i.function.arguments)

                        result = await self.session.call_tool(tool_name, tool_args)
                        final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
                        assistant_message_content.append(str(i.function))
                        msgs.append({
                            "role": "assistant",
                            "content": str(assistant_message_content)
                        })
                        msgs.append({
                            "role": "user",
                            "content": str(result.content)
                        })
                        resp2 = self.deepseek.chat.completions.create(
                            model="deepseek-chat",
                            max_tokens=1000,
                            messages=msgs,
                            tools=available_tools
                        )
                        formatted = Markdown(resp2.choices[0].message.content)
                        final_text.append(formatted)
                for i in final_text:
                    self.console.print(i)

    async def chat_loop(self):
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        while True:
            try:
                query = input("\nQuery: ").strip()
                if query.lower() == 'quit':
                    break
                await self.process_query(query)
            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        await self.exit_stack.aclose()
