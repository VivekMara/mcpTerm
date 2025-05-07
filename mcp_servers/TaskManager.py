from datetime import datetime
import sqlite3
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("TaskManager")
dbPath = "tasks.db"

def initDB():
    with sqlite3.connect(dbPath) as connection:
        cursor = connection.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        connection.commit()

@mcp.tool()
def create_task(title: str, desc: str) -> str:
    """
    Add a new task to the database.

    Args:
        title (str): The title of the task.
        desc (str): The description of the task.

    Returns:
        str: Confirmation message or error.
    """
    try:
        with sqlite3.connect(dbPath) as connection:
            cursor = connection.cursor()
            current_time = datetime.now()
            cursor.execute("""
            INSERT INTO tasks (title, description, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """, (title, desc, "in_progress", current_time, current_time))
            connection.commit()
        return f"Task '{title}' created successfully at {current_time}"
    except sqlite3.Error as e:
        return f"Error creating task: {e}"

@mcp.tool()
def read_tasks() -> list[dict]:
    """
    Fetch all tasks from the database.

    Returns:
        list[dict]: List of tasks (each task is a dictionary with keys like 'id', 'title', etc.).
    """
    with sqlite3.connect(dbPath) as connection:
        connection.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM tasks")
        return [dict(row) for row in cursor.fetchall()]

@mcp.tool()
def update_tasks_by_keyword(keyword: str) -> str:
    """
    Mark all tasks as 'completed' if their title contains `keyword`.

    Args:
        keyword (str): Keyword to search in task titles (case-sensitive).

    Returns:
        str: Status message (e.g., "Updated 3 tasks").
    """
    try:
        with sqlite3.connect(dbPath) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tasks
                SET status = 'completed', updated_at = ?
                WHERE LOWER(title) LIKE LOWER(?) AND status != 'completed'
            """, (datetime.now(), f"%{keyword}%"))
            conn.commit()
            return f"Updated {cursor.rowcount} tasks containing '{keyword}'"
    except sqlite3.Error as e:
        return f"Error: {e}"

@mcp.tool()
def delete_tasks_by_keyword(keyword: str) -> str:
    """
    Delete tasks whose titles partially match a keyword (case-sensitive).

    Args:
        keyword (str): Keyword to search in task titles (e.g., "bug").

    Returns:
        str: Status message (e.g., "Deleted 2 tasks").
    """
    try:
        with sqlite3.connect(dbPath) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM tasks
                WHERE LOWER(title) LIKE LOWER(?)
            """, (f"%{keyword}%",))
            conn.commit()
            return f"Deleted {cursor.rowcount} tasks containing '{keyword}'"
    except sqlite3.Error as e:
        return f"Error: {e}"

if __name__ == "__main__":
    initDB()
    mcp.run(transport='stdio')
