import streamlit as st
import json
import re
import requests
import snowflake.connector
import pandas as pd
from snowflake.snowpark import Session
#from snowflake.core import Root
from typing import Any, Dict, List, Optional, Tuple
import plotly.express as px
import time

# Snowflake/Cortex Configuration
HOST = "XYUHKAV-XRB12650.snowflakecomputing.com"
DATABASE = "INVENTORY_DW"
SCHEMA = "GOLD"
API_ENDPOINT = "/api/v2/cortex/agent:run"
API_TIMEOUT = 50000  # in milliseconds

# Updated to use your Inventory Semantic Model path
SEMANTIC_MODEL = '@"INVENTORY_DW"."SEMANTIC"."SEMANTIC_MODELS"/inv_analytics.yaml'

# Model options
MODELS = [
    "mistral-large",
    "snowflake-arctic",
    "llama3-70b",
    "llama3-8b",
]

# Streamlit Page Config
st.set_page_config(
    page_title="Welcome to Cortex AI Assistant",
    layout="wide",
    initial_sidebar_state="auto"
)

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.password = ""
    st.session_state.CONN = None
    st.session_state.snowpark_session = None
    st.session_state.chat_history = []
    st.session_state.messages = []
    st.session_state.welcome_displayed = False
if "debug_mode" not in st.session_state:
    st.session_state.debug_mode = False
if "last_suggestions" not in st.session_state:
    st.session_state.last_suggestions = []
if "chart_x_axis" not in st.session_state:
    st.session_state.chart_x_axis = None
if "chart_y_axis" not in st.session_state:
    st.session_state.chart_y_axis = None
if "chart_type" not in st.session_state:
    st.session_state.chart_type = "Bar Chart"
if "current_query" not in st.session_state:
    st.session_state.current_query = None
if "current_results" not in st.session_state:
    st.session_state.current_results = None
if "current_sql" not in st.session_state:
    st.session_state.current_sql = None
if "current_summary" not in st.session_state:
    st.session_state.current_summary = None
if "service_metadata" not in st.session_state:
    st.session_state.service_metadata = []
if "model_name" not in st.session_state:
    st.session_state.model_name = "mistral-large"
if "num_retrieved_chunks" not in st.session_state:
    st.session_state.num_retrieved_chunks = 100
if "num_chat_messages" not in st.session_state:
    st.session_state.num_chat_messages = 10
if "use_chat_history" not in st.session_state:
    st.session_state.use_chat_history = True
if "clear_conversation" not in st.session_state:
    st.session_state.clear_conversation = False
if "show_suggested_buttons" not in st.session_state:
    st.session_state.show_suggested_buttons = False
if "selected_query" not in st.session_state:
    st.session_state.selected_query = None
if "rerun_trigger" not in st.session_state:
    st.session_state.rerun_trigger = False

# Hide Streamlit branding, prevent chat history shading, ensure text wrapping, and style the logo
st.markdown("""
<style>
#MainMenu, header, footer {visibility: hidden;}
/* Prevent shading of previous chat messages and ensure text wrapping */
[data-testid="stChatMessage"] {
    opacity: 1 !important;
    background-color: transparent !important;
}
[data-testid="stChatMessageContent"] {
    white-space: normal !important; /* Ensure text wraps */
    overflow-wrap: break-word !important; /* Wrap long words */
    word-break: break-word !important; /* Break words if necessary */
    max-width: 100% !important; /* Ensure content doesn't overflow */
}
/* Style for the logo container */
.logo-container {
    position: absolute;
    top: 10px;
    right: 10px;
    z-index: 1000;
}
</style>
""", unsafe_allow_html=True)

# Add DiLytics logo at the top right
logo_url = "https://dilytics.com/wp-content/uploads/2022/11/logo.png" 
st.markdown(f'<div class="logo-container"><img src="{logo_url}" width="150"></div>', unsafe_allow_html=True)

# Function to start a new conversation
def start_new_conversation():
    st.session_state.chat_history = []
    st.session_state.messages = []
    st.session_state.current_query = None
    st.session_state.current_results = None
    st.session_state.current_sql = None
    st.session_state.current_summary = None
    st.session_state.chart_x_axis = None
    st.session_state.chart_y_axis = None
    st.session_state.chart_type = "Bar Chart"
    st.session_state.last_suggestions = []
    st.session_state.clear_conversation = False
    st.session_state.welcome_displayed = False
    st.session_state.rerun_trigger = True

# Initialize config options
def init_config_options():
    st.sidebar.button("Clear conversation", on_click=start_new_conversation)
    st.sidebar.toggle("Debug", key="debug_mode", value=st.session_state.debug_mode)
    st.sidebar.toggle("Use chat history", key="use_chat_history", value=True)
    with st.sidebar.expander("Advanced options"):
        st.selectbox("Select model:", MODELS, key="model_name")
        st.number_input(
            "Select number of context chunks",
            value=100,
            key="num_retrieved_chunks",
            min_value=1,
            max_value=400
        )
        st.number_input(
            "Select number of messages to use in chat history",
            value=10,
            key="num_chat_messages",
            min_value=1,
            max_value=100
        )
    if st.session_state.debug_mode:
        st.sidebar.expander("Session State").write(st.session_state)

# --- CORTEX SEARCH FUNCTION COMMENTED OUT DUE TO INACTIVE SERVICE ---
# def query_cortex_search_service(query):
#     db, schema = session.get_current_database(), session.get_current_schema()
#     root = Root(session)
#     cortex_search_service = (
#         root.databases[db]
#         .schemas[schema]
#         .cortex_search_services[st.session_state.selected_cortex_search_service]
#     )
#     context_documents = cortex_search_service.search(
#         query, columns=[], limit=st.session_state.num_retrieved_chunks
#     )
#     results = context_documents.results
#     service_metadata = st.session_state.service_metadata
#     search_col = [s["search_column"] for s in service_metadata
#                  if s["name"] == st.session_state.selected_cortex_search_service][0]
#     context_str = ""
#     for i, r in enumerate(results):
#         context_str += f"Context document {i+1}: {r[search_col]} \n\n"
#     if st.session_state.debug_mode:
#         st.sidebar.text_area("Context documents", context_str, height=500)
#     return context_str

# Get chat history
def get_chat_history():
    start_index = max(
        0, len(st.session_state.chat_history) - st.session_state.num_chat_messages
    )
    return st.session_state.chat_history[start_index : len(st.session_state.chat_history) - 1]

# Make chat history summary
def make_chat_history_summary(chat_history, question):
    chat_history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
    prompt = f"""
        [INST]
        Based on the chat history below and the question, generate a query that extends the question
        with the chat history provided. The query should be in natural language.
        Answer with only the query. Do not add any explanation.

        <chat_history>
        {chat_history_str}
        </chat_history>
        <question>
        {question}
        </question>
        [/INST]
    """
    summary = complete(st.session_state.model_name, prompt)
    if st.session_state.debug_mode:
        st.sidebar.text_area("Chat history summary", summary.replace("$", "\$"), height=150)
    return summary

# Create prompt handling text responses without cortex search context
def create_prompt(user_question):
    chat_history_str = ""
    if st.session_state.use_chat_history:
        chat_history = get_chat_history()
        if chat_history:
            chat_history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
    
    prompt_instruction = (
        f"Provide a detailed and concise explanation or answer for the query '{user_question}' "
        f"in the context of Inventory Analytics and Stock Management data. "
        f"Ensure the response is clear, specific, and directly addresses the user's request."
    )

    prompt = f"""
        [INST]
        {prompt_instruction}

        <chat_history>
        {chat_history_str}
        </chat_history>
        <question>
        {user_question}
        </question>
        [/INST]
        Answer:
    """
    return complete(st.session_state.model_name, prompt)

# Authentication logic
if not st.session_state.authenticated:
    st.title("Welcome to Snowflake Cortex AI")
    st.markdown("Please login to interact with your data")
    st.session_state.username = st.text_input("Enter Snowflake Username:", value=st.session_state.username)
    st.session_state.password = st.text_input("Enter Password:", type="password")
    if st.button("Login"):
        try:
            conn = snowflake.connector.connect(
                user=st.session_state.username,
                password=st.session_state.password,
                account="XYUHKAV-XRB12650",
                host=HOST,
                port=443,
                warehouse="COMPUTE_WH",
                role="ACCOUNTADMIN",
                database=DATABASE,
                schema=SCHEMA,
            )
            st.session_state.CONN = conn
            snowpark_session = Session.builder.configs({
                "connection": conn
            }).create()
            st.session_state.snowpark_session = snowpark_session
            with conn.cursor() as cur:
                cur.execute(f"USE DATABASE {DATABASE}")
                cur.execute(f"USE SCHEMA {SCHEMA}")
                cur.execute("ALTER SESSION SET TIMEZONE = 'UTC'")
                cur.execute("ALTER SESSION SET QUOTED_IDENTIFIERS_IGNORE_CASE = TRUE")
            st.session_state.authenticated = True
            st.success("Authentication successful! Redirecting...")
            st.rerun()
        except Exception as e:
            st.error(f"Authentication failed: {e}")
else:
    session = st.session_state.snowpark_session
    root = Root(session)

    if st.session_state.rerun_trigger:
        st.session_state.rerun_trigger = False
        st.rerun()

    # Utility Functions
    def run_snowflake_query(query):
        try:
            if not query:
                return None
            df = session.sql(query)
            data = df.collect()
            if not data:
                return None
            columns = df.schema.names
            result_df = pd.DataFrame(data, columns=columns)
            return result_df
        except Exception as e:
            st.error(f"❌ SQL Execution Error: {str(e)}")
            return None

    def is_structured_query(query: str):
        structured_patterns = [
            r'\b(total|show|top|inventory value|quantity|on hand|available qty|stockout|warehouse|product|category|brand|excess stock|reorder|safety stock|sum|count|avg|max|min)\b'
        ]
        return any(re.search(pattern, query.lower()) for pattern in structured_patterns)

    def is_unstructured_query(query: str):
        unstructured_keywords = [
            "metric", "describe", "reports", "facts", "join", "filter", "explain", "summary",
            "policy", "document", "description", "highlight", "guidelines", "procedure",
            "how to", "define", "definition", "rules", "steps", "overview", "objective",
            "purpose", "benefits", "importance", "impact", "details", "regulation",
            "requirement", "compliance", "when to", "where to", "meaning", "interpretation",
            "clarify", "note", "explanation", "instructions"
        ]
        return any(keyword in query.lower() for keyword in unstructured_keywords)

    def is_complete_query(query: str):
        complete_patterns = [r'\b(generate|write|create|describe|explain)\b']
        return any(re.search(pattern, query.lower()) for pattern in complete_patterns)

    def is_summarize_query(query: str):
        summarize_patterns = [r'\b(summarize|summary|condense)\b']
        return any(re.search(pattern, query.lower()) for pattern in summarize_patterns)

    def is_question_suggestion_query(query: str):
        suggestion_patterns = [
            r'\b(what|which|how)\b.*\b(questions|type of questions|queries)\b.*\b(ask|can i ask|pose)\b',
            r'\b(give me|show me|list)\b.*\b(questions|examples|sample questions)\b'
        ]
        return any(re.search(pattern, query.lower()) for pattern in suggestion_patterns)

    def is_greeting_query(query: str):
        greeting_keywords = ["hi", "hello", "hey", "greetings"]
        return any(keyword == query.strip().lower() for keyword in greeting_keywords)

    def is_invalid_query(query: str) -> bool:
        query_clean = query.strip().lower()
        if not query_clean or len(query_clean) < 3:
            return True
        alphabetic_count = sum(c.isalpha() for c in query_clean)
        if len(query_clean) > 0 and alphabetic_count / len(query_clean) < 0.5:
            return True
        words = query_clean.split()
        if not words or all(len(word) < 3 for word in words):
            return True
        return False

    def complete(model, prompt):
        try:
            prompt = prompt.replace("'", "\\'")
            query = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', '{prompt}') AS response"
            result = session.sql(query).collect()
            return result[0]["RESPONSE"]
        except Exception as e:
            st.error(f"❌ COMPLETE Function Error: {str(e)}")
            return None

    def summarize(text):
        try:
            text = text.replace("'", "\\'")
            query = f"SELECT SNOWFLAKE.CORTEX.SUMMARIZE('{text}') AS summary"
            result = session.sql(query).collect()
            return result[0]["SUMMARY"]
        except Exception as e:
            st.error(f"❌ SUMMARIZE Function Error: {str(e)}")
            return None

    def parse_sse_response(response_text: str) -> List[Dict]:
        events = []
        lines = response_text.strip().split("\n")
        current_event = {}
        for line in lines:
            if line.startswith("event:"):
                current_event["event"] = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_str = line.split(":", 1)[1].strip()
                if data_str != "[DONE]":
                    try:
                        data_json = json.loads(data_str)
                        current_event["data"] = data_json
                        events.append(current_event)
                        current_event = {}
                    except json.JSONDecodeError as e:
                        st.error(f"❌ Failed to parse SSE data: {str(e)} - Data: {data_str}")
        return events

    def snowflake_api_call(query: str, is_structured: bool = False):
        payload = {
            "model": st.session_state.model_name,
            "messages": [{"role": "user", "content": [{"type": "text", "text": query}]}],
            "tools": []
        }
        if is_structured:
            payload["tools"].append({"tool_spec": {"type": "cortex_analyst_text_to_sql", "name": "analyst1"}})
            payload["tool_resources"] = {"analyst1": {"semantic_model_file": SEMANTIC_MODEL}}
        # --- CORTEX SEARCH TOOL CALL COMMENTED OUT ---
        # else:
        #     payload["tools"].append({"tool_spec": {"type": "cortex_search", "name": "search1"}})
        #     payload["tool_resources"] = {"search1": {"name": st.session_state.selected_cortex_search_service, "max_results": st.session_state.num_retrieved_chunks}}
        
        try:
            resp = requests.post(
                url=f"https://{HOST}{API_ENDPOINT}",
                json=payload,
                headers={
                    "Authorization": f'Snowflake Token="{st.session_state.CONN.rest.token}"',
                    "Content-Type": "application/json",
                },
                timeout=API_TIMEOUT // 1000
            )
            if st.session_state.debug_mode:
                st.write(f"API Response Status: {resp.status_code}")
                st.write(f"API Raw Response: {resp.text}")
            if resp.status_code < 400:
                if not resp.text.strip():
                    st.error("❌ API returned an empty response.")
                    return None
                return parse_sse_response(resp.text)
            else:
                raise Exception(f"Failed request with status {resp.status_code}: {resp.text}")
        except Exception:
            return None

    def suggest_sample_questions(query: str) -> List[str]:
        return sample_questions[:5]

    def process_sse_response(response, is_structured):
        sql = ""
        search_results = []
        if not response:
            return sql, search_results
        try:
            for event in response:
                if event.get("event") == "message.delta" and "data" in event:
                    delta = event["data"].get("delta", {})
                    content = delta.get("content", [])
                    for item in content:
                        if item.get("type") == "tool_results":
                            tool_results = item.get("tool_results", {})
                            if "content" in tool_results:
                                for result in tool_results["content"]:
                                    if result.get("type") == "json":
                                        result_data = result.get("json", {})
                                        if is_structured and "sql" in result_data:
                                            sql = result_data.get("sql", "")
                                        # elif not is_structured and "searchResults" in result_data:
                                        #     search_results = [sr["text"] for sr in result_data["searchResults"]]
        except Exception as e:
            st.error(f"❌ Error Processing Response: {str(e)}")
            return sql, search_results
        return sql.strip(), search_results

    def display_chart_tab(df: pd.DataFrame, prefix: str = "chart", query: str = ""):
        if df.empty or len(df.columns) < 2:
            return
        query_lower = query.lower()
        if re.search(r'\b(warehouse|region)\b', query_lower):
            default_chart = "Bar Chart"
        elif re.search(r'\b(month|year|date)\b', query_lower):
            default_chart = "Line Chart"
        else:
            default_chart = "Bar Chart"
        all_cols = list(df.columns)
        col1, col2, col3 = st.columns(3)
        default_x = st.session_state.get(f"{prefix}_x", all_cols[0])
        try:
            x_index = all_cols.index(default_x)
        except ValueError:
            x_index = 0
        x_col = col1.selectbox("X axis", all_cols, index=x_index, key=f"{prefix}_x")
        remaining_cols = [c for c in all_cols if c != x_col]
        default_y = st.session_state.get(f"{prefix}_y", remaining_cols[0] if remaining_cols else all_cols[0])
        try:
            y_index = remaining_cols.index(default_y)
        except ValueError:
            y_index = 0
        y_col = col2.selectbox("Y axis", remaining_cols, index=y_index, key=f"{prefix}_y")
        chart_options = ["Line Chart", "Bar Chart", "Pie Chart", "Scatter Chart", "Histogram Chart"]
        default_type = st.session_state.get(f"{prefix}_type", default_chart)
        try:
            type_index = chart_options.index(default_type)
        except ValueError:
            type_index = chart_options.index(default_chart)
        chart_type = col3.selectbox("Chart Type", chart_options, index=type_index, key=f"{prefix}_type")
        if chart_type == "Line Chart":
            fig = px.line(df, x=x_col, y=y_col, title=chart_type)
            st.plotly_chart(fig, key=f"{prefix}_line")
        elif chart_type == "Bar Chart":
            fig = px.bar(df, x=x_col, y=y_col, title=chart_type)
            st.plotly_chart(fig, key=f"{prefix}_bar")
        elif chart_type == "Pie Chart":
            fig = px.pie(df, names=x_col, values=y_col, title=chart_type)
            st.plotly_chart(fig, key=f"{prefix}_pie")
        elif chart_type == "Scatter Chart":
            fig = px.scatter(df, x=x_col, y=y_col, title=chart_type)
            st.plotly_chart(fig, key=f"{prefix}_scatter")
        elif chart_type == "Histogram Chart":
            fig = px.histogram(df, x=x_col, title=chart_type)
            st.plotly_chart(fig, key=f"{prefix}_hist")

    # UI Logic
    with st.sidebar:
        st.markdown("""
        <style>
        [data-testid="stSidebar"] [data-testid="stButton"] > button,
        [data-testid="stButton"] > button {
            background-color: #29B5E8 !important;
            color: white !important;
            font-weight: bold !important;
            width: 100% !important;
            height: 60px !important;
            border-radius: 0px !important;
            margin: 5px 0 !important;
            border: none !important;
            padding: 0.5rem 1rem !important;
            white-space: normal !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            display: -webkit-box !important;
            -webkit-line-clamp: 2 !important;
            -webkit-box-orient: vertical !important;
            box-sizing: border-box !important;
        }
        </style>
        """, unsafe_allow_html=True)
        logo_container = st.container()
        button_container = st.container()
        about_container = st.container()
        help_container = st.container()
        with logo_container:
            logo_url = "https://www.snowflake.com/wp-content/themes/snowflake/assets/img/logo-blue.svg"
            st.image(logo_url, width=250)
        with button_container:
            init_config_options()
        with about_container:
            st.markdown("### About")
            st.write(
                "This application uses **Snowflake Cortex Analyst** with your Inventory Semantic Model "
                "to interpret your natural language questions and generate data insights. "
                "Simply ask a question below to see relevant answers and visualizations."
            )
        with help_container:
            st.markdown("### Help & Documentation")
            st.markdown(
                "- [User Guide](https://docs.snowflake.com/en/guides-overview-ai-features)  \n"
                "- [Snowflake Cortex Analyst Docs](https://docs.snowflake.com/en/user-guide/snowflake-cortex)  \n"
                "- [Contact Support](https://support.snowflake.com/s/)"
            )

    st.title("Cortex AI-Inventory Assistant by DiLytics")
    semantic_model_filename = SEMANTIC_MODEL.split("/")[-1]
    st.markdown(f"Semantic Model: `{semantic_model_filename}`")

    # Display welcome message only once, outside of chat history loop
    if not st.session_state.welcome_displayed:
        welcome_message = "Hi, I am your Inventory Assistant. I can help you explore inventory stock positions, valuations, stockouts, and analytics."
        with st.chat_message("assistant"):
            st.markdown(welcome_message, unsafe_allow_html=True)
        if not any(msg["content"] == welcome_message for msg in st.session_state.chat_history):
            st.session_state.chat_history.append({"role": "assistant", "content": welcome_message})
        st.session_state.welcome_displayed = True

    st.sidebar.subheader("Sample Questions")
    sample_questions = [
        "What is the total inventory value as of the latest snapshot date?",
        "What is the total quantity of inventory currently on hand?",
        "What is the inventory value by warehouse as of the latest snapshot?",
        "What is the total inventory value by product category as of the latest snapshot?",
        "How many products are out of stock as of the latest snapshot?",
        "How many products need to be reordered as of the latest snapshot?",
        "What is the total excess inventory value by warehouse?",
        "What is the inventory value by ABC classification?"
    ]

    # Display chat history without chat bubbles for assistant, skipping the welcome message
    for idx, message in enumerate(st.session_state.chat_history):
        if idx == 0 and "Hi, I am your Inventory Assistant" in message["content"]:
            continue
        if message["role"] == "user":
            with st.chat_message("user"):
                st.markdown(f"**You:** {message['content']}", unsafe_allow_html=True)
        else:
            with st.chat_message("assistant"):
                st.markdown(message["content"], unsafe_allow_html=True)
            if "results" in message and message["results"] is not None:
                with st.expander("View SQL Query", expanded=False):
                    st.code(message["sql"], language="sql")
                st.markdown(f"**Query Results ({len(message['results'])} rows):**")
                st.dataframe(message["results"])
                if not message["results"].empty and len(message["results"].columns) >= 2:
                    st.markdown("**📈 Visualization:**")
                    unique_prefix = f"chart_{idx}_{hash(message['content'])}"
                    display_chart_tab(message["results"], prefix=unique_prefix, query=message.get("query", ""))

    query = st.chat_input("Ask your question...")
    if not query and st.session_state.selected_query:
        query = st.session_state.selected_query
        st.session_state.chat_history.append({"role": "user", "content": query})
        st.session_state.messages.append({"role": "user", "content": query})
        st.session_state.selected_query = None

    for sample in sample_questions:
        if st.sidebar.button(sample, key=sample):
            query = sample

    if query:
        st.session_state.chart_x_axis = None
        st.session_state.chart_y_axis = None
        st.session_state.chart_type = "Bar Chart"
        original_query = query
        if query.strip().isdigit() and st.session_state.last_suggestions:
            try:
                index = int(query.strip()) - 1
                if 0 <= index < len(st.session_state.last_suggestions):
                    query = st.session_state.last_suggestions[index]
                else:
                    query = original_query
            except ValueError:
                query = original_query
        st.session_state.chat_history.append({"role": "user", "content": original_query})
        st.session_state.messages.append({"role": "user", "content": original_query})
        with st.chat_message("user"):
            st.markdown(f"**You:** {original_query}", unsafe_allow_html=True)
        with st.spinner("Generating Response..."):
            response_placeholder = st.empty()
            is_structured = is_structured_query(query)
            is_unstructured = is_unstructured_query(query)
            is_complete = is_complete_query(query)
            is_summarize = is_summarize_query(query)
            is_suggestion = is_question_suggestion_query(query)
            is_greeting = is_greeting_query(query)
            is_invalid = is_invalid_query(query)
            assistant_response = {"role": "assistant", "content": "", "query": query}
            response_content = ""
            failed_response = False

            if is_greeting:
                response_content = "Hello! Here are some inventory questions you can ask me:\n\n"
                for i, q in enumerate(sample_questions[:5], 1):
                    response_content += f"{i}. {q}\n"
                response_content += "\nFeel free to ask any of these or come up with your own related to Inventory Analytics!"
                with response_placeholder:
                    with st.chat_message("assistant"):
                        st.markdown(response_content, unsafe_allow_html=True)
                assistant_response["content"] = response_content
                st.session_state.last_suggestions = sample_questions[:5]
                st.session_state.messages.append({"role": "assistant", "content": response_content})
                st.session_state.show_suggested_buttons = True

            elif is_suggestion:
                response_content = "Here are some inventory questions you can ask me:\n\n"
                for i, q in enumerate(sample_questions[:5], 1):
                    response_content += f"{i}. {q}\n"
                response_content += "\nFeel free to ask any of these or come up with your own related to Inventory Analytics!"
                with response_placeholder:
                    with st.chat_message("assistant"):
                        st.markdown(response_content, unsafe_allow_html=True)
                assistant_response["content"] = response_content
                st.session_state.last_suggestions = sample_questions[:5]
                st.session_state.messages.append({"role": "assistant", "content": response_content})
                st.session_state.show_suggested_buttons = True

            elif is_invalid:
                suggestions = suggest_sample_questions(query)
                st.session_state.last_suggestions = suggestions
                response_content = "I'm sorry, I didn't understand your question. Could you please rephrase it? Here are some suggested inventory questions:\n\n"
                for i, suggestion in enumerate(suggestions, 1):
                    response_content += f"{i}. {suggestion}\n"
                response_content += "\nFeel free to ask any of these or rephrase your question!"
                with response_placeholder:
                    with st.chat_message("assistant"):
                        st.markdown(response_content, unsafe_allow_html=True)
                assistant_response["content"] = response_content
                st.session_state.messages.append({"role": "assistant", "content": response_content})
                st.session_state.chat_history.append(assistant_response)
                st.session_state.current_query = query
                st.session_state.current_results = assistant_response.get("results")
                st.session_state.current_sql = assistant_response.get("sql")
                st.session_state.current_summary = assistant_response.get("summary")
                st.stop()

            elif is_complete or is_unstructured:
                response = create_prompt(query)
                if response:
                    response_content = response
                    with response_placeholder:
                        with st.chat_message("assistant"):
                            st.markdown(response_content, unsafe_allow_html=True)
                    assistant_response["content"] = response_content
                    st.session_state.messages.append({"role": "assistant", "content": response_content})
                else:
                    failed_response = True
                    assistant_response["content"] = response_content

            elif is_summarize:
                summary = summarize(query)
                if summary:
                    response_content = summary
                    with response_placeholder:
                        with st.chat_message("assistant"):
                            st.markdown(response_content, unsafe_allow_html=True)
                    assistant_response["content"] = response_content
                    st.session_state.messages.append({"role": "assistant", "content": response_content})
                else:
                    failed_response = True
                    assistant_response["content"] = response_content

            elif is_structured:
                response = snowflake_api_call(query, is_structured=True)
                sql, _ = process_sse_response(response, is_structured=True)
                if sql:
                    results = run_snowflake_query(sql)
                    if results is not None and not results.empty:
                        results_text = results.to_string(index=False)
                        prompt = f"Provide a concise natural language answer to the query '{query}' using the following data, avoiding phrases like 'Based on the query results':\n\n{results_text}"
                        summary = complete(st.session_state.model_name, prompt)
                        if not summary:
                            summary = "⚠️ Unable to generate a natural language summary."
                        response_content = summary
                        with response_placeholder:
                            with st.chat_message("assistant"):
                                st.markdown(response_content, unsafe_allow_html=True)
                        with st.expander("View SQL Query", expanded=False):
                            st.code(sql, language="sql")
                        st.markdown(f"**Query Results ({len(results)} rows):**")
                        st.dataframe(results)
                        if len(results.columns) >= 2:
                            st.markdown("**📈 Visualization:**")
                            display_chart_tab(results, prefix=f"chart_{hash(query)}", query=query)
                        assistant_response.update({
                            "content": response_content,
                            "sql": sql,
                            "results": results,
                            "summary": summary
                        })
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": response_content,
                            "sql": sql,
                            "results": results,
                            "summary": summary
                        })
                    else:
                        failed_response = True
                        assistant_response["content"] = response_content
                else:
                    failed_response = True
                    assistant_response["content"] = response_content

            else:
                # Fallback to general LLM response since Cortex Search is bypassed
                response = create_prompt(query)
                if response:
                    response_content = response
                    with response_placeholder:
                        with st.chat_message("assistant"):
                            st.markdown(response_content, unsafe_allow_html=True)
                    assistant_response["content"] = response_content
                    st.session_state.messages.append({"role": "assistant", "content": response_content})
                else:
                    failed_response = True
                    assistant_response["content"] = response_content

            if failed_response:
                suggestions = suggest_sample_questions(query)
                st.session_state.last_suggestions = suggestions
                response_content = "I'm sorry, I didn't understand your question. Could you please rephrase it? Here are some suggested inventory questions:\n\n"
                for i, suggestion in enumerate(suggestions, 1):
                    response_content += f"{i}. {suggestion}\n"
                response_content += "\nFeel free to ask any of these or rephrase your question!"
                with response_placeholder:
                    with st.chat_message("assistant"):
                        st.markdown(response_content, unsafe_allow_html=True)
                assistant_response["content"] = response_content
                st.session_state.messages.append({"role": "assistant", "content": response_content})
                st.session_state.chat_history.append(assistant_response)
                st.session_state.current_query = query
                st.session_state.current_results = assistant_response.get("results")
                st.session_state.current_sql = assistant_response.get("sql")
                st.session_state.current_summary = assistant_response.get("summary")
                st.stop()

            st.session_state.chat_history.append(assistant_response)
            st.session_state.current_query = query
            st.session_state.current_results = assistant_response.get("results")
            st.session_state.current_sql = assistant_response.get("sql")
            st.session_state.current_summary = assistant_response.get("summary")
