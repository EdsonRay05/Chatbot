import os
import streamlit as st
from perplexity import Perplexity
from dotenv import load_dotenv

# Load environment variables (optional, for local dev)
load_dotenv()

# Page config
st.set_page_config(
    page_title="Perplexity Chatbot",
    page_icon="🤖",
    layout="wide"
)

# Custom CSS for better chat UI
st.markdown("""
    <style>
    .chat-message {padding: 1rem; border-radius: 1rem; margin-bottom: 1rem;}
    .user {background: #007bff; color: white; text-align: right;}
    .bot {background: #f0f2f6; color: black;}
    .chat-container {max-height: 600px; overflow-y: auto;}
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "client" not in st.session_state:
    st.session_state.client = None

# Resolve API key: Streamlit secrets (cloud) → env (local)
def get_api_key():
    try:
        return st.secrets["PERPLEXITY_API_KEY"]
    except Exception:
        return os.getenv("PERPLEXITY_API_KEY", "")

# API Key input (sidebar)
with st.sidebar:
    st.title("🔑 API Settings")

    # Pre-fill from secrets/env but still editable for debugging
    api_key = st.text_input(
        "Perplexity API Key",
        type="password",
        value=get_api_key()
    )

    model = st.selectbox(
        "Model",
        ["sonar-pro", "sonar-small", "llama-3.1-sonar-large-128k-online"]
    )

    if st.button("Connect", type="primary"):
        if api_key:
            try:
                st.session_state.client = Perplexity(api_key=api_key)
                st.success("✅ Connected!")
            except Exception as e:
                st.error(f"❌ Connection failed: {e}")
        else:
            st.warning("⚠️ Enter API key first")

# Main chat interface
st.title("🤖 Perplexity AI Chatbot")
st.markdown("Ask anything! Powered by Perplexity Sonar models.")

# Display chat history
chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"], unsafe_allow_html=True)

# Chat input
if prompt := st.chat_input("Type your message..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with chat_container:
        with st.chat_message("user"):
            st.markdown(prompt)

    # Generate response (with streaming + citations)
    with chat_container:
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            sources_placeholder = st.empty()  # for sources under the answer
            full_response = ""
            collected_sources = []  # will hold search_results from stream

            if st.session_state.client:
                try:
                    # Stream the response so text appears token by token
                    stream = st.session_state.client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": m["role"], "content": m["content"]}
                            for m in st.session_state.messages
                        ],
                        stream=True
                    )

                    for chunk in stream:
                        delta = chunk.choices[0].delta

                        # Append streamed text
                        if delta.content:
                            full_response += delta.content
                            message_placeholder.markdown(full_response + "▌")

                        # Grab search_results once they arrive in the stream
                        if hasattr(chunk, "search_results") and chunk.search_results:
                            collected_sources = chunk.search_results

                    # Final answer without cursor
                    message_placeholder.markdown(full_response)

                    # Render clickable sources under the answer
                    if collected_sources:
                        md_lines = ["**Sources:**"]
                        for i, src in enumerate(collected_sources, start=1):
                            title = getattr(src, "title", f"Source {i}")
                            url = getattr(src, "url", "")
                            date = getattr(src, "date", "")
                            if url:
                                line = f"[{i}] [{title}]({url})"
                                if date:
                                    line += f" — {date}"
                                md_lines.append(line)
                        sources_placeholder.markdown("\n\n".join(md_lines))

                except Exception as e:
                    message_placeholder.error(f"Error: {e}")
            else:
                message_placeholder.warning("⚠️ Connect API first in sidebar")

    # Add bot response to history
    if st.session_state.client and full_response:
        st.session_state.messages.append(
            {"role": "assistant", "content": full_response}
        )

# Sidebar controls
with st.sidebar:
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()
    with col2:
        if st.button("💾 Save Chat"):
            st.download_button(
                label="Download Chat",
                data="\n".join(
                    [f"{m['role']}: {m['content']}" for m in st.session_state.messages]
                ),
                file_name="chat_history.txt",
                mime="text/plain"
            )

    st.caption("**Setup:** `pip install streamlit perplexityai python-dotenv`")
