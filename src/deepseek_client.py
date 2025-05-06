from contextlib import AsyncExitStack
import json
from openai import OpenAI
from dotenv import load_dotenv
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()
apiKey = os.getenv("deepseek-api-key")
baseUrl = os.getenv("base-url")

client = OpenAI(api_key=apiKey, base_url=baseUrl)

def req():
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "What is the weather like in Paris today?"},
        ],
        tools=[{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current temperature for a given location.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City and country e.g. Bogotá, Colombia"
                        }
                    },
                    "required": [
                        "location"
                    ],
                    "additionalProperties": False
                },
                "strict": True
            }
        }]
    )

    print(response.choices[0].message.tool_calls[0].function.arguments)
    # print(response.choices[0].message.tool_calls.id)
    # print(response.choices[0].message.tool_calls.function.arguments)

class MCPClient:
    def __init__(self):
        self.deepseek = OpenAI(api_key=apiKey, base_url=baseUrl)
        self.session = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self, server_path:str):
        server_params = StdioServerParameters(command="python", args=[server_path], env=None)

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        msgs = [
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

        resp1 = self.deepseek.chat.completions.create(
            model="deepseek-chat",
            max_tokens=1000,
            messages=msgs,
            tools=available_tools
        )

        if resp1.choices[0].message.tool_calls == None:
            final_text.append(resp1.choices[0].message.content)
            assistant_message_content.append(resp1.choices[0].message.content)
        else:
            for i in resp1.choices[0].message.tool_calls:
                tool_name = i.function.name
                tool_args = json.loads(i.function.arguments)

                result = await self.session.call_tool(tool_name, tool_args)
                final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
                assistant_message_content.append(str(i.function))
                # can you tell me the weather forecast at san francisco?
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
                final_text.append(resp2.choices[0].message.content)
        return "\n".join(final_text)

    async def chat_loop(self):
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        while True:
            try:
                query = input("\nQuery: ").strip()
                if query.lower() == 'quit':
                    break
                response = await self.process_query(query)
                print("\n" + response)
            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        await self.exit_stack.aclose
