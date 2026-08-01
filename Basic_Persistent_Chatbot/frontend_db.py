import streamlit as st
from backend_db import chatbot
from langchain_core.messages import HumanMessage
import uuid
from backend_db import get_all_created_thread

# ************************************* Utility Functions ***************************
def generate_thread_id():
    thread_id = uuid.uuid4()
    return thread_id


def new_chat():
    st.session_state["thread_id"] = generate_thread_id()
    st.session_state["message_history"] = []
    add_chat_thread(st.session_state["thread_id"])


def add_chat_thread(thread_id):
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(thread_id)


def load_conversation(thread_id):
    state = chatbot.get_state(config={"configurable": {"thread_id": thread_id}})
    return state.values.get("messages", [])


# ************************************ PAGE CONFIG ***********************************
st.set_page_config(
    page_title="BASIC PERSISTENT CHATBOT",
    layout="wide",
)

# ***************************************** SESSION STAte ****************************
if "message_history" not in st.session_state:
    st.session_state["message_history"] = []

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = generate_thread_id()

if "chat_threads" not in st.session_state:
    st.session_state["chat_threads"] = get_all_created_thread() # this would return all the unique thread_ids created in database every time a new chat was created in frontend

add_chat_thread(st.session_state["thread_id"])

# **************************************** SIDE BAR **********************************
with st.sidebar:
    st.title("Your Chats ")
    st.markdown("---")
    if st.button("New Chat"):
        new_chat()

    for thread_id in st.session_state["chat_threads"]:
        if st.sidebar.button(str(thread_id)):
            st.session_state["thread_id"] = thread_id
            messages = load_conversation(thread_id)

            temp_messages = []

            for message in messages:
                if isinstance(message, HumanMessage):
                    role = "user"
                else:
                    role = "assistant"

                temp_messages.append({"role": role, "content": message.content})

            st.session_state["message_history"] = temp_messages

    st.markdown("---")
    st.markdown("**Developed by Amitoj Singh Chawla**")


# **************************************************************** MAIN UI **********************************************

for message in st.session_state["message_history"]:
    role = message["role"]
    content = message["content"]

    if role == "user":
        with st.chat_message("user"):
            st.write(content)

    elif role == "assistant":
        with st.chat_message("assistant"):
            st.write(content)

CONFIG = {"configurable": {"thread_id": st.session_state["thread_id"]}}
user_input = st.chat_input("Enter your message")

if user_input:
    if user_input.strip().lower() in ["exit", "quit", "end"]:
        st.session_state["message_history"] = []

    st.session_state["message_history"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    try:

        with st.chat_message("assistant"):
            ai_message = st.write_stream(
                message_chunk.content
                for message_chunk, metadata in chatbot.stream(
                    {"messages": [HumanMessage(content=user_input)]},
                    config=CONFIG,
                    stream_mode="messages",
                )
            )

        st.session_state["message_history"].append(
            {"role": "assistant", "content": ai_message}
        )

    except Exception as e:
        st.session_state["message_history"].append(
            {"role": "assistant", "content": str(e)}
        )

    st.rerun()
