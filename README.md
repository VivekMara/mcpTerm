# mcpTerm
a cli for interacting with mcp servers using your favourite llm providers
*currently only supports deepseek

---

# installation
ensure that you have uv installed or install it with
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# for linux or mac users
```
```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
#for windows users
```
```bash
git clone https://github.com/VivekMara/mcpTerm && cd mcpTerm && uv sync
```

---
add a .env file in the same project directory with the key name "deepseek-api-key"


# running
```bash
uv run main.py <"path to your mcp server">
```
