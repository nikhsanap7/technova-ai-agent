"""TechNova enterprise assistant - Streamlit chat UI.
Run:  streamlit run app.py
"""
import streamlit as st

from agent.gemini_agent import EnterpriseAgent

st.set_page_config(page_title="TechNova Assistant", page_icon="🏢")

EXAMPLES = [
    "Find customer 1025.",
    "Show all pending orders from German customers.",
    "Which products have less than 10 units in stock?",
    "Show all unpaid invoices.",
    "Mark order 5001 as Delivered.",
    "Update the customer.",
    "Mark order 9999 as Delivered.",
]

PURPOSE_LABELS = {
    "agent": "",
    "preview": " - preview before confirmation",
    "confirmed_write": " - WRITE, confirmed by user",
    "verify": " - verification read",
}


# ---------- helpers ----------
# def show_tools(tool_calls):
#     for c in tool_calls:
#         icon = "✅" if c["result"].get("ok") else "⚠️"
#         label = PURPOSE_LABELS.get(c["purpose"], "")
#         with st.expander(f"{icon} Tool: {c['name']}{label} ({c['ms']} ms)"):
#             st.caption("Arguments")
#             st.json(c["args"])
#             st.caption("Result")
#             st.json(c["result"])


def render(msg):
    with st.chat_message(msg["role"]):
        if msg.get("error"):
            st.error(msg["error"])
        if msg.get("text"):
            st.markdown(msg["text"])
        # if msg.get("tools"):
        #     show_tools(msg["tools"])
        if msg.get("seconds") is not None and msg["role"] == "assistant":
            st.caption(f"{msg['seconds']} s")


def store(reply):
    st.session_state.messages.append({
        "role": "assistant", "text": reply.text, "tools": reply.tool_calls,
        "error": reply.error, "seconds": reply.seconds,
    })
    st.session_state.pending = reply.pending


# ---------- sidebar ----------
with st.sidebar:
    st.header("TechNova GmbH")
    mode_label = st.radio(
        "Tools given to Gemini",
        ["All MCP tools", "Top 3 from metadata retrieval"],
    )
    mode = "all" if mode_label.startswith("All") else "retrieval"
    if st.button("Reset conversation"):
        st.session_state.messages = []
        st.session_state.pending = None
        st.session_state.agent = None
        st.rerun()
    st.markdown("**Try these:**")
    for example in EXAMPLES:
        st.markdown(f"- {example}")

# ---------- state ----------
st.session_state.setdefault("messages", [])
st.session_state.setdefault("pending", None)

if st.session_state.get("agent") is None:
    try:
        with st.spinner("Connecting to the MCP server..."):
            st.session_state.agent = EnterpriseAgent(tool_mode=mode)
    except Exception as e:
        st.error(f"Could not start the agent: {type(e).__name__}: {e}")
        st.stop()

agent = st.session_state.agent
agent.tool_mode = mode

# ---------- page ----------
st.title("TechNova Enterprise Assistant")
# st.caption("Streamlit -> Gemini agent -> MCP client -> MCP server -> "
#            "FastAPI -> SQLite (fictional data)")

for m in st.session_state.messages:
    render(m)

# Write operations wait here until the user clicks a button.
pending = st.session_state.pending
if pending:
    with st.chat_message("assistant"):
        st.warning("**Confirmation required.** Nothing has been changed yet.")
        st.markdown(pending.description)
        col1, col2 = st.columns(2)
        if col1.button("✅ Confirm", type="primary"):
            with st.spinner("Executing and verifying..."):
                reply = agent.confirm_pending()
            store(reply)
            st.rerun()
        if col2.button("❌ Cancel"):
            reply = agent.cancel_pending()
            store(reply)
            st.rerun()

prompt = st.chat_input(
    "Ask about customers, orders, products or invoices...",
    disabled=pending is not None,
)
if pending:
    st.caption("Confirm or cancel the change above to continue.")

if prompt:
    st.session_state.messages.append({"role": "user", "text": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = agent.send(prompt)
    store(reply)
    st.rerun()