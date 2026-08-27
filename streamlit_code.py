import streamlit as st
import pandas as pd
from datetime import datetime
import snowflake.connector
from snowflake.snowpark import Session

# Configuration
HOST = "XYUHKAV-XRB12650.snowflakecomputing.com"
ACCOUNT = "XYUHKAV-XRB12650"
DATABASE = "INVENTORY_DW"
SCHEMA = "GOLD"
WAREHOUSE = "COMPUTE_WH"

# Page Configuration
st.set_page_config(page_title="Inventory AI Copilot", page_icon="📦", layout="wide")

# Custom UI Styling
st.markdown("""
<style>
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background-color: #ecfdf5;
        color: #065f46;
        border: 1px solid #a7f3d0;
        border-radius: 20px;
        padding: 2px 10px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    div[data-testid="stButton"] > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease-in-out;
    }
</style>
""", unsafe_allow_html=True)


# ===================================================================
# 1. STREAMLIT CLOUD LOGIN SCREEN
# ===================================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = "PBCS"
    st.session_state.password = ""
    st.session_state.snowpark_session = None

if not st.session_state.authenticated:
    st.title("Welcome to Inventory AI Copilot")
    st.markdown("Please login to connect to your Snowflake Data Warehouse.")
    
    st.session_state.username = st.text_input("Enter Snowflake Username:", value=st.session_state.username)
    st.session_state.password = st.text_input("Enter Password:", type="password")
    
    if st.button("Login"):
        try:
            with st.spinner("Connecting to Snowflake..."):
                conn = snowflake.connector.connect(
                    user=st.session_state.username,
                    password=st.session_state.password,
                    account=ACCOUNT,
                    host=HOST,
                    port=443,
                    warehouse=WAREHOUSE,
                    role="ACCOUNTADMIN",
                    database=DATABASE,
                    schema=SCHEMA
                )
                # Create the Snowpark session
                st.session_state.snowpark_session = Session.builder.configs({"connection": conn}).create()
                st.session_state.authenticated = True
                st.rerun()
        except Exception as e:
            st.error(f"Authentication failed: {e}")
            
    # Stop execution here until the user logs in
    st.stop()


# ===================================================================
# 2. MAIN APP LOGIC (Runs only after login)
# ===================================================================

# Get the authenticated session
session = st.session_state.snowpark_session

# Session State Management for Multi-Chat History
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {}
if "current_session_id" not in st.session_state:
    init_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.current_session_id = init_id
    st.session_state.chat_sessions[init_id] = {
        "title": "New Conversation",
        "messages": []
    }

# Shortcut to active messages list
current_id = st.session_state.current_session_id
messages = st.session_state.chat_sessions[current_id]["messages"]

# Helper: Interactive Chart Renderer
def display_chart_tab(df: pd.DataFrame, key_prefix: str = ""):
    if len(df.columns) < 2:
        st.info("Need at least 2 columns to render a chart.")
        return

    all_cols = list(df.columns)
    col1, col2, col3 = st.columns(3)
    x_key = f"{key_prefix}_x" if key_prefix else "x_axis"
    y_key = f"{key_prefix}_y" if key_prefix else "y_axis"
    t_key = f"{key_prefix}_type" if key_prefix else "chart_type"
    x_col = col1.selectbox("Dimension (X-axis)", all_cols, index=0, key=x_key)
    remaining_cols = [c for c in all_cols if c != x_col]
    y_col = col2.selectbox("Metric (Y-axis)", remaining_cols, index=0 if remaining_cols else 0, key=y_key)
    chart_type = col3.selectbox("Chart Type", ["Bar Chart", "Line Chart", "Area Chart", "Scatter Plot"], key=t_key)

    chart_df = df.copy()
    if any(k in x_col.lower() for k in ["year", "quarter", "month", "day", "date"]):
        chart_df[x_col] = chart_df[x_col].apply(lambda x: str(int(x)) if pd.notnull(x) and isinstance(x, (int, float)) else str(x))

    if chart_type == "Bar Chart":
        st.bar_chart(chart_df.set_index(x_col)[y_col])
    elif chart_type == "Line Chart":
        st.line_chart(chart_df.set_index(x_col)[y_col])
    elif chart_type == "Area Chart":
        st.area_chart(chart_df.set_index(x_col)[y_col])
    elif chart_type == "Scatter Plot":
        st.scatter_chart(chart_df, x=x_col, y=y_col)

# YAML Verified Query Matcher & Rule-Based SQL Engine
def generate_sql_from_prompt(prompt: str):
    p = prompt.lower().strip()
    
    # 0. Greetings & Status Questions
    if any(greet in p for greet in ["how are you", "how's it going", "what's up", "whats up"]):
        explanation = "I'm doing well, thank you! I am ready to help you analyze inventory levels, stockouts, warehouses, and product categories. What metric would you like to explore?"
        return explanation, None

    elif p in ["hi", "hello", "hey", "help", "good morning", "good evening"]:
        explanation = "Hello! I am your Inventory Intelligence Assistant powered by your semantic data model. Ask any question about stock, warehouses, products, or supply!"
        return explanation, None

    # 1. Total available inventory value
    if "total available inventory" in p or ("inventory value" in p and "warehouse" not in p and "category" not in p and "brand" not in p):
        explanation = "Calculating total inventory value across all warehouses as of the latest snapshot."
        sql = """
        SELECT SUM(INVENTORY_VALUE_AMT) AS TOTAL_INVENTORY_VALUE
        FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT
        WHERE SNAPSHOT_DATE_KEY = (SELECT MAX(SNAPSHOT_DATE_KEY) FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT)
        """
        return explanation, sql.strip()

    # 2. Total quantity on hand
    elif "quantity" in p and "on hand" in p and "product" not in p:
        explanation = "Calculating the total physical quantity of inventory currently on hand."
        sql = """
        SELECT SUM(ON_HAND_QTY) AS TOTAL_ON_HAND_QTY
        FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT
        WHERE SNAPSHOT_DATE_KEY = (SELECT MAX(SNAPSHOT_DATE_KEY) FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT)
        """
        return explanation, sql.strip()

    # 3. Inventory value by warehouse
    elif "inventory value by warehouse" in p:
        explanation = "Aggregating total inventory value grouped by warehouse location."
        sql = """
        SELECT w.WAREHOUSE_NAME, SUM(f.INVENTORY_VALUE_AMT) AS INVENTORY_VALUE
        FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT f
        JOIN INVENTORY_DW.GOLD.DIM_WAREHOUSE w ON f.WAREHOUSE_KEY = w.WAREHOUSE_KEY
        WHERE f.SNAPSHOT_DATE_KEY = (SELECT MAX(SNAPSHOT_DATE_KEY) FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT)
        GROUP BY w.WAREHOUSE_NAME ORDER BY INVENTORY_VALUE DESC
        """
        return explanation, sql.strip()

    # 4. Total inventory value by product category
    elif "inventory value by product category" in p or "by category" in p:
        explanation = "Aggregating inventory value by product category."
        sql = """
        SELECT p.CATEGORY_NAME, SUM(f.INVENTORY_VALUE_AMT) AS TOTAL_INVENTORY_VALUE
        FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT f
        JOIN INVENTORY_DW.GOLD.DIM_PRODUCT p ON f.PRODUCT_KEY = p.PRODUCT_KEY
        WHERE f.SNAPSHOT_DATE_KEY = (SELECT MAX(SNAPSHOT_DATE_KEY) FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT)
        GROUP BY p.CATEGORY_NAME ORDER BY TOTAL_INVENTORY_VALUE DESC
        """
        return explanation, sql.strip()

    # 5. Inventory value by subcategory
    elif "subcategory" in p:
        explanation = "Aggregating inventory value by product subcategory."
        sql = """
        SELECT p.SUBCATEGORY_NAME, SUM(f.INVENTORY_VALUE_AMT) AS TOTAL_INVENTORY_VALUE
        FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT f
        JOIN INVENTORY_DW.GOLD.DIM_PRODUCT p ON f.PRODUCT_KEY = p.PRODUCT_KEY
        WHERE f.SNAPSHOT_DATE_KEY = (SELECT MAX(SNAPSHOT_DATE_KEY) FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT)
        GROUP BY p.SUBCATEGORY_NAME ORDER BY TOTAL_INVENTORY_VALUE DESC
        """
        return explanation, sql.strip()

    # 6. Inventory value by brand
    elif "brand" in p:
        explanation = "Aggregating inventory value by product brand."
        sql = """
        SELECT p.BRAND_NAME, SUM(f.INVENTORY_VALUE_AMT) AS TOTAL_INVENTORY_VALUE
        FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT f
        JOIN INVENTORY_DW.GOLD.DIM_PRODUCT p ON f.PRODUCT_KEY = p.PRODUCT_KEY
        WHERE f.SNAPSHOT_DATE_KEY = (SELECT MAX(SNAPSHOT_DATE_KEY) FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT)
        GROUP BY p.BRAND_NAME ORDER BY TOTAL_INVENTORY_VALUE DESC
        """
        return explanation, sql.strip()

    # 7. Products out of stock / Stockout count
    elif "stockout" in p or "out of stock" in p:
        if "warehouse" in p:
            explanation = "Calculating the number of stockouts organized by warehouse."
            sql = """
            SELECT w.WAREHOUSE_NAME, COUNT_IF(f.IS_STOCKOUT_FLAG) AS STOCKOUT_COUNT
            FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT f
            JOIN INVENTORY_DW.GOLD.DIM_WAREHOUSE w ON f.WAREHOUSE_KEY = w.WAREHOUSE_KEY
            WHERE f.SNAPSHOT_DATE_KEY = (SELECT MAX(SNAPSHOT_DATE_KEY) FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT)
            GROUP BY w.WAREHOUSE_NAME ORDER BY STOCKOUT_COUNT DESC
            """
        else:
            explanation = "Counting how many products are completely out of stock."
            sql = """
            SELECT COUNT(*) AS STOCKOUT_COUNT
            FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT
            WHERE SNAPSHOT_DATE_KEY = (SELECT MAX(SNAPSHOT_DATE_KEY) FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT)
            AND IS_STOCKOUT_FLAG = TRUE
            """
        return explanation, sql.strip()

    # 8. Excess inventory value by warehouse
    elif "excess" in p and "warehouse" in p:
        explanation = "Aggregating the financial value of excess stock held above safety buffers by warehouse."
        sql = """
        SELECT w.WAREHOUSE_NAME, SUM(f.EXCESS_STOCK_VALUE_AMT) AS TOTAL_EXCESS_VALUE
        FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT f
        JOIN INVENTORY_DW.GOLD.DIM_WAREHOUSE w ON f.WAREHOUSE_KEY = w.WAREHOUSE_KEY
        WHERE f.SNAPSHOT_DATE_KEY = (SELECT MAX(SNAPSHOT_DATE_KEY) FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT)
        GROUP BY w.WAREHOUSE_NAME ORDER BY TOTAL_EXCESS_VALUE DESC
        """
        return explanation, sql.strip()

    # 9. Top 10 products by inventory value
    elif "top 10" in p and "inventory value" in p:
        explanation = "Ranking the top 10 products carrying the highest inventory value."
        sql = """
        SELECT p.PRODUCT_SKU, p.PRODUCT_NAME, SUM(f.INVENTORY_VALUE_AMT) AS INVENTORY_VALUE
        FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT f
        JOIN INVENTORY_DW.GOLD.DIM_PRODUCT p ON f.PRODUCT_KEY = p.PRODUCT_KEY
        WHERE f.SNAPSHOT_DATE_KEY = (SELECT MAX(SNAPSHOT_DATE_KEY) FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT)
        GROUP BY p.PRODUCT_SKU, p.PRODUCT_NAME ORDER BY INVENTORY_VALUE DESC LIMIT 10
        """
        return explanation, sql.strip()

    # 10. Reorder needed
    elif "reorder" in p:
        explanation = "Counting products that have fallen below their reorder threshold."
        sql = """
        SELECT COUNT(*) AS REORDER_NEEDED_COUNT
        FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT
        WHERE SNAPSHOT_DATE_KEY = (SELECT MAX(SNAPSHOT_DATE_KEY) FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT)
        AND IS_REORDER_NEEDED_FLAG = TRUE
        """
        return explanation, sql.strip()

    # 11. ABC Classification
    elif "abc" in p:
        explanation = "Evaluating inventory value across ABC classification tiers."
        sql = """
        SELECT p.ABC_CLASSIFICATION, SUM(f.INVENTORY_VALUE_AMT) AS TOTAL_INVENTORY_VALUE
        FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT f
        JOIN INVENTORY_DW.GOLD.DIM_PRODUCT p ON f.PRODUCT_KEY = p.PRODUCT_KEY
        WHERE f.SNAPSHOT_DATE_KEY = (SELECT MAX(SNAPSHOT_DATE_KEY) FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT)
        GROUP BY p.ABC_CLASSIFICATION ORDER BY p.ABC_CLASSIFICATION
        """
        return explanation, sql.strip()

    # 12. Out-of-Domain Guardrail Check
    domain_keywords = [
        "inventory", "warehouse", "product", "stock", "stockout", "excess", "quarantine", "reorder", 
        "category", "subcategory", "brand", "abc", "hazardous", "perishable", "cold-chain", "sku", "supply", "quantity"
    ]
    if not any(word in p for word in domain_keywords):
        explanation = (
            "I am specialized strictly as an **Inventory Domain Intelligence Copilot**.\n\n"
            "I don't have external web data to answer general knowledge or non-inventory queries. "
            "Please ask a question related to stock, warehouses, products, or supply!"
        )
        return explanation, None

    # 13. Fallback Overview
    else:
        explanation = "Displaying a recent snapshot overview of inventory by product and warehouse:"
        sql = """
        SELECT 
            d.FULL_DATE, p.PRODUCT_NAME, w.WAREHOUSE_NAME, f.ON_HAND_QTY, f.INVENTORY_VALUE_AMT, f.IS_STOCKOUT_FLAG
        FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT f
        JOIN INVENTORY_DW.GOLD.DIM_DATE d ON f.SNAPSHOT_DATE_KEY = d.DATE_KEY
        JOIN INVENTORY_DW.GOLD.DIM_PRODUCT p ON f.PRODUCT_KEY = p.PRODUCT_KEY
        JOIN INVENTORY_DW.GOLD.DIM_WAREHOUSE w ON f.WAREHOUSE_KEY = w.WAREHOUSE_KEY
        WHERE f.SNAPSHOT_DATE_KEY = (SELECT MAX(SNAPSHOT_DATE_KEY) FROM INVENTORY_DW.GOLD.FACT_INVENTORY_DAILY_SNAPSHOT)
        ORDER BY f.INVENTORY_VALUE_AMT DESC
        LIMIT 20
        """
        return explanation, sql.strip()

# ----------------- LEFT NATIVE SIDEBAR PANEL -----------------
with st.sidebar:
    st.markdown("### ⚡ Copilot")
    st.markdown('<span class="status-pill">● Semantic Mart Live</span>', unsafe_allow_html=True)
    st.write("")
    
    # ➕ New Chat Action
    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        new_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.current_session_id = new_id
        st.session_state.chat_sessions[new_id] = {
            "title": f"Chat {len(st.session_state.chat_sessions) + 1}",
            "messages": []
        }
        st.rerun()

    st.markdown("---")
    st.markdown("##### 🕒 Recent Conversations")
    
    # List of Chat Sessions
    for s_id, s_data in reversed(list(st.session_state.chat_sessions.items())):
        is_active = (s_id == st.session_state.current_session_id)
        session_label = s_data["title"]
        if len(session_label) > 20:
            session_label = session_label[:18] + "..."
        if st.button(f"{'👉 ' if is_active else '🗨️ '}{session_label}", key=f"sess_{s_id}", use_container_width=True):
            st.session_state.current_session_id = s_id
            st.rerun()

    st.markdown("---")
    if st.button("🗑️ Clear All Sessions", use_container_width=True):
        st.session_state.chat_sessions = {}
        init_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.current_session_id = init_id
        st.session_state.chat_sessions[init_id] = {
            "title": "New Conversation",
            "messages": []
        }
        st.rerun()


# ----------------- MAIN CHAT & ANALYTICS AREA -----------------
# Header Bar
head_col1, head_col2 = st.columns([4.5, 1.2])
with head_col1:
    st.title("💬 Inventory AI Copilot")
    st.caption("Ask questions in natural language to explore stock levels, warehouse capacity, and product segments.")
with head_col2:
    st.write("")
    if st.button("🔄 Reset Thread", use_container_width=True, help="Clear message history in this specific thread"):
        st.session_state.chat_sessions[current_id]["messages"] = []
        st.session_state.chat_sessions[current_id]["title"] = "New Conversation"
        st.rerun()

# User-Centric Help & Capabilities Guide
with st.expander("💡 What can I ask this assistant?", expanded=False):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        **🎯 Warehouse & Stock Levels**
        * Track total physical quantity on hand and available inventory.
        * Breakdown inventory value by warehouse location.
        * Identify excess stock value holding up capital.
        **⚠️ Exceptions & Supply Issues**
        * Find out exactly how many products are currently out of stock.
        * Discover which products urgently need to be reordered.
        * Analyze quarantine inventory.
        """)
    with col_b:
        st.markdown("""
        **📦 Products & Categories**
        * Breakdown stock value by category, subcategory, and brand.
        * Analyze the top 10 products carrying the most inventory value.
        * Segment inventory by ABC classification.
        **❄️ Handling & Logistics**
        * Find inventory value for perishable or hazardous goods.
        * Calculate value of stock requiring cold-chain handling.
        """)
    st.info("💡 **Pro-Tip:** Type naturally below or click any quick-prompt button to get started.")

# Onboarding / Verified Questions Selector
st.markdown("##### 💡 Verified Onboarding Questions:")
q_col1, q_col2, q_col3, q_col4, q_col5 = st.columns(5)
quick_prompt = None

if q_col1.button("💰 Total Inv. Value", use_container_width=True):
    quick_prompt = "What is the total available inventory?"
if q_col2.button("🏭 Value by Warehouse", use_container_width=True):
    quick_prompt = "What is the inventory value by warehouse?"
if q_col3.button("📦 Value by Category", use_container_width=True):
    quick_prompt = "What is the inventory value by product category?"
if q_col4.button("📉 Stockout Count", use_container_width=True):
    quick_prompt = "How many products are out of stock?"
if q_col5.button("⚠️ Excess Stock", use_container_width=True):
    quick_prompt = "What is the total excess inventory value by warehouse?"

# Display Current Thread's History
for idx, msg in enumerate(messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg and msg["sql"]:
            with st.expander("Generated SQL", expanded=False):
                st.code(msg["sql"], language="sql")
        if "data" in msg and msg["data"] is not None:
            tab_data, tab_chart = st.tabs(["Data 📄", "Chart 📈"])
            with tab_data:
                st.dataframe(msg["data"])
            with tab_chart:
                display_chart_tab(msg["data"], key_prefix=f"hist_{current_id}_{idx}")

# Handle Inputs
user_prompt = st.chat_input("Ask a question about inventory, warehouses, products, or stockouts...") or quick_prompt

if user_prompt:
    if len(messages) == 0:
        st.session_state.chat_sessions[current_id]["title"] = user_prompt[:25] + ("..." if len(user_prompt) > 25 else "")

    messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        explanation, sql_query = generate_sql_from_prompt(user_prompt)
        st.markdown(explanation)
        df = None
        if sql_query:
            with st.expander("Generated SQL", expanded=False):
                st.code(sql_query, language="sql")

            try:
                df = session.sql(sql_query).to_pandas()
                tab_data, tab_chart = st.tabs(["Data 📄", "Chart 📈"])
                with tab_data:
                    st.dataframe(df)
                with tab_chart:
                    display_chart_tab(df, key_prefix=f"live_{current_id}")
            except Exception as e:
                st.error(f"SQL Execution Error: {str(e)}")

        messages.append({
            "role": "assistant",
            "content": explanation,
            "sql": sql_query,
            "data": df
        })
        st.rerun()
