import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import google.generativeai as genai
import json
from io import BytesIO
from PIL import Image
import os
import json

import gspread
from oauth2client.service_account import ServiceAccountCredentials

file_path = os.path.join(os.path.dirname(__file__), "questions_full.json")
with open(file_path, "r") as f:
    questions = json.load(f)

# --- CONFIGURATION ---
st.set_page_config(page_title="TAICC AI Readiness", layout="wide", page_icon="🤖")
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    st.secrets["gcp_service_account"], scope
)
client = gspread.authorize(creds)
sheet = client.open(st.secrets["SHEET_NAME"]).sheet1

# Score mapping
score_map = {
    "Not at all": 1,
    "Slightly": 2,
    "Moderately": 3,
    "Very": 4,
    "Fully": 5
}

# Readiness levels
readiness_levels = [
    (0, 1.0, "Beginner"),
    (1.1, 2.0, "Emerging"),
    (2.1, 3.0, "Established"),
    (3.1, 4.0, "Advanced"),
    (4.1, 5.0, "AI Leader")
]

# Extract domain and tier lists from JSON
domains = list(questions.keys())
tiers = list(next(iter(questions.values())).keys())

# --- SESSION STATE ---
if "page" not in st.session_state:
    st.session_state.page = "login"
    st.session_state.answers = {}
    st.session_state.section_scores = {}
    st.session_state.user_data = {}
    st.session_state.selected_domain = ""
    st.session_state.selected_tier = ""
    st.session_state.start_time = datetime.now()

# --- UI FUNCTIONS ---
def login_screen():
    st.image("https://i.postimg.cc/441ZWPjs/Whats-App-Image-2025-02-20-at-11-29-36.jpg", width=150)
    st.title("TAICC AI Readiness Assessment")
    st.markdown("Fill out your details to begin the assessment.")

    with st.form("user_details_form"):
        name = st.text_input("Full Name")
        company = st.text_input("Company Name")
        email = st.text_input("Email Address")
        phone = st.text_input("Phone Number")

        domain = st.selectbox("Select Your Domain", domains)
        tier = st.selectbox("Select Your Tier", tiers)

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
            st.session_state.page = "questions"

def question_screen():
    st.sidebar.title("TAICC")
    st.sidebar.markdown("AI Transformation Partner")
    st.title("AI Readiness Assessment")
    st.markdown("Rate your organization on these factors.")

    domain = st.session_state.selected_domain
    tier = st.session_state.selected_tier
    questions_for_tier = questions[domain][tier]

    answered = 0
    total_questions = len(questions_for_tier)

    for idx, q in enumerate(questions_for_tier):
        key = f"Q{idx}-{q}"
        val = st.radio(q, list(score_map.keys()), key=key)
        st.session_state.answers[key] = score_map[val]
        answered += 1

    progress = int((answered / total_questions) * 100)
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
    avg = list(st.session_state.section_scores.values())[0]
    maturity = determine_maturity(avg)

    prompt = f"""
    You are an expert AI consultant. Analyze this AI readiness score: {avg}.
    Provide a detailed professional report including:
    - Summary of current maturity level ({maturity})
    - Key weaknesses or challenges organizations at this level face
    - Practical recommendations for improvement
    - A concluding call to action encouraging to partner with TAICC for AI transformation support.
    """

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return maturity, response.text.strip()

def download_pdf(report_text, maturity):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "TAICC AI Readiness Assessment Report", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", size=12)
    pdf.cell(0, 8, "User Details:", ln=True)
    for k, v in st.session_state.user_data.items():
        pdf.cell(0, 8, f"{k}: {v}", ln=True)
    pdf.ln(5)

    pdf.cell(0, 8, f"AI Maturity Level: {maturity}", ln=True)
    pdf.ln(10)

    pdf.multi_cell(0, 8, report_text.encode('latin-1', 'replace').decode('latin-1'))
    pdf.ln(10)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, "Report generated by TAICC AI Readiness Assessment Tool", ln=True, align="C")

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

    # ✅ Save results to Google Sheets
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
            list(st.session_state.section_scores.values())[0],  # Overall Score
            maturity
        ]
        sheet.append_row(row)
        st.success("✅ Results saved to Google Sheets successfully!")
    except Exception as e:
        st.error(f"❌ Could not save to Google Sheets: {e}")

# --- ROUTER ---
if st.session_state.page == "login":
    login_screen()
elif st.session_state.page == "questions":
    question_screen()
elif st.session_state.page == "results":
    results_screen()
