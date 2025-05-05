from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
apiKey = os.getenv("deepseek-api-key")
baseUrl = os.getenv("base-url")

client = OpenAI(api_key=apiKey, base_url=baseUrl)

def req():
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
        ],
        stream=False
    )

    print(response.choices[0].message.content)
