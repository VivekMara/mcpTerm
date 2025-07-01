from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json
import uuid
from datetime import datetime

class Agent:
    def __init__(self, llm):
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.mcp_servers_path = "./mcp_servers"
        self.session_start_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_msgs = [{
            "id": str(uuid.uuid4()),
            "role": "system",
            "content": f"You are JARVIS, a personal AI assistant.You run in a loop of Thought, Action, PAUSE, Observation. At the end of the loop you output an Answer.Use Thought to describe your thoughts about the question or command you have been given.Use Action to run one of the available actions - then return PAUSE.Observation will be the result of running those actions.The current time is {self.session_start_time}. You also have the ability to revisit earlier conversations with the user as all the past conversations have been stored in a vector database. The name of the tool is query_convos which takes a query string (note that when calling the tool you must specify the name of the argument as `query` and nothing else) and returns a list of similar conversation messages between the user. You can call it whenever you feel like it's need to better help the user. When accessing, if you get no results then keep calling the tool with different queries until you get the desired result."
        }]
        self.llm = llm
    
    async def connect_to_server(self, server_path:str):
        server_params = StdioServerParameters(command="python", args=[server_path], env=None)

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        response = await self.session.list_tools()
        tools = response.tools
        return tools
    
    async def process_query(self, query: str, max_iterations: int) -> list:
        current_iteration = 0
        self.session_msgs.append({
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": query
        })
        final_text = []
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
                
        while current_iteration < max_iterations:
            current_iteration += 1
            resp = self.llm(messages = self.session_msgs, available_tools=available_tools)
            message = resp.choices[0].message
            if message.tool_calls is None:
                final_text.append(message.content)
                self.session_msgs.append({
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": str(message.content)
                })
                return final_text
            else:
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "query_convos":
                        tool_name = "query_convos"
                        arguments = json.loads(tool_call.function.arguments)
                        tool_args = arguments
                        query = arguments["query"]
                        content = self.query_convos(query)
                    else:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        result = await self.session.call_tool(tool_name, tool_args)
                        content = result.content
                    self.session_msgs.append({
                        "id": str(uuid.uuid4()),
                        "role": "assistant",
                        "content": f"Action: {tool_name}({tool_args})\nPAUSE"
                    })
                    self.session_msgs.append({
                        "id": str(uuid.uuid4()),
                        "role": "user",
                        "content": f"Observation: {content}"
                    })
        return final_text
    
    async def cleanup(self):
        await self.exit_stack.aclose()