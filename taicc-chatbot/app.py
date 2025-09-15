import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import google.generativeai as genai
import json
from io import BytesIO
from PIL import Image
import os
import requests
import streamlit.components.v1 as components
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import razorpay

# Razorpay Test Credentials
RAZORPAY_KEY_ID = "rzp_test_RGEMU8juHeSLYL"
RAZORPAY_KEY_SECRET = "WseFgOL3r58nxWdv6g2dyOQa"

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def create_order(amount=199):
    order = razorpay_client.order.create({
        "amount": amount * 100,  # Razorpay expects paise
        "currency": "INR",
        "payment_capture": 1
    })
    return order

# -----------------------------
# --- CONFIGURATION & SETUP ---
# -----------------------------
# Load questions JSON
file_path = os.path.join(os.path.dirname(__file__), "questions_full.json")
with open(file_path, "r") as f:
    questions = json.load(f)

# Streamlit page config
st.set_page_config(page_title="TAICC AI Readiness", layout="wide")
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Score mapping and readiness levels
score_map = {"Not at all": 1, "Slightly": 2, "Moderately": 3, "Very": 4, "Fully": 5}
readiness_levels = [
    (0, 1.0, "Beginner"),
    (1.1, 2.0, "Emerging"),
    (2.1, 3.0, "Established"),
    (3.1, 4.0, "Advanced"),
    (4.1, 5.0, "AI Leader")
]

# Extract domains and tiers from JSON
domains = list(questions.keys())
tiers = list(next(iter(questions.values())).keys())  # assumes all domains have same tiers

# Domain and Tier explanations
domain_explanations = {
    "BFSI": "Banking, Financial Services, and Insurance including NBFCs, Co-op Banks, Stock Broking, and more.",
    "Manufacturing": "Industries such as Automobiles, Textiles, and Machinery.",
    "Healthcare": "Hospitals, diagnostics, health-tech platforms, and telemedicine.",
    "Hospitality": "Hotels, resorts, restaurants, and travel accommodations.",
    "Pharma": "Pharmaceutical research, biotech, and medicine production.",
    "Travel and Tourism": "Tour operators, online travel platforms, airlines, etc.",
    "Construction": "Infrastructure, civil engineering, and public works.",
    "Real Estate": "Residential and commercial property development and sales.",
    "Education & EdTech": "Schools, universities, online learning platforms.",
    "Retail & E-commerce": "Retail chains, marketplaces, and D2C brands.",
    "Logistics & Supply Chain": "Warehousing, distribution, and delivery services.",
    "Agritech": "Smart farming, agri-inputs, and precision agriculture.",
    "IT & ITES": "Software companies, IT services, and BPOs.",
    "Legal & Compliance": "Law firms, compliance tools, and contract automation.",
    "Energy & Utilities": "Power generation, oil & gas, renewables.",
    "Telecommunications": "Network providers, internet services, and 5G tech.",
    "Media & Entertainment": "Broadcasting, streaming platforms, and gaming.",
    "PropTech": "Real estate technology platforms.",
    "FMCG & Consumer Goods": "Packaged goods and fast-moving consumer brands.",
    "Public Sector": "Government departments, PSUs, and public welfare.",
    "Automotive": "OEMs, auto ancillaries, and connected vehicles.",
    "Environmental & Sustainability": "Climate tech, carbon tracking, and ESG.",
    "Smart Cities": "Urban tech, IoT infrastructure, and city planning."
}

tier_explanations = {
    "Tier 1": "Enterprise Leaders – Large organizations with significant AI investments and robust strategies.",
    "Tier 2": "Strategic Innovators – Established companies actively experimenting and implementing AI.",
    "Tier 3": "Growth Enablers – Mid-sized firms beginning structured AI adoption efforts.",
    "Tier 4": "Agile Starters – Startups or small businesses with a high willingness to explore AI.",
    "Tier 5": "Traditional Operators – Individuals or firms with minimal or no current AI engagement."
}

# -----------------------------
# --- GOOGLE SHEETS SETUP ---
# -----------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)
sheet = client.open(st.secrets["SHEET_NAME"]).sheet1

# -----------------------------
# --- SESSION STATE SETUP ---
# -----------------------------
if "page" not in st.session_state:
    st.session_state.page = "login"
    st.session_state.answers = {}
    st.session_state.section_scores = {}
    st.session_state.user_data = {}
    st.session_state.selected_domain = ""
    st.session_state.selected_tier = ""
    st.session_state.start_time = datetime.now()
    st.session_state.paid = False  # <-- NEW: track if user has paid

# -----------------------------
# --- PAYMENT FUNCTION ---
# -----------------------------
import streamlit.components.v1 as components

import streamlit.components.v1 as components

def payment_screen():
    import streamlit.components.v1 as components

    st.subheader("💳 Payment Required")
    st.write("Please complete the payment of **₹199** to continue to the assessment.")

    # Order creation: safe for reloads
    if "order_id" not in st.session_state:
        order = razorpay_client.order.create({
            "amount": 19900,
            "currency": "INR",
            "payment_capture": 1
        })
        st.session_state["order_id"] = order["id"]
        st.session_state["order_amount"] = order["amount"]

    # Payment widget
    payment_html = f"""<html>
    <head>
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script></head>
    <body>
    <script>
        var options = {{
            "key": "{RAZORPAY_KEY_ID}",
            "amount": "{st.session_state['order_amount']}",
            "currency": "INR",
            "name": "TAICC Partners",
            "description": "AI Readiness Assessment",
            "order_id": "{st.session_state['order_id']}",
            "theme": {{ "color": "#3399cc" }},
            "handler": function (response) {{
                window.parent.postMessage({{
                    "razorpay_payment_id": response.razorpay_payment_id,
                    "razorpay_order_id": response.razorpay_order_id,
                    "razorpay_signature": response.razorpay_signature
                }}, "*");
            }},
            "method": {{
                "upi": true,"card": true, "netbanking": true, "wallet": true
            }}
        }};
        var rzp1 = new Razorpay(options);
        rzp1.open();
    </script></body></html>
    """
    components.html(payment_html, height=650)

    # JS for communicating with Streamlit
    success_js = """
<script>
window.addEventListener("message", (event) => {
    if (event.data && event.data.razorpay_payment_id) {
        const url = new URL(window.location.href);
        url.searchParams.set("payment_id", event.data.razorpay_payment_id);
        url.searchParams.set("order_id", event.data.razorpay_order_id);
        url.searchParams.set("signature", event.data.razorpay_signature);
        url.searchParams.set("page", "questions");  // <<< This tells the app to go to questions page
        window.location.replace(url.toString());
    }
});
</script>
"""
st.markdown(success_js, unsafe_allow_html=True)

    # Read payment query params
    params = st.query_params
    paid = False
    if "payment_id" in params and "order_id" in params and "signature" in params:
        payment_id = params.get("payment_id", [""])
        order_id = params.get("order_id", [""])
        signature = params.get("signature", [""])
        try:
            razorpay_client.utility.verify_payment_signature({
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature
            })
            paid = True
            st.success("✅ Payment verified successfully! Redirecting to assessment ...")
            # Only set state and rerun here—ignore old session state
            st.session_state.paid = True
            st.session_state.page = "questions"
            st.experimental_rerun()  # st.rerun() also works
        except Exception as ex:
            st.error("❌ Payment verification failed. Please try again or contact support.")
            st.write(str(ex))

    # Display payment UI if not paid
    if not paid: 
        st.info("Awaiting payment completion ...")

# After Razorpay widget code inside payment_screen():

params = st.experimental_get_query_params()  # safer form of st.query_params
current_page = params.get("page", ["payment"])[0]  # default 'payment'

if "payment_id" in params and "order_id" in params and "signature" in params:
    payment_id = params["payment_id"][0]
    order_id = params["order_id"][0]
    signature = params["signature"][0]

    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature
        })
        st.success("✅ Payment verified successfully! Redirecting...")

        # Show manual continue link for safety
        st.markdown(f"[Continue to Assessment]({st.experimental_get_query_params().get('page', ['questions'])[0]})")

        return  # stop showing payment screen

    except Exception as ex:
        st.error(f"❌ Payment verification failed: {ex}")
else:
    # Show payment widget only if still on payment page
    if current_page != "questions":
        components.html(payment_html, height=650)
    else:
        st.success("Payment successful! Please continue to the assessment.")


# -----------------------------
# --- UI FUNCTIONS ---
# -----------------------------
def login_screen():
    st.image("https://i.postimg.cc/441ZWPjs/Whats-App-Image-2025-02-20-at-11-29-36.jpg", width=150)
    st.title("TAICC AI Readiness Assessment")
    st.markdown("Fill out your details to begin the assessment.")

    with st.form("user_details_form"):
        name = st.text_input("Full Name")
        company = st.text_input("Company Name")
        email = st.text_input("Email Address")
        phone = st.text_input("Phone Number")

        domain = st.selectbox("Select Your Domain", domains, format_func=lambda x: f"{x} - {domain_explanations.get(x, '')}")
        tier = st.selectbox("Select Your Tier", tiers, format_func=lambda x: f"{x} - {tier_explanations.get(x, '')}")

        submitted = st.form_submit_button("Start Assessment")

        if submitted:
            st.session_state.user_data = {
                "Name": name,
                "Company": company,
                "Email": email,
                "Phone": phone
            }
            st.session_state.selected_domain = domain
            st.session_state.selected_tier = tier
            st.session_state.page = "payment"


def question_screen():
    st.sidebar.title("TAICC")
    st.sidebar.markdown("AI Transformation Partner")
    st.title("AI Readiness Assessment")
    st.markdown("Rate your organization on these factors.")

    domain = st.session_state.selected_domain
    tier = st.session_state.selected_tier
    questions_for_tier = questions[domain][tier]

    for idx, q in enumerate(questions_for_tier):
        key = f"Q{idx}-{q}"
        val = st.radio(q, list(score_map.keys()), key=key)
        st.session_state.answers[key] = score_map[val]

    progress = int(len(st.session_state.answers) / len(questions_for_tier) * 100)
    st.progress(progress)

    if st.button("Submit"):
        st.session_state.page = "results"


def calculate_scores():
    values = list(st.session_state.answers.values())
    avg = round(sum(values) / len(values), 2)
    st.session_state.section_scores = {"Overall Score": avg}


def determine_maturity(avg):
    for low, high, label in readiness_levels:
        if low <= avg <= high:
            return label
    return "Undefined"


def generate_professional_summary():
    avg_score = list(st.session_state.section_scores.values())[0]
    maturity = determine_maturity(avg_score)
    
    user = st.session_state.user_data
    client_name = user.get("Name", "[Client Name]")
    company_name = user.get("Company", "[Company Name]")
    
    prompt = f"""
    You are an expert AI consultant. Create a professional AI readiness report for:
    Client: {client_name}
    Company: {company_name}
    AI Score: {avg_score} ({maturity})
    
    Include the following sections in clear, business-report style:
    1. Executive Summary
    2. Current Maturity Level
    3. Key Weaknesses and Challenges
    4. Recommendations for Improvement
    5. Conclusion and Call to Action

    Make it concise, professional, and ready to be included in a PDF report. Use bullet points for challenges and recommendations where appropriate.
    """
    
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    report_text = response.text.strip()
    
    # Optionally, prepend user details to the report
    report_text = f"Client: {client_name}\nCompany: {company_name}\nEmail: {user.get('Email','')}\nPhone: {user.get('Phone','')}\n\n{report_text}"
    
    return maturity, report_text


def download_pdf(report_text, maturity):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --- Logo at the top ---
    logo_url = "https://i.postimg.cc/441ZWPjs/Whats-App-Image-2025-02-20-at-11-29-36.jpg"  # replace with your logo URL
    response = requests.get(logo_url)
    logo_image = Image.open(BytesIO(response.content))
    logo_path = "temp_logo.png"
    logo_image.save(logo_path)
    pdf.image(logo_path, x=10, y=8, w=40)

    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "TAICC AI Readiness Assessment Report", ln=True, align="C")
    pdf.ln(15)

    # --- Watermark ---
    watermark = logo_image.convert("RGBA").resize((100, 100))
    alpha = watermark.split()[3].point(lambda p: p * 0.1)  # 10% opacity
    watermark.putalpha(alpha)
    watermark.save("temp_watermark.png")
    pdf.image("temp_watermark.png", x=60, y=100, w=90)

    # --- User Details ---
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, "User Details:", ln=True)
    for k, v in st.session_state.user_data.items():
        pdf.cell(0, 8, f"{k}: {v}", ln=True)
    pdf.ln(5)

    pdf.cell(0, 8, f"AI Maturity Level: {maturity}", ln=True)
    pdf.ln(10)

    # --- Report Text ---
    pdf.multi_cell(0, 8, report_text.encode('latin-1', 'replace').decode('latin-1'))

    # --- Footer ---
    pdf.ln(10)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, "Report generated by TAICC AI Readiness Assessment Tool", ln=True, align="C")

    # --- Download Button ---
    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    st.download_button(
        label="Download Full Professional Report (PDF)",
        data=pdf_bytes,
        file_name="TAICC_AI_Readiness_Report.pdf",
        mime="application/pdf"
    )


def show_maturity_levels():
    st.markdown("### AI Maturity Levels Explained")
    df_levels = pd.DataFrame([
        {"Score Range": "0.0 - 1.0", "Level": "Beginner", "Description": "Just starting AI journey, minimal awareness."},
        {"Score Range": "1.1 - 2.0", "Level": "Emerging", "Description": "Early experiments, limited AI integration."},
        {"Score Range": "2.1 - 3.0", "Level": "Established", "Description": "Defined AI strategy, some successful projects."},
        {"Score Range": "3.1 - 4.0", "Level": "Advanced", "Description": "Mature AI adoption, integrated into processes."},
        {"Score Range": "4.1 - 5.0", "Level": "AI Leader", "Description": "Industry-leading AI innovation and scale."},
    ])
    st.table(df_levels)


def results_screen():
    calculate_scores()
    st.title("📊 AI Readiness Assessment Results")
    df = pd.DataFrame(list(st.session_state.section_scores.items()), columns=["Section", "Score"])
    st.bar_chart(df.set_index("Section"))

    maturity, detailed_report = generate_professional_summary()
    st.success(f"Your AI Maturity Level: **{maturity}**")
    st.markdown(detailed_report)

    show_maturity_levels()
    time_taken = datetime.now() - st.session_state.start_time
    st.caption(f"⏱️ Time taken: {time_taken.seconds // 60} min {time_taken.seconds % 60} sec")

    download_pdf(detailed_report, maturity)

    # -----------------------------
    # --- SAVE TO GOOGLE SHEETS ---
    # -----------------------------
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [
            now,
            st.session_state.user_data.get("Name", ""),
            st.session_state.user_data.get("Company", ""),
            st.session_state.user_data.get("Email", ""),
            st.session_state.user_data.get("Phone", ""),
            st.session_state.selected_domain,
            st.session_state.selected_tier,
            list(st.session_state.section_scores.values())[0],
            maturity
        ]
        sheet.append_row(row)
        st.success("✅ Results saved to Google Sheets successfully!")
    except Exception as e:
        st.error(f"❌ Could not save to Google Sheets: {e}")

# -----------------------------
# --- ROUTER ---
# -----------------------------

def main_router():
    params = st.experimental_get_query_params()
    page = params.get("page", ["login"])[0]

    if page == "login":
        login_screen()
    elif page == "payment":
        payment_screen()
    elif page == "questions":
        question_screen()
    elif page == "results":
        results_screen()
    else:
        st.write("Unknown page; showing login.")
        login_screen()

if __name__ == "__main__":
    main_router()

