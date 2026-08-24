# ─────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────
import os
import asyncio
import threading
import aiosqlite
import requests
from typing import TypedDict, Annotated
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import tool, BaseTool
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages  # optimised reducer for message state
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_mcp_adapters.client import MultiServerMCPClient

# ─────────────────────────────────────────────
# Async Event Loop Setup
# ─────────────────────────────────────────────
# Dedicated async loop for backend tasks
_ASYNC_LOOP = asyncio.new_event_loop()
_ASYNC_THREAD = threading.Thread(target=_ASYNC_LOOP.run_forever, daemon=True)
_ASYNC_THREAD.start()


def _submit_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, _ASYNC_LOOP)


def run_async(coro):
    return _submit_async(coro).result()


def submit_async_task(coro):
    """Schedule a coroutine on the backend event loop."""
    return _submit_async(coro)


# ─────────────────────────────────────────────
# Environment & Config
# ─────────────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
GITHUB_PAT = os.getenv("GITHUB_PAT")


# ─────────────────────────────────────────────
# State Definition
# ─────────────────────────────────────────────
class chatstate(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# ─────────────────────────────────────────────
# Chat Models
# ─────────────────────────────────────────────
chatmodel = ChatOpenAI(model="gpt-4o-mini")
title_model = ChatOpenAI(model="gpt-4o-mini")


# ─────────────────────────────────────────────
# Tools — added on 10th August 2026
# ─────────────────────────────────────────────
search_tool = TavilySearch(max_results=3)


@tool()
def calculator(num1: float, num2: float, operator: str) -> dict:
    """
    Performs basic arithmetic operations on two numbers.
    Supported Operations are sum, div, mul, sub
    """
    try:
        if operator == "sum":
            result = num1 + num2
        elif operator == "sub":
            result = num1 - num2
        elif operator == "mul":
            result = num1 * num2
        elif operator == "div":
            if num2 == 0:
                return {"error": "Error: Cannot divide by zero!"}
            result = num1 / num2
            return {"result": result}
        else:
            return {"error": "Error: Invalid operator!"}
    except Exception as e:
        return {"error": str(e)}


@tool()
def get_stock_price(symbol: str, date: str) -> dict:
    """
    this is a function which calls yfinance to get stock prices for a given symbol/ticker and on a given date
    """
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={API_KEY}"
    response = requests.get(url)
    return response.json()

@tool()
def rag_tool():

# ─────────────────────────────────────────────
# MCP Client & Tool Loading
# ─────────────────────────────────────────────
client = MultiServerMCPClient(
    {
        "github": {
            "transport": "streamable_http",
            "url": "https://api.githubcopilot.com/mcp/",
            "headers": {
                "Authorization": f"Bearer {GITHUB_PAT}",
                "X-MCP-Toolsets": "repos,issues,pull_requests",
                "X-MCP-Readonly": "true",
            },
        },
        "manim-server": {
            "transport": "stdio",
            "command": "C:\\Users\\amito\\AppData\\Local\\Programs\\Python\\Python313\\python.exe",
            "args": [
                "C:\\Users\\amito\\PycharmProjects\\manim-server\\manim-mcp-server\\src\\manim_server.py"
            ],
            "env": {
                "MANIM_EXECUTABLE": "C:\\Users\\amito\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\manim.exe"
            },
        },
    }
)

def load_mcp_tools() -> list[BaseTool]:
    collected = []
    for server in ("github", "manim-server"):
        try:
            server_tools = run_async(client.get_tools(server_name=server))
            print(f"[MCP] {server}: {len(server_tools)} tools")
            collected.extend(server_tools)
        except Exception as e:
            print(f"[MCP] {server} failed: {e}")
    return collected


mcp_tools = load_mcp_tools()

tools = [search_tool, get_stock_price, *mcp_tools]
chat_model_with_tools = chatmodel.bind_tools(tools)
tool_node = ToolNode(tools, handle_tool_errors=True)


# ─────────────────────────────────────────────
# Graph Node
# ─────────────────────────────────────────────
async def chatbot(state: chatstate):
    """LLM node that may answer or request a tool call."""
    messages = state["messages"]
    response = await chat_model_with_tools.ainvoke(state["messages"])
    return {"messages": [response]}


# ─────────────────────────────────────────────
# Checkpointer Setup
# ─────────────────────────────────────────────
async def _init_checkpointer():
    conn = await aiosqlite.connect(database="chatbot.db")
    return AsyncSqliteSaver(conn)


checkpointer = run_async(_init_checkpointer())


# ─────────────────────────────────────────────
# Graph Construction & Compilation
# ─────────────────────────────────────────────
graph = StateGraph(chatstate)
graph.add_node("chat_node", chatbot)
graph.add_edge(START, "chat_node")

if tool_node:
    graph.add_node("tools", tool_node)
    graph.add_conditional_edges("chat_node", tools_condition)
    graph.add_edge("tools", "chat_node")
else:
    graph.add_edge("chat_node", END)

chatbot = graph.compile(checkpointer=checkpointer)


# ─────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────
async def get_all_created_thread():
    # creates a hashset which only stores unique values and since we need only the unique threads
    # from the list of checkpointer which contains redundant thread_ids recorded at every checkpoint.
    all_threads = set()

    # checkpointer.list() returns a list of the saved checkpoints (AI and human messages at each checkpoint)
    async for checkpoint in checkpointer.alist(None):
        all_threads.add(checkpoint.config["configurable"]["thread_id"])

    return list(all_threads)
