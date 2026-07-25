from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Literal, Annotated
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import add_messages # this import is used for adding a reducer function. Although operator.add also works but this inbuilt function is more optimised to handle state chnages .
load_dotenv()


# ChatModel
chatmodel = ChatOpenAI(model='gpt-4o-mini')


# Definining Workflow state
class chatstate(TypedDict):

    messages: Annotated[list[BaseMessage], add_messages]


# chatbot function

def chatbot(state: chatstate):

    messages = state['messages']

    response = chatmodel.invoke(state['messages'])

    return {'messages': [response]}


# using langgraph to structure the flow of the graph

graph = StateGraph(chatstate)
checkpointer = InMemorySaver()
graph.add_node("chat",chatbot)
graph.add_edge(START, "chat")
graph.add_edge("chat",END)

chatbot = graph.compile(checkpointer=checkpointer)


thread_id = "1"

if __name__ == "__main__":

    while True:
        user_message = input("Type your message: ")

        print('User:', user_message)

        if user_message.strip().lower() in ["exit","quit"]:
            break
        config = {'configurable': {"thread_id": thread_id}}
        response = chatbot.invoke({"messages": [HumanMessage(content=user_message)]}, config=config)

        print('AI:', response['messages'][-1].content)