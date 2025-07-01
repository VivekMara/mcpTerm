import json
from openai import OpenAI
from dotenv import load_dotenv
import os
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from sentence_transformers import SentenceTransformer
import chromadb
from src.agent import Agent
from datetime import datetime

load_dotenv()
apiKey = os.getenv("deepseek-api-key")

class MCPClient:
    def __init__(self):
        self.deepseek = OpenAI(api_key=apiKey, base_url="https://api.deepseek.com")
        self.console = Console(record=True)
        self.mcp_servers_path = "./mcp_servers"
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        self.chromadb_client = chromadb.PersistentClient("./vector_data")
        self.session_start_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.agent = Agent(self.llm)
    
    def llm(self, messages, available_tools):
        return self.deepseek.chat.completions.create(
            model="deepseek-chat",
            max_tokens=1000,
            messages=messages,
            tools=available_tools
        )
    
    def save_convos(self):
        with open(f"./convos/user_convo{self.session_start_time}.json", "w") as f:
            json.dump(self.agent.session_msgs, f, indent=4)
        collection = self.chromadb_client.get_or_create_collection("user_convos")
        embeddings = self.embedding_model.encode(self.agent.session_msgs)
        ids = []
        for msg in self.agent.session_msgs:
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

    async def chat_loop(self):
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
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
            await self.agent.connect_to_server(f"{self.mcp_servers_path}/{server_name}")
        except Exception as e:
            self.console.print(f"\nError: {e}")
            await self.agent.cleanup()
        while True:
            try:
                query = self.console.input("\n [bold cyan]Query: ").strip()
                if query.lower() == 'quit':
                    self.save_convos()
                    await self.agent.cleanup()
                    break
                resp = await self.agent.process_query(query, 5)
                for i in resp:
                    self.console.print(Markdown(i))
            except Exception as e:
                self.console.print(f"\nError: {str(e)}")