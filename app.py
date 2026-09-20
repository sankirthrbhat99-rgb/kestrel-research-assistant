import os
import streamlit as st
from dotenv import load_dotenv

from kestrel.graph import stream_question, get_graph

st.set_page_config(page_title="Kestrel Research Assistant", page_icon="🦅")

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

st.title("🦅 Kestrel Research Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    import uuid
    st.session_state.conversation_id = str(uuid.uuid4())

# Sidebar
with st.sidebar:
    if st.button("New conversation", use_container_width=True):
        st.session_state.messages = []
        import uuid
        st.session_state.conversation_id = str(uuid.uuid4())
        st.rerun()
    st.markdown("---")
    st.markdown("**Local Assistant Features:**\n- LangGraph orchestration\n- Hybrid chunk retrieval\n- Fact-checking verifier")

# Display chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("citations"):
            with st.expander("Citations & Verification"):
                for c in msg["citations"]:
                    st.markdown(f"- **[{c['chunk_id']}]**: {c['title']}")
                if msg.get("verdict"):
                    color = "green" if msg["verdict"] == "supported" else ("orange" if msg["verdict"] == "partially_supported" else "red")
                    st.markdown(f"**Verdict**: :{color}[{msg['verdict']}]")

if prompt := st.chat_input("Ask a question about Kestrel Labs..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        history = [m for m in st.session_state.messages[:-1] if m["role"] in ("user", "assistant")]
        
        status_container = st.container()
        answer_container = st.empty()
        
        state_update = {}
        error_occurred = False
        
        with status_container:
            try:
                for node_name, status, state in stream_question(prompt, history, conversation_id=st.session_state.conversation_id):
                    state_update.update(state)
                    
                    if node_name == "router":
                        st.info(f"🔄 Router: Re-wrote question to '{state.get('standalone_question', prompt)}' (Route: {state.get('route', '')})")
                    elif node_name == "retriever":
                        ev = state.get('evidence', [])
                        st.info(f"🔍 Retriever: Found {len(ev)} chunks")
                    elif node_name == "synthesiser":
                        st.info(f"✍️ Synthesiser: Drafted response with {len(state.get('claims', []))} claims")
                    elif node_name == "verifier":
                        st.info(f"✅ Verifier: Verdict was '{state.get('verification_verdict', '')}'")
            except Exception as e:
                if "LLMQuotaExhausted" in str(type(e)):
                    st.error("🚨 **Daily LLM Quota Exhausted**: The Groq free-tier limit has been reached. Please try again tomorrow or configure a different provider. The assistant has safely halted.")
                else:
                    st.error(f"⚠️ A rate limit or backend error occurred. Falling back or stopping: {str(e)}")
                error_occurred = True

        if not error_occurred:
            final_answer = state_update.get("final_answer", "")
            citations = state_update.get("citations", [])
            verdict = state_update.get("verification_verdict", "")
            
            answer_container.markdown(final_answer)
            
            if citations:
                with st.expander("Citations & Verification"):
                    for c in citations:
                        st.markdown(f"- **[{c['chunk_id']}]**: {c['title']}")
                    if verdict:
                        color = "green" if verdict == "supported" else ("orange" if verdict == "partially_supported" else "red")
                        st.markdown(f"**Verdict**: :{color}[{verdict}]")
            
            # Save to session history
            st.session_state.messages.append({
                "role": "assistant",
                "content": final_answer,
                "citations": citations,
                "verdict": verdict
            })
