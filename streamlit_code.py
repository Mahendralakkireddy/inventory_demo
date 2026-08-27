
import streamlit as st
import json
import re
import snowflake.connector
import pandas as pd
from snowflake.snowpark import Session
from typing import Any, Dict, List, Optional
import plotly.express as px

# Snowflake/Cortex Configuration
HOST = "xyuhkav-xrb12650.snowflakecomputing.com" 
DATABASE = "INVENTORY_DW"
SCHEMA = "GOLD" # Ensure your tables are actually in this schema

# Model options
MODELS = ["mistral-large", "snowflake-arctic", "llama3-70b", "llama3-8b"]

st.set_page_config(page_title="Welcome to Cortex AI Assistant", layout="wide", initial_sidebar_state="auto")

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
if "model_name" not in st.session_state:
    st.session_state.model_name = "mistral-large"
if "num_chat_messages" not in st.session_state:
    st.session_state.num_chat_messages = 10
if "use_chat_history" not in st.session_state:
    st.session_state.use_chat_history = True
if "selected_query" not in st.session_state:
    st.session_state.selected_query = None
if "rerun_trigger" not in st.session_state:
    st.session_state.rerun_trigger = False

st.markdown("""
<style>
#MainMenu, header, footer {visibility: hidden;}
[data-testid="stChatMessage"] {opacity: 1 !important; background-color: transparent !important;}
[data-testid="stChatMessageContent"] {white-space: normal !important; overflow-wrap: break-word !important; word-break: break-word !important; max-width: 100% !important; }
.logo-container {position: absolute; top: 10px; right: 10px; z-index: 1000;}
</style>
""", unsafe_allow_html=True)

logo_url = "https://dilytics.com/wp-content/uploads/2022/11/logo.png" 
st.markdown(f'<div class="logo-container"><img src="{logo_url}" width="150"></div>', unsafe_allow_html=True)

def start_new_conversation():
    st.session_state.chat_history = []
    st.session_state.messages = []
    st.session_state.last_suggestions = []
    st.session_state.welcome_displayed = False
    st.session_state.rerun_trigger = True

def init_config_options():
    st.sidebar.button("Clear conversation", on_click=start_new_conversation)
    st.sidebar.toggle("Debug", key="debug_mode", value=st.session_state.debug_mode)
    st.sidebar.toggle("Use chat history", key="use_chat_history", value=True)
    with st.sidebar.expander("Advanced options"):
        st.selectbox("Select model:", MODELS, key="model_name")
        st.number_input("Select number of messages to use in chat history", value=10, key="num_chat_messages", min_value=1, max_value=100)
    if st.session_state.debug_mode:
        st.sidebar.expander("Session State").write(st.session_state)

def get_chat_history():
    start_index = max(0, len(st.session_state.chat_history) - st.session_state.num_chat_messages)
    return st.session_state.chat_history[start_index : len(st.session_state.chat_history) - 1]

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
            st.session_state.snowpark_session = Session.builder.configs({"connection": conn}).create()
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
    if st.session_state.rerun_trigger:
        st.session_state.rerun_trigger = False
        st.rerun()

    def run_snowflake_query(query):
        try:
            if not query: return None
            df = session.sql(query)
            data = df.collect()
            if not data: return None
            return pd.DataFrame(data, columns=df.schema.names)
        except Exception as e:
            if st.session_state.debug_mode: st.error(f"❌ SQL Execution Error: {str(e)}")
            return None

    def is_structured_query(query: str):
        structured_patterns = [r'\b(total|show|top|group by|order by|how much|give|count|average|avg|max|min|least|highest|lowest|by year|how many|amount|units|quantity|inventory|stock|movement|warehouse|product|sku|category|brand|region|status|receipt|issue|transfer|return|adjustment|scrap|value|cost|date|month|year|variance|breakdown|comparison|change)\b']
        return any(re.search(pattern, query.lower()) for pattern in structured_patterns)

    def is_summarize_query(query: str):
        return bool(re.search(r'\b(summarize|summary|condense)\b', query.lower()))

    def is_question_suggestion_query(query: str):
        suggestion_patterns = [r'\b(what|which|how)\b.*\b(questions|type of questions|queries)\b.*\b(ask|can i ask|pose)\b', r'\b(give me|show me|list)\b.*\b(questions|examples|sample questions)\b']
        return any(re.search(pattern, query.lower()) for pattern in suggestion_patterns)

    def is_greeting_query(query: str):
        return any(keyword == query.strip().lower() for keyword in ["hi", "hello", "hey", "greetings"])

    def is_invalid_query(query: str) -> bool:
        query_clean = query.strip().lower()
        if not query_clean or len(query_clean) < 3: return True
        alphabetic_count = sum(c.isalpha() for c in query_clean)
        if len(query_clean) > 0 and alphabetic_count / len(query_clean) < 0.5: return True
        return False

    def complete(model, prompt):
        try:
            prompt = prompt.replace("'", "\\'")
            result = session.sql(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', '{prompt}') AS response").collect()
            return result[0]["RESPONSE"]
        except Exception as e:
            st.error(f"❌ COMPLETE Function Error: {str(e)}")
            return None

    def summarize(text):
        try:
            text = text.replace("'", "\\'")
            result = session.sql(f"SELECT SNOWFLAKE.CORTEX.SUMMARIZE('{text}') AS summary").collect()
            return result[0]["SUMMARY"]
        except Exception as e:
            st.error(f"❌ SUMMARIZE Function Error: {str(e)}")
            return None

    # --- NEW CUSTOM TEXT-TO-SQL ENGINE ---
    def generate_sql_from_cortex(query: str):
        # NOTE: EDIT THIS SCHEMA CONTEXT TO MATCH YOUR EXACT TABLES AND COLUMNS
        schema_context = f"""
        You are an expert Snowflake SQL Developer.
        Write a valid Snowflake SQL query to answer the user's question based on the following schema:
        
        Database: {DATABASE}
        Schema: {SCHEMA}
        
        Tables:
        1. FACT_INVENTORY_SNAPSHOT (Contains daily inventory balances)
           - DW_DATE_KEY (integer)
           - DW_PRODUCT_KEY (integer)
           - DW_WAREHOUSE_KEY (integer)
           - QUANTITY_ON_HAND (number)
           - QUANTITY_ON_ORDER (number)
           - STOCKOUT_IND (varchar, 'Y' or 'N')
           
        2. DIM_PRODUCT
           - DW_PRODUCT_KEY (integer)
           - PRODUCT_NAME (varchar)
           - CATEGORY (varchar)
           
        3. DIM_WAREHOUSE
           - DW_WAREHOUSE_KEY (integer)
           - WAREHOUSE_NAME (varchar)
           - REGION (varchar)
           
        Always join FACT_INVENTORY_SNAPSHOT to dimension tables using the DW_*_KEY columns.
        Return ONLY the raw SQL query. Do not include markdown formatting like ```sql, explanations, or a trailing semicolon.
        """
        
        prompt = f"{schema_context}\n\nUser Question: {query}\nSQL Query:"
        
        sql = complete(st.session_state.model_name, prompt)
        if sql:
            # Clean up formatting if the LLM adds markdown by mistake
            sql = sql.replace("```sql", "").replace("```", "").strip()
            if sql.endswith(";"):
                sql = sql[:-1]
            return sql
        return None

    def create_prompt(user_question):
        chat_history_str = ""
        if st.session_state.use_chat_history:
            chat_history = get_chat_history()
            if chat_history:
                chat_history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
        prompt = f"""
            You are a helpful AI assistant for inventory analytics.
            Answer the user's question directly and concisely based on your general knowledge. 
            Do not write SQL queries.

            <chat_history>
            {chat_history_str}
            </chat_history>

            <question>
            {user_question}
            </question>
        """
        return complete(st.session_state.model_name, prompt)

    def display_chart_tab(df: pd.DataFrame, prefix: str = "chart", query: str = ""):
        if df.empty or len(df.columns) < 2: return
        query_lower = query.lower()
        default_chart = "Pie Chart" if re.search(r'\b(county|jurisdiction)\b', query_lower) else ("Line Chart" if re.search(r'\b(month|year|date)\b', query_lower) else "Bar Chart")
        all_cols = list(df.columns)
        col1, col2, col3 = st.columns(3)
        x_col = col1.selectbox("X axis", all_cols, index=all_cols.index(st.session_state.get(f"{prefix}_x", all_cols[0])) if st.session_state.get(f"{prefix}_x", all_cols[0]) in all_cols else 0, key=f"{prefix}_x")
        remaining_cols = [c for c in all_cols if c != x_col]
        y_col = col2.selectbox("Y axis", remaining_cols, index=remaining_cols.index(st.session_state.get(f"{prefix}_y", remaining_cols[0] if remaining_cols else all_cols[0])) if st.session_state.get(f"{prefix}_y", remaining_cols[0] if remaining_cols else all_cols[0]) in remaining_cols else 0, key=f"{prefix}_y")
        chart_options = ["Line Chart", "Bar Chart", "Pie Chart", "Scatter Chart", "Histogram Chart"]
        chart_type = col3.selectbox("Chart Type", chart_options, index=chart_options.index(st.session_state.get(f"{prefix}_type", default_chart)) if st.session_state.get(f"{prefix}_type", default_chart) in chart_options else chart_options.index(default_chart), key=f"{prefix}_type")
        
        if chart_type == "Line Chart": st.plotly_chart(px.line(df, x=x_col, y=y_col, title=chart_type), key=f"{prefix}_line")
        elif chart_type == "Bar Chart": st.plotly_chart(px.bar(df, x=x_col, y=y_col, title=chart_type), key=f"{prefix}_bar")
        elif chart_type == "Pie Chart": st.plotly_chart(px.pie(df, names=x_col, values=y_col, title=chart_type), key=f"{prefix}_pie")
        elif chart_type == "Scatter Chart": st.plotly_chart(px.scatter(df, x=x_col, y=y_col, title=chart_type), key=f"{prefix}_scatter")
        elif chart_type == "Histogram Chart": st.plotly_chart(px.histogram(df, x=x_col, title=chart_type), key=f"{prefix}_hist")

    with st.sidebar:
        st.markdown("""<style>[data-testid="stSidebar"] [data-testid="stButton"] > button, [data-testid="stButton"] > button {background-color: #29B5E8 !important; color: white !important; font-weight: bold !important; width: 100% !important; height: 60px !important; border-radius: 0px !important; margin: 5px 0 !important; border: none !important; padding: 0.5rem 1rem !important; white-space: normal !important;}</style>""", unsafe_allow_html=True)
        st.image("https://www.snowflake.com/wp-content/themes/snowflake/assets/img/logo-blue.svg", width=250)
        init_config_options()

    st.title("Custom Cortex Text-to-SQL Assistant by DiLytics")
    
    if not st.session_state.welcome_displayed:
        welcome_message = "Hi, I am your Custom Inventory Assistant. I am generating SQL manually using LLMs because the Analyst API is disabled on your Trial Account."
        with st.chat_message("assistant"): st.markdown(welcome_message, unsafe_allow_html=True)
        if not any(msg["content"] == welcome_message for msg in st.session_state.chat_history): st.session_state.chat_history.append({"role": "assistant", "content": welcome_message})
        st.session_state.welcome_displayed = True

    sample_questions = [
        "What is the total quantity of inventory currently on hand?",
        "What is the total available inventory as of the latest snapshot?",
        "What is the inventory value by warehouse as of the latest snapshot?"
    ]

    def suggest_sample_questions(query: str) -> List[str]:
        return sample_questions[:5]

    st.sidebar.subheader("Sample Questions")
    for idx, message in enumerate(st.session_state.chat_history):
        if idx == 0: continue
        if message["role"] == "user":
            with st.chat_message("user"): st.markdown(f"**You:** {message['content']}", unsafe_allow_html=True)
        else:
            with st.chat_message("assistant"):
                st.markdown(message["content"], unsafe_allow_html=True)
            if "results" in message and message["results"] is not None:
                with st.expander("View SQL Query", expanded=False): st.code(message["sql"], language="sql")
                st.markdown(f"**Query Results ({len(message['results'])} rows):**")
                st.dataframe(message["results"])
                if not message["results"].empty and len(message["results"].columns) >= 2:
                    display_chart_tab(message["results"], prefix=f"chart_{idx}_{hash(message['content'])}", query=message.get("query", ""))

    query = st.chat_input("Ask your question...")
        
    for sample in sample_questions[:5]: 
        if st.sidebar.button(sample, key=sample): query = sample

    if query:
        original_query = query
        st.session_state.chat_history.append({"role": "user", "content": original_query})
        st.session_state.messages.append({"role": "user", "content": original_query})
        with st.chat_message("user"): st.markdown(f"**You:** {original_query}", unsafe_allow_html=True)
            
        with st.spinner("Generating Response..."):
            response_placeholder = st.empty()
            is_structured = is_structured_query(query)
            is_summarize = is_summarize_query(query)
            is_suggestion = is_question_suggestion_query(query)
            is_greeting = is_greeting_query(query)
            is_invalid = is_invalid_query(query)
            
            assistant_response = {"role": "assistant", "content": "", "query": query}
            failed_response = False

            if is_greeting or is_suggestion:
                response_content = "Here are some questions you can ask me:\n\n" + "\n".join([f"{i}. {q}" for i, q in enumerate(sample_questions[:5], 1)])
                with response_placeholder:
                    with st.chat_message("assistant"): st.markdown(response_content, unsafe_allow_html=True)
                assistant_response["content"] = response_content

            elif is_invalid:
                suggestions = suggest_sample_questions(query)
                response_content = "I didn't understand. Try:\n\n" + "\n".join([f"{i}. {s}" for i, s in enumerate(suggestions, 1)])
                with response_placeholder:
                    with st.chat_message("assistant"): st.markdown(response_content, unsafe_allow_html=True)
                assistant_response["content"] = response_content
                st.stop()

            elif is_summarize:
                summary = summarize(query)
                if summary:
                    with response_placeholder:
                        with st.chat_message("assistant"): st.markdown(summary, unsafe_allow_html=True)
                    assistant_response["content"] = summary
                else:
                    failed_response = True

            elif is_structured:
                # --- THIS IS THE NEW WORKAROUND LOGIC ---
                sql = generate_sql_from_cortex(query)
                
                if sql:
                    results = run_snowflake_query(sql)
                    if results is not None and not results.empty:
                        results_text = results.to_string(index=False)
                        summary_prompt = f"Provide a concise natural language answer to the query '{query}' using the following data:\n\n{results_text}"
                        summary = complete(st.session_state.model_name, summary_prompt)
                        response_content = summary if summary else "Here are your results:"
                        
                        with response_placeholder:
                            with st.chat_message("assistant"): st.markdown(response_content, unsafe_allow_html=True)
                        with st.expander("View Generated SQL Query", expanded=False): st.code(sql, language="sql")
                        st.markdown(f"**Query Results ({len(results)} rows):**")
                        st.dataframe(results)
                        if len(results.columns) >= 2:
                            st.markdown("**📈 Visualization:**")
                            display_chart_tab(results, prefix=f"chart_{hash(query)}", query=query)
                        
                        assistant_response.update({"content": response_content, "sql": sql, "results": results})
                    else:
                        st.error(f"The LLM generated this query, but it failed or returned 0 rows: \n\n {sql}")
                        failed_response = True
                else:
                    failed_response = True

            else:
                response = create_prompt(query)
                if response:
                    with response_placeholder:
                        with st.chat_message("assistant"): st.markdown(response, unsafe_allow_html=True)
                    assistant_response["content"] = response
                else:
                    failed_response = True

            if failed_response:
                response_content = "I'm sorry, I was unable to generate an answer for your question."
                with response_placeholder:
                    with st.chat_message("assistant"): st.markdown(response_content, unsafe_allow_html=True)
                assistant_response["content"] = response_content

            st.session_state.chat_history.append(assistant_response)
