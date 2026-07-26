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

        with st.chat_message("assistant"):
            ai_message = st.write_stream(message_chunk.content for message_chunk, metadata in chatbot.stream({"messages": [HumanMessage(content=user_input)]}, config=CONFIG, stream_mode="messages"))


        st.session_state["messages"].append({"role": "assistant", "content": ai_message})

    except Exception as e:
        st.session_state["messages"].append({"role": "assistant", "content": str(e)})


    st.rerun()
