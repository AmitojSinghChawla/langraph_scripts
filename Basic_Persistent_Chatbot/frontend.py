import streamlit as st
from backend import chatbot
from langchain_core.messages import HumanMessage

thread_id = "1"
CONFIG = {"configurable": {'thread_id': thread_id}}

if "messages"  not in st.session_state:
    st.session_state["messages"] = []


for message in st.session_state["messages"]:
    role = message["role"]
    content = message["content"]

    if role == "user":
        with st.chat_message("user"):
            st.write(content)

    elif role == "assistant":
        with st.chat_message("assistant"):
            st.write(content)


user_input = st.chat_input("Enter your message")

if user_input:
    if user_input.strip().lower() in ["exit", "quit","end"]:
        st.session_state["messages"] = []


    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)


    try:

        response = chatbot.invoke({"messages": [HumanMessage(content=user_input)]}, config=CONFIG)
        st.session_state["messages"].append({"role": "assistant", "content": response['messages'][-1].content})
        with st.chat_message("assistant"):
            st.write(response['messages'][-1].content)

    except Exception as e:
        st.session_state["messages"].append({"role": "assistant", "content": str(e)})


    st.rerun()
