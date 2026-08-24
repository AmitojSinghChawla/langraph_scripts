# ─────────────────────────────────────────────
# Imports
# ─────────────────────────────────────────────
import queue
import uuid

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from backend_db_with_tools_MCP import (
    chatbot,
    submit_async_task,
    run_async,
    get_all_created_thread,
)


# ─────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────
def generate_thread_id():
    # thread ids are kept as strings so that freshly created ids and the ids read
    # back from the sqlite checkpointer compare equal (otherwise the sidebar dupes)
    return str(uuid.uuid4())


def new_chat():  # every press generates a fresh chat environment
    st.session_state["thread_id"] = generate_thread_id()
    st.session_state["message_history"] = []
    add_chat_thread(st.session_state["thread_id"])


def add_chat_thread(thread_id):
    thread_id = str(thread_id)
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(thread_id)


def load_conversation(thread_id):
    # pulls the persisted message list for a thread out of the workflow state
    state = chatbot.get_state(config={"configurable": {"thread_id": str(thread_id)}})
    return state.values.get("messages", [])


def to_display_messages(messages):
    # the graph state now also holds ToolMessages and AIMessages that carry only
    # tool_calls (empty content) — neither should be rendered as a chat bubble
    display = []
    for message in messages:
        if isinstance(message, HumanMessage):
            display.append({"role": "user", "content": message.content})
        elif isinstance(message, AIMessage) and message.content:
            display.append({"role": "assistant", "content": message.content})
    return display


# ─────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="BASIC PERSISTENT CHATBOT",
    layout="wide",
)


# ─────────────────────────────────────────────
# Session State
# ─────────────────────────────────────────────
if "message_history" not in st.session_state:
    st.session_state["message_history"] = []

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = generate_thread_id()

if "chat_threads" not in st.session_state:
    # get_all_created_thread is a coroutine on the new backend, so it has to be
    # driven on the backend's dedicated event loop
    st.session_state["chat_threads"] = [
        str(t) for t in run_async(get_all_created_thread())
    ]

add_chat_thread(st.session_state["thread_id"])


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("Your Chats ")
    st.markdown("---")

    if st.button("New Chat"):
        new_chat()

    for thread_id in st.session_state["chat_threads"][::-1]:  # newest first
        if st.button(str(thread_id), key=f"thread-{thread_id}"):
            st.session_state["thread_id"] = thread_id
            st.session_state["message_history"] = to_display_messages(
                load_conversation(thread_id)
            )

    st.markdown("---")
    st.markdown("**Developed by Amitoj Singh Chawla**")


# ─────────────────────────────────────────────
# Main UI — chat history
# ─────────────────────────────────────────────
for message in st.session_state["message_history"]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

user_input = st.chat_input("Enter your message")


# ─────────────────────────────────────────────
# Main UI — new message handling
# ─────────────────────────────────────────────
if user_input:
    st.session_state["message_history"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    CONFIG = {
        "configurable": {"thread_id": str(st.session_state["thread_id"])},
        "metadata": {"thread_id": str(st.session_state["thread_id"])},
        "run_name": "chat_turn",
    }

    with st.chat_message("assistant"):
        # mutable holder so the generator can create/update the status box
        status_holder = {"box": None}

        def ai_message_stream():
            event_queue: queue.Queue = queue.Queue()

            async def run_stream():
                # runs on the backend's event loop; results are handed back to
                # streamlit's thread through the queue
                try:
                    async for message_chunk, metadata in chatbot.astream(
                        {"messages": [HumanMessage(content=user_input)]},
                        config=CONFIG,
                        stream_mode="messages",
                    ):
                        event_queue.put(("chunk", message_chunk))
                except Exception as exc:
                    event_queue.put(("error", exc))
                finally:
                    event_queue.put(None)

            submit_async_task(run_stream())

            while True:
                item = event_queue.get()
                if item is None:
                    break

                kind, payload = item
                if kind == "error":
                    raise payload

                message_chunk = payload

                # show a single status container whenever a tool runs
                if isinstance(message_chunk, ToolMessage):
                    tool_name = getattr(message_chunk, "name", "tool")
                    if status_holder["box"] is None:
                        status_holder["box"] = st.status(
                            f"🔧 Using `{tool_name}` …", expanded=True
                        )
                    else:
                        status_holder["box"].update(
                            label=f"🔧 Using `{tool_name}` …",
                            state="running",
                            expanded=True,
                        )
                    continue

                # stream assistant tokens only, skipping empty tool-call chunks
                if isinstance(message_chunk, AIMessage) and message_chunk.content:
                    yield message_chunk.content

        try:
            ai_message = st.write_stream(ai_message_stream())
        except Exception as e:
            ai_message = f"⚠️ {e}"
            st.error(ai_message)

        if status_holder["box"] is not None:
            status_holder["box"].update(
                label="✅ Tool finished", state="complete", expanded=False
            )

    st.session_state["message_history"].append(
        {"role": "assistant", "content": ai_message}
    )
