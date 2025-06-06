from contextlib import AsyncExitStack
import json
from openai import OpenAI
from dotenv import load_dotenv
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from sentence_transformers import SentenceTransformer
import chromadb
from datetime import datetime
import uuid

load_dotenv()
apiKey = os.getenv("deepseek-api-key")

class MCPClient:
    def __init__(self):
        self.deepseek = OpenAI(api_key=apiKey, base_url="https://api.deepseek.com")
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.console = Console(record=True)
        self.mcp_servers_path = "./mcp_servers"
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        self.chromadb_client = chromadb.PersistentClient("./vector_data")
        self.session_msgs = []
        self.session_start_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        system_msg = {
            "id": str(uuid.uuid4()),
            "role": "system",
            "content": f"You are JARVIS, a personal AI assistant.You run in a loop of Thought, Action, PAUSE, Observation. At the end of the loop you output an Answer.Use Thought to describe your thoughts about the question or command you have been given.Use Action to run one of the available actions - then return PAUSE.Observation will be the result of running those actions.The current time is {self.session_start_time}. You also have the ability to revisit earlier conversations with the user as all the past conversations have been stored in a vector database. The name of the tool is query_convos which takes a query string (note that when calling the tool you must specify the name of the argument as `query` and nothing else) and returns a list of similar conversation messages between the user. You can call it whenever you feel like it's need to better help the user. When accessing, if you get no results then keep calling the tool with different queries until you get the desired result."
        }
        self.session_msgs.append(system_msg)

    def save_convos(self):
        with open(f"./convos/user_convo{self.session_start_time}.json", "w") as f:
            json.dump(self.session_msgs, f, indent=4)
        collection = self.chromadb_client.get_or_create_collection("user_convos")
        embeddings = self.embedding_model.encode(self.session_msgs)
        ids = []
        for msg in self.session_msgs:
            ids.append(msg["id"])
        collection.upsert(embeddings=embeddings, ids=ids)

    def query_convos(self, query) -> list:
        collection = self.chromadb_client.get_or_create_collection("user_convos")
        query_embeddings = self.embedding_model.encode(query)
        result = collection.query(query_embeddings=query_embeddings, n_results=5)
        ids = result["ids"]
        self.console.print(ids)
        convo_files = os.listdir("./convos")
        matched_msgs = []
        for file in convo_files:
            self.console.print(file)
            with open(f"./convos/{file}", "r") as f:
                content = json.load(f)
                for i in ids:
                    for j in i:
                        for msg in content:
                            if msg["id"] == j:
                                matched_msgs.append(msg)

        if len(matched_msgs) == 0:
            return "No msg matches the query"
        else:
            return matched_msgs

    async def startup_menu(self):
        table = Table(title="List of mcp servers")
        table.add_column("Index", justify="centre", style="cyan", no_wrap=True)
        table.add_column("Title", justify="centre", style="cyan", no_wrap=True)
        table.add_column("Description", justify="centre", style="cyan", no_wrap=True)
        mcp_servers = os.listdir(self.mcp_servers_path)
        index = 0
        for server in mcp_servers:
            index += 1
            table.add_row(str(index), server, "TBD")
        self.console.print(table)
        try:
            inp = self.console.input("\n [bold cyan]So what server are you choosing?? (specify the index): ")
            server_name = mcp_servers[int(inp) - 1]
            await self.connect_to_server(f"{self.mcp_servers_path}/{server_name}")
        except Exception as e:
            self.console.print(f"\nError: {e}")
            await self.cleanup()

    async def connect_to_server(self, server_path:str):
        server_params = StdioServerParameters(command="python", args=[server_path], env=None)

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        response = await self.session.list_tools()
        tools = response.tools
        self.console.print("\nConnected to server with tools:", [tool.name for tool in tools])

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

            with self.console.status("[bold green] Thinking...", spinner="dots"):
                while current_iteration < max_iterations:
                    current_iteration += 1
                    resp = self.deepseek.chat.completions.create(
                        model="deepseek-chat",
                        max_tokens=1000,
                        messages=self.session_msgs,
                        tools=available_tools
                    )
                    message = resp.choices[0].message
                    self.console.print(message)
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

                            self.console.print(f"[Calling tool {tool_name} with args {tool_args}]")
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
                self.console.print("[yellow] Max iterations reached.")
            return final_text

    async def chat_loop(self):
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        while True:
            try:
                query = self.console.input("\n [bold cyan]Query: ").strip()
                if query.lower() == 'quit':
                    self.save_convos()
                    break
                resp = await self.process_query(query, 5)
                for i in resp:
                    self.console.print(Markdown(i))
            except Exception as e:
                self.console.print(f"\nError: {str(e)}")

    async def cleanup(self):
        await self.exit_stack.aclose()
