from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Literal, Annotated
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages
# this import is used for adding a reducer function. Although operator.add also works but this inbuilt function is more optimised to handle state chnages .
import sqlite3

conn = sqlite3.connect("chatbot.db", check_same_thread=False)
load_dotenv()


# ChatModel
chatmodel = ChatOpenAI(model="gpt-4o-mini")

title_model = ChatOpenAI(model="gpt-4o-mini")


# Definining Workflow state
class chatstate(TypedDict):

    messages: Annotated[list[BaseMessage], add_messages]


# chatbot function


def chatbot(state: chatstate):

    messages = state["messages"]

    response = chatmodel.invoke(state["messages"])

    return {"messages": [response]}


# using langgraph to structure the flow of the graph

graph = StateGraph(chatstate)
checkpointer = SqliteSaver(conn=conn)
graph.add_node("chat", chatbot)
graph.add_edge(START, "chat")
graph.add_edge("chat", END)

chatbot = graph.compile(checkpointer=checkpointer)


def get_all_created_thread():
    all_threads = set() # creates a hashset which only stores unique values and since we need only the unique threads from the list of checkpointer which contains redundant thread_ids recorded at every checkpoint.
    for checkpoint in checkpointer.list(None): # checkpointer.list() returns a list of the saved checkpoints( AI and human messages at each checkpoint)
        all_threads.add(checkpoint.config['configurable']['thread_id'])

    return list(all_threads)
