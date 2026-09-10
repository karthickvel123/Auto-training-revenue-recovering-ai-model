import streamlit as st
import streamlit.components.v1 as components
import requests
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="Adaptive Revenue Recovery Agent", 
    page_icon="🔄", 
    layout="wide",
    initial_sidebar_state="expanded"
)

API_URL = "http://127.0.0.1:8000"

st.title("🔄 Adaptive Revenue Recovery Agent")
st.caption("Fintech-grade payment recovery agent: AI failure reasoning + deterministic safety gateway + outcome-driven learning")

# Sidebar
st.sidebar.title("⚙️ Controls & Setup")

# API Configuration Section
with st.sidebar.expander("🔑 Razorpay & AI API Keys", expanded=True):
    st.markdown("**Real Gateway Integration**")
    cfg_status = {}
    try:
        cfg_res = requests.get(f"{API_URL}/api/config-status", timeout=2)
        if cfg_res.status_code == 200:
            cfg_status = cfg_res.json()
    except Exception:
        pass
        
    has_rzp = cfg_status.get("has_razorpay_keys", False)
    if has_rzp:
        st.success(f"🟢 Razorpay Active: `{cfg_status.get('razorpay_key_id')}`")
    else:
        st.warning("⚠️ Using test placeholders. Enter your Razorpay Test keys below for live gateway calls.")
        
    rzp_key_input = st.text_input("Razorpay Key ID", placeholder="rzp_test_...", type="password")
    rzp_secret_input = st.text_input("Razorpay Key Secret", placeholder="Enter secret", type="password")
    webhook_secret_input = st.text_input("Webhook Secret", placeholder="Enter webhook secret", type="password")
    openai_key_input = st.text_input("OpenAI API Key (Optional)", placeholder="sk-...", type="password")
    
    if st.button("💾 Save Credentials to .env", use_container_width=True):
        payload = {}
        if rzp_key_input: payload["razorpay_key_id"] = rzp_key_input
        if rzp_secret_input: payload["razorpay_key_secret"] = rzp_secret_input
        if webhook_secret_input: payload["razorpay_webhook_secret"] = webhook_secret_input
        if openai_key_input: payload["openai_api_key"] = openai_key_input
        
        try:
            save_res = requests.post(f"{API_URL}/api/save-config", json=payload, timeout=5)
            if save_res.status_code == 200:
                st.success("Saved! Reloading...")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Failed to save credentials.")
        except Exception as e:
            st.error(f"Error saving: {e}")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🛍️ Customer Storefront")
st.sidebar.markdown("Test the live consumer shopping & checkout recovery experience:")
st.sidebar.link_button("⚡ Open VoltStore Storefront", "http://127.0.0.1:8000/", use_container_width=True)

st.sidebar.info(
    "**Core Philosophy:**\n"
    "Failure → Reasoning → Strategy Selection → Safety Gate → Action → Outcome → Learning"
)

auto_refresh = st.sidebar.checkbox("Auto-refresh (10s)", value=False)
if st.sidebar.button("🔄 Refresh Data Now", use_container_width=True):
    st.rerun()

st.sidebar.divider()
st.sidebar.markdown("### 🔌 API Status")

def fetch_metrics():
    try:
        response = requests.get(f"{API_URL}/api/metrics", timeout=4)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None

metrics = fetch_metrics()
if metrics:
    st.sidebar.success("🟢 Backend Connected (Port 8000)")
else:
    st.sidebar.error("🔴 Backend Disconnected\nMake sure `uvicorn backend.main:app` is running.")

st.sidebar.divider()
st.sidebar.markdown(
    "**Official Razorpay Test Docs:**\n"
    "- [Test Cards & Integration](https://razorpay.com/docs/payments/payments/test-integration/)\n"
    "- Mock UPI: `failure@razorpay`"
)

# Top Metrics Row
if metrics:
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        total_tx = metrics.get("transactions_processed") or metrics.get("total_transactions", 0)
        st.metric("Transactions Processed", f"{total_tx:,}")
    with col2:
        failed = metrics.get("failed_payments", 0)
        st.metric("Failed Payments", f"{failed:,}")
    with col3:
        recovered = metrics.get("recovered_transactions", 0)
        st.metric("Recovered", f"{recovered:,}")
    with col4:
        amount_rec_paise = metrics.get("amount_recovered_paise") or metrics.get("amount_recovered", 0)
        st.metric("Amount Recovered", f"₹{amount_rec_paise / 100:,.2f}")
    with col5:
        rate = metrics.get("recovery_rate_percent") or metrics.get("recovery_rate", 0.0)
        st.metric("Recovery Rate", f"{rate:.1f}%")
    with col6:
        pending = metrics.get("pending_recovery", 0)
        st.metric("Pending Recovery", f"{pending:,}")
    st.divider()

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🔴 Live Demo & Simulation", 
    "📋 Transactions", 
    "🔍 Transaction Detail", 
    "📊 Strategy Performance", 
    "🔥 Failure Analytics & Insights", 
    "📝 Agent Audit Log"
])

# ==========================================
# TAB 1: LIVE DEMO & SIMULATION
# ==========================================
with tab1:
    st.header("🔴 Live Recovery Pipeline Demonstration")
    st.write(
        "Demonstrate the end-to-end autonomous recovery lifecycle with real Razorpay Test Mode transactions."
    )
    
    with st.expander("ℹ️ How the Demo Works", expanded=False):
        st.markdown("""
        1. **Create Order:** Generates a real Razorpay test order via Razorpay API.
        2. **Simulate/Trigger Failure:** Either fail it via Razorpay Test Checkout or instant test webhook simulation.
        3. **Autonomous Pipeline:**
           - Webhook received and verified via HMAC-SHA256 signature.
           - AI analyzes the Razorpay error (`error_code`, `error_reason`, `error_step`).
           - Strategy engine chooses optimal recovery strategy based on past outcomes.
           - Deterministic safety gateway verifies 7 fintech safety rules.
           - Real Razorpay Payment Link generated and sent.
        4. **Recovery Capture:** Payment is completed via link → Webhook captures event → Transaction marked **RECOVERED**.
        """)

    col_a, col_b = st.columns([1, 1])
    
    with col_a:
        st.subheader("1. Setup Test Transaction")
        amount_input = st.number_input("Transaction Amount (₹)", min_value=1.0, max_value=50000.0, value=500.0, step=50.0)
        error_scenario = st.selectbox(
            "Simulated Failure Scenario",
            [
                ("insufficient_funds", "Customer Action: Insufficient Funds (Card)"),
                ("wrong_otp", "Customer Action: OTP Authentication Failed"),
                ("network_error", "Temporary: Bank Gateway Timeout"),
                ("suspected_fraud", "Security: Risk / Fraud Flag (Must Block)"),
                ("invalid_card_number", "Permanent: Invalid Card Number (Must Stop)"),
                ("account_closed", "Permanent: Bank Account Closed (Must Stop)"),
            ],
            format_func=lambda x: x[1]
        )
        
        create_btn = st.button("🚀 1. Create Real Razorpay Test Order", use_container_width=True)
        if create_btn:
            try:
                paise = int(amount_input * 100)
                res = requests.post(f"{API_URL}/api/create-test-order", json={"amount": paise}, timeout=10)
                if res.status_code == 200:
                    order_data = res.json()
                    st.session_state["demo_order_id"] = order_data["order_id"]
                    st.session_state["demo_order_amount"] = amount_input
                    st.session_state["demo_key_id"] = order_data.get("razorpay_key_id", "")
                    st.success(f"Created Real Razorpay Order: `{order_data['order_id']}`")
                else:
                    st.error(f"Error creating order: {res.text}")
            except Exception as e:
                st.error(f"Connection failed: {e}")

    with col_b:
        st.subheader("2. Test Payment / Trigger Failure")
        demo_order_id = st.session_state.get("demo_order_id")
        if demo_order_id:
            st.info(f"Active Test Order: **{demo_order_id}** (₹{st.session_state.get('demo_order_amount', 500)})")
            
            key_id = st.session_state.get('demo_key_id', '')
            amt_paise = int(st.session_state.get('demo_order_amount', 500) * 100)
            
            # Option 1: Real Interactive Razorpay Checkout Modal
            if key_id and "xxxx" not in key_id and key_id != "rzp_test_placeholder":
                st.markdown("**Method A: Real Razorpay Modal (Live Popup)**")
                checkout_html = f"""
                <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
                <button id="rzp-button" style="background:#0F88EB;color:#fff;border:none;padding:10px 18px;border-radius:6px;font-size:15px;font-weight:600;cursor:pointer;width:100%;">
                    💳 Open Real Razorpay Checkout Modal
                </button>
                <script>
                var options = {{
                    "key": "{key_id}",
                    "amount": "{amt_paise}",
                    "currency": "INR",
                    "name": "Revenue Recovery Agent",
                    "description": "Order {demo_order_id}",
                    "order_id": "{demo_order_id}",
                    "prefill": {{
                        "name": "Test Customer",
                        "email": "customer@example.com",
                        "contact": "9999999999"
                    }},
                    "theme": {{"color": "#0F88EB"}}
                }};
                var rzp1 = new Razorpay(options);
                document.getElementById('rzp-button').onclick = function(e){{
                    rzp1.open();
                    e.preventDefault();
                }};
                </script>
                """
                components.html(checkout_html, height=55)
                st.caption("Click above to test via Razorpay modal → pick Netbanking / UPI → Click **Failure** on bank page.")
            else:
                st.info("💡 To launch the live Razorpay modal, save your real `RAZORPAY_KEY_ID` in the sidebar.")
            
            # Option 2: Instant webhook trigger
            st.markdown("**Method B: Instant Webhook Dispatch**")
            trigger_fail_btn = st.button("⚡ Dispatch Failure Webhook Directly", type="primary", use_container_width=True)
            if trigger_fail_btn:
                try:
                    fail_res = requests.post(
                        f"{API_URL}/api/trigger-test-failure",
                        params={"order_id": demo_order_id, "error_reason": error_scenario[0]},
                        timeout=10
                    )
                    if fail_res.status_code == 200:
                        st.success(f"Webhook dispatched for failure reason: `{error_scenario[0]}`")
                    else:
                        st.error(f"Webhook dispatch failed: {fail_res.text}")
                except Exception as e:
                    st.error(f"Error triggering webhook: {e}")
        else:
            st.warning("Click 'Create Real Razorpay Test Order' first to begin the demo flow.")

    st.divider()
    st.subheader("3. Live Pipeline Visualization")
    
    current_order = st.session_state.get("demo_order_id")
    if current_order:
        status_box = st.empty()
        
        try:
            poll_res = requests.get(f"{API_URL}/api/simulation-status/{current_order}", timeout=5)
            if poll_res.status_code == 200:
                s_data = poll_res.json()
                
                if s_data.get("webhook_received"):
                    ai_cls = s_data.get("ai_classification", {})
                    category = ai_cls.get("category") or ai_cls.get("failure_category", "analyzing...")
                    strategy = s_data.get("strategy") or "Evaluating..."
                    safety = s_data.get("safety") or "Verifying..."
                    link = s_data.get("recovery_link")
                    recovered = s_data.get("recovered", False)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.markdown(f"**Step 1: Webhook**\n\n✅ `payment.failed` received")
                    with c2:
                        st.markdown(f"**Step 2: AI Reasoning**\n\n🧠 Category: `{category}`")
                    with c3:
                        st.markdown(f"**Step 3: Strategy Selected**\n\n🎯 `{strategy}`")
                    with c4:
                        st.markdown(f"**Step 4: Safety Gate**\n\n🛡️ `{safety}`")
                    
                    st.write("")
                    if link:
                        st.success(f"🔗 **Real Razorpay Recovery Payment Link Created:**")
                        st.markdown(f"👉 **[Click here to complete payment on Razorpay: {link}]({link})**")
                    elif strategy == "stop":
                        st.warning("🛑 Recovery stopped by Fintech Safety Gateway (fraud or permanent failure).")
                    elif strategy == "human_review":
                        st.info("👤 High-value or high-risk transaction routed to Human Review Queue.")
                    
                    if recovered:
                        st.balloons()
                        st.success("🎉 **Payment RECOVERED! Outcome updated in historical learning engine.**")
                else:
                    status_box.info(f"⏳ Waiting for failure webhook on order `{current_order}`...")
        except Exception as e:
            status_box.error(f"Error checking pipeline status: {e}")
    else:
        st.info("No active demo session. Create an order above to watch the pipeline execute live.")

# ==========================================
# TAB 2: TRANSACTIONS
# ==========================================
with tab2:
    st.header("📋 Transactions Ledger")
    
    col_f1, col_f2 = st.columns([1, 3])
    with col_f1:
        status_filter = st.selectbox("Filter by Status", ["ALL", "FAILED", "RECOVERED", "CAPTURED", "AUTHORIZED"])
    
    try:
        url = f"{API_URL}/api/transactions"
        if status_filter != "ALL":
            url += f"?status={status_filter}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            txs = res.json()
            if txs:
                df = pd.DataFrame(txs)
                display_cols = [
                    "transaction_id", "amount", "status", "error_reason", 
                    "selected_strategy", "recovery_status", "created_at"
                ]
                available_cols = [c for c in display_cols if c in df.columns]
                df_disp = df[available_cols].copy()
                if "amount" in df_disp.columns:
                    df_disp["amount"] = df_disp["amount"] / 100
                
                st.dataframe(
                    df_disp,
                    use_container_width=True,
                    column_config={
                        "amount": st.column_config.NumberColumn("Amount (₹)", format="₹%.2f"),
                        "transaction_id": st.column_config.TextColumn("Transaction ID"),
                        "status": st.column_config.TextColumn("Payment Status"),
                        "recovery_status": st.column_config.TextColumn("Recovery Status"),
                    }
                )
            else:
                st.info("⏳ Waiting for Razorpay Test Mode transactions...")
    except Exception as e:
        st.error(f"Could not load transactions: {e}")

# ==========================================
# TAB 3: TRANSACTION DETAIL TRACE
# ==========================================
with tab3:
    st.header("🔍 Transaction Deep Dive & Decision Trace")
    try:
        res = requests.get(f"{API_URL}/api/transactions", timeout=5)
        if res.status_code == 200 and res.json():
            txs = res.json()
            tx_map = {f"{t['transaction_id']} (₹{t['amount']/100:,.2f} - {t.get('error_reason','N/A')})": t['transaction_id'] for t in txs}
            selected_key = st.selectbox("Select a Transaction to Inspect", list(tx_map.keys()))
            
            if selected_key:
                selected_id = tx_map[selected_key]
                tx_res = requests.get(f"{API_URL}/api/transactions/{selected_id}")
                if tx_res.status_code == 200:
                    t = tx_res.json()
                    
                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        st.markdown("#### 1. Razorpay Failure Metadata")
                        st.json({
                            "transaction_id": t.get("transaction_id"),
                            "order_id": t.get("order_id"),
                            "amount_rupees": t.get("amount", 0) / 100,
                            "error_code": t.get("error_code"),
                            "error_description": t.get("error_description"),
                            "error_source": t.get("error_source"),
                            "error_step": t.get("error_step"),
                            "error_reason": t.get("error_reason"),
                            "payment_method": t.get("payment_method"),
                        })
                        
                        st.markdown("#### 2. AI Failure Reasoning")
                        st.json(t.get("ai_classification") or {"note": "No AI classification recorded yet"})
                    
                    with col_t2:
                        st.markdown("#### 3. Strategy Selection & Safety Check")
                        st.write(f"**Selected Strategy:** `{t.get('selected_strategy', 'N/A')}`")
                        st.write(f"**Safety Verdict:** `{t.get('safety_decision', 'N/A')}`")
                        st.write(f"**Recovery Attempt Count:** `{t.get('recovery_attempt_count', 0)}`")
                        st.write(f"**Recovery Status:** `{t.get('recovery_status', 'N/A')}`")
                        if t.get("recovered_amount"):
                            st.success(f"**Amount Recovered:** ₹{t.get('recovered_amount')/100:,.2f}")
        else:
            st.info("No transactions available to inspect.")
    except Exception as e:
        st.error(f"Error: {e}")

# ==========================================
# TAB 4: STRATEGY PERFORMANCE & LEARNING
# ==========================================
with tab4:
    st.header("📊 Adaptive Strategy Performance (The Learning Loop)")
    st.write(
        "Demonstrates outcome-driven adaptive selection: strategies that achieve higher success rates "
        "are preferred for future failures of the same category."
    )
    
    try:
        res = requests.get(f"{API_URL}/api/strategy-stats", timeout=5)
        if res.status_code == 200:
            stats = res.json()
            if stats:
                df_stats = pd.DataFrame(stats)
                df_stats["recovery_rate_pct"] = df_stats["recovery_rate"] * 100
                df_stats["amount_recovered_inr"] = df_stats["total_amount_recovered"] / 100
                
                st.dataframe(
                    df_stats[[
                        "failure_category", "error_reason", "strategy", 
                        "attempts", "successful_recoveries", "recovery_rate_pct", "amount_recovered_inr"
                    ]],
                    use_container_width=True,
                    column_config={
                        "recovery_rate_pct": st.column_config.NumberColumn("Recovery Rate (%)", format="%.1f%%"),
                        "amount_recovered_inr": st.column_config.NumberColumn("Total Recovered (₹)", format="₹%.2f"),
                    }
                )
                
                fig = px.bar(
                    df_stats,
                    x="strategy",
                    y="recovery_rate_pct",
                    color="failure_category",
                    barmode="group",
                    title="Recovery Rate by Strategy and Failure Category",
                    labels={"recovery_rate_pct": "Recovery Rate (%)", "strategy": "Strategy"}
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No historical strategy statistics yet. Run demo recoveries to observe the learning loop update in real-time.")
    except Exception as e:
        st.error(f"Could not load strategy performance: {e}")

# ==========================================
# TAB 5: FAILURE ANALYTICS & INSIGHTS
# ==========================================
with tab5:
    st.header("🔥 Failure Pattern Heatmap & Predictive AI Insights")
    st.write("Discovers systemic payment failure patterns and recommends automated operational fixes.")
    
    try:
        res = requests.get(f"{API_URL}/api/insights", timeout=5)
        if res.status_code == 200:
            data = res.json()
            
            # AI Insight Card
            ai_insight = data.get("ai_insight", {})
            if ai_insight and ai_insight.get("headline") not in ["No Data", "Insight Generation Failed"]:
                st.markdown(f"""
                <div style="background-color:#1E293B; border-left: 5px solid #38BDF8; padding: 16px; border-radius: 8px; margin-bottom: 24px;">
                    <h4 style="color:#38BDF8; margin:0 0 8px 0;">💡 AI Failure Insight: {ai_insight.get('headline')}</h4>
                    <p style="margin:0 0 8px 0;"><strong>Pattern Detected:</strong> {ai_insight.get('pattern')}</p>
                    <p style="margin:0;"><strong>Recommendation:</strong> {ai_insight.get('recommendation')}</p>
                </div>
                """, unsafe_allow_html=True)
            
            col_g1, col_g2 = st.columns(2)
            
            # Heatmap
            with col_g1:
                st.subheader("Failure Density (Day of Week vs Hour)")
                heatmap_data = data.get("heatmap", [])
                if heatmap_data and any(h.get("count", 0) > 0 for h in heatmap_data):
                    df_heat = pd.DataFrame(heatmap_data)
                    heat_pivot = df_heat.pivot(index="day", columns="hour", values="count").fillna(0)
                    
                    fig_heat = px.imshow(
                        heat_pivot,
                        labels=dict(x="Hour of Day (UTC)", y="Day of Week", color="Failures"),
                        color_continuous_scale="Reds"
                    )
                    st.plotly_chart(fig_heat, use_container_width=True)
                else:
                    st.info("Heatmap will populate as transactions are ingested across time windows.")
            
            # Trends
            with col_g2:
                st.subheader("Failures by Error Reason")
                reasons = data.get("failure_reasons", [])
                if reasons:
                    df_reasons = pd.DataFrame(reasons)
                    fig_pie = px.pie(
                        df_reasons, 
                        names="reason", 
                        values="count", 
                        hole=0.4,
                        title="Distribution of Error Reasons"
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("No failure distribution data available yet.")
        else:
            st.warning("Could not retrieve analytics data.")
    except Exception as e:
        st.error(f"Error loading insights: {e}")

# ==========================================
# TAB 6: AGENT AUDIT LOG
# ==========================================
with tab6:
    st.header("📝 Agent Decision Audit Log")
    st.write("Immutable log of every classification, strategy choice, safety gate check, and automated recovery action.")
    
    try:
        res = requests.get(f"{API_URL}/api/agent-decisions", timeout=5)
        if res.status_code == 200:
            decisions = res.json()
            if decisions:
                df_dec = pd.DataFrame(decisions)
                st.dataframe(
                    df_dec[["id", "transaction_id", "step", "input_data", "output_data", "created_at"]],
                    use_container_width=True,
                    column_config={
                        "step": st.column_config.TextColumn("Agent Step"),
                        "created_at": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm:ss")
                    }
                )
            else:
                st.info("No decisions logged yet.")
    except Exception as e:
        st.error(f"Could not load audit log: {e}")

if auto_refresh:
    time.sleep(10)
    st.rerun()

