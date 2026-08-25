# ─────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────
import os
import sqlite3
import requests
from typing import TypedDict, Annotated
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages  # optimised reducer for message state
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import ToolNode, tools_condition

# ─────────────────────────────────────────────
# Environment & Config
# ─────────────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
conn = sqlite3.connect("chatbot.db", check_same_thread=False)


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


tools = get_stock_price, calculator, search_tool
chat_model_with_tools = chatmodel.bind_tools(tools)
tool_node = ToolNode(tools, handle_tool_errors=True)


# ─────────────────────────────────────────────
# Graph Node
# ─────────────────────────────────────────────
def chatbot(state: chatstate):
    messages = state["messages"]
    response = chat_model_with_tools.invoke(state["messages"])
    return {"messages": [response]}


# ─────────────────────────────────────────────
# Graph Construction & Compilation
# ─────────────────────────────────────────────
graph = StateGraph(chatstate)
checkpointer = SqliteSaver(
    conn=conn
)  # now the checkpointer stores the workflow state in a sql lite database which is persistant

graph.add_node("chat", chatbot)
graph.add_node("tools", tool_node)

graph.add_edge(START, "chat")
graph.add_conditional_edges("chat", tools_condition)
graph.add_edge("tools", "chat")

chatbot = graph.compile(checkpointer=checkpointer)


# ─────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────
def get_all_created_thread():
    all_threads = (
        set()
    )  # creates a hashset which only stores unique values and since we need only the unique threads from the list of checkpointer which contains redundant thread_ids recorded at every checkpoint.
    for checkpoint in checkpointer.list(
        None
    ):  # checkpointer.list() returns a list of the saved checkpoints( AI and human messages at each checkpoint)
        all_threads.add(checkpoint.config["configurable"]["thread_id"])

    return list(all_threads)
