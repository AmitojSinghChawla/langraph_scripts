import streamlit as st
from backend_db import chatbot
from langchain_core.messages import HumanMessage
import uuid
from backend_db import get_all_created_thread

# ************************************* Utility Functions ***************************
def generate_thread_id(): #creates a random uuid based thread_id
    thread_id = uuid.uuid4()
    return thread_id


def new_chat(): # new chat button function, every time one presses it , this generates a new chat environment variables
    st.session_state["thread_id"] = generate_thread_id()
    st.session_state["message_history"] = []
    add_chat_thread(st.session_state["thread_id"])


def add_chat_thread(thread_id):
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(thread_id)


def load_conversation(thread_id): # after adding persistence SQL lite database this function helps retain the chat history in the UI of the app after retrieving it from the workflow state of the chatbot which is then printed by the loop at line 77
    state = chatbot.get_state(config={"configurable": {"thread_id": thread_id}})
    return state.values.get("messages", [])


# ************************************ PAGE CONFIG ***********************************
st.set_page_config(
    page_title="BASIC PERSISTENT CHATBOT",
    layout="wide",
)

# ***************************************** SESSION STAte ****************************
if "message_history" not in st.session_state:
    st.session_state["message_history"] = []  # creates a session variable storing all the message history of that specific session

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
        if st.sidebar.button(str(thread_id)):       # each previous thread is clickable as a button, one can revisit old conversations
            st.session_state["thread_id"] = thread_id   # initialise the workflow with that specific thread_id
            messages = load_conversation(thread_id)     #  loads the chat history from the workflow state stored in sql lite databse using the helper function      #

            temp_messages = []

            for message in messages:
                if isinstance(message, HumanMessage):
                    role = "user"
                else:
                    role = "assistant"

                temp_messages.append({"role": role, "content": message.content})

            st.session_state["message_history"] = temp_messages  # appends all the conversation in that specific chat into it's message history

    st.markdown("---")
    st.markdown("**Developed by Amitoj Singh Chawla**")


# **************************************************************** MAIN UI **********************************************
# this loop prints the message history which is retrieved by the load_conversation utility function. so whenever we open our old thread we can see our previous chats.
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
