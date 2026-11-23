import time
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from pypdf import PdfReader

st.set_page_config(page_title="SkyMPSC & SAAM AI", page_icon="🤖", layout="centered")

# --- डेटा स्ट्रक्चर (MPSC टेस्ट के लिए) ---
class OptionDetail(BaseModel):
    text: str = Field(description="विकल्प का टेक्स्ट")
    explanation: str = Field(description="यह विकल्प सही या गलत क्यों है, इसकी संक्षिप्त व्याख्या")

class QuestionItem(BaseModel):
    question: str = Field(description="MPSC पैटर्न का प्रश्न (विधान अ, ब, क शैली में)")
    options: list[OptionDetail] = Field(description="ठीक 4 विकल्प")
    correct_index: int = Field(description="सही विकल्प का इंडेक्स (0, 1, 2, या 3)")

class MPSCTest(BaseModel):
    questions: list[QuestionItem]

# --- मेमोरी और सेशन स्टेट (SAAM के सीखने और याद रखने के लिए) ---
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "saam_messages" not in st.session_state:
    st.session_state.saam_messages = [
        {
            "role": "assistant",
            "content": "नमस्कार! मैं **SAAM** हूँ—आपका पर्सनल AI असिस्टेंट। आप मुझसे मराठी, हिंदी या English में बिल्कुल एक दोस्त की तरह बात कर सकते हैं। बताइए, आज मैं आपके लिए क्या करूँ? (जैसे: नई सरकारी भर्ती खोजें, मेरा टाइमटेबल बनाएं, या किसी विषय पर चर्चा करें)"
        }
    ]
if "saam_memory" not in st.session_state:
    st.session_state.saam_memory = []
if "tasks" not in st.session_state:
    st.session_state.tasks = []

# --- हेडर और API Key ---
st.title("🚀 SkyMPSC & SAAM AI")
api_key = st.text_input("🔑 अपनी Gemini API Key डालें:", type="password")

# --- दो मुख्य टैब: MPSC टेस्ट और SAAM असिस्टेंट ---
tab1, tab2 = st.tabs(["📚 MPSC AI Tutor", "🤖 SAAM (पर्सनल असिस्टेंट & जॉब अलर्ट)"])

# ==========================================
# TAB 1: MPSC AI TUTOR
# ==========================================
with tab1:
    uploaded_files = st.file_uploader(
        "📄 पुराने प्रश्नपत्र या नोट्स की PDF अपलोड करें (वैकल्पिक)",
        type=["pdf"],
        accept_multiple_files=True,
    )

    exam_type = st.selectbox(
        "परीक्षा चुनें:",
        ["MPSC Rajyaseva (राज्यसेवा)", "MPSC Combine Group B & C (संयुक्त गट ब व क)", "MPSC Technical / Engineering"],
    )

    subject = st.text_input(
        "विषय / टॉपिक (जैसे: महाराष्ट्राचा इतिहास, राज्यघटना, चालू घडामोडी):",
        value="भारतीय राज्यघटना (Indian Polity)",
    )

    question_mode = st.radio(
        "प्रश्नों का प्रकार:",
        [
            "PYQ पैटर्न + नए संभावित प्रश्न (Expected Questions)",
            "सिर्फ अपलोड किए गए PYQ पेपर्स पर आधारित",
            "लाइव चालू घडामोडी (Current Affairs & GK)",
        ],
    )

    language = st.selectbox("भाषा चुनें:", ["मराठी (Marathi)", "हिंदी (Hindi)", "English"])
    num_questions = st.slider("प्रश्नों की संख्या:", min_value=1, max_value=10, value=3)

    if st.button("🚀 नया टेस्ट शुरू करें", type="primary", use_container_width=True):
        if not api_key:
            st.warning("⚠️ कृपया सबसे ऊपर अपनी Gemini API Key डालें और Enter दबाएं।")
        else:
            with st.spinner("AI आपके लिए MPSC पैटर्न के प्रश्न तैयार कर रहा है..."):
                try:
                    pyq_context = ""
                    if uploaded_files:
                        for f in uploaded_files:
                            reader = PdfReader(f)
                            for page in reader.pages[:8]:
                                pyq_context += (page.extract_text() or "") + "\n"
                        pyq_context = pyq_context[:12000]

                    prompt = f"""तुम एक अनुभवी MPSC (Maharashtra Public Service Commission) शिक्षक हो।
परीक्षा: {exam_type}
विषय: {subject}
प्रश्नों का प्रकार: {question_mode}
भाषा: {language}
प्रश्नों की संख्या: {num_questions}

निर्देश:
1. यदि नीचे PYQ Context दिया है, तो उसके स्तर और पैटर्न का उपयोग करो।
2. MPSC की असली शैली के अनुसार 'विधान अ, ब, क' वाले विश्लेषणात्मक प्रश्न बनाओ।
3. कुल {num_questions} प्रश्न बनाओ और हर प्रश्न के ठीक 4 विकल्प दो।
4. हर ऑप्शन (सही और गलत दोनों) की संक्षिप्त व्याख्या दो।
5. पूरा आउटपुट {language} भाषा में लिखो।

PYQ Context:
{pyq_context if pyq_context else "कोई PDF अपलोड नहीं की गई है।"}
"""
                    client = genai.Client(api_key=api_key.strip())
                    response = None
                    last_error = None

                    for model_name in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]:
                        for attempt in range(2):
                            try:
                                response = client.models.generate_content(
                                    model=model_name,
                                    contents=prompt,
                                    config=types.GenerateContentConfig(
                                        response_mime_type="application/json",
                                        response_schema=MPSCTest,
                                        temperature=0.4,
                                    ),
                                )
                                break
                            except Exception as err:
                                last_error = err
                                if "503" in str(err) or "UNAVAILABLE" in str(err):
                                    time.sleep(3)
                                    continue
                                break
                        if response is not None:
                            break

                    if response is None:
                        raise last_error

                    st.session_state.quiz_data = MPSCTest.model_validate_json(response.text)
                    st.rerun()

                except Exception as e:
                    st.error(f"समस्या आई: {e}")

    if st.session_state.quiz_data:
        st.divider()
        questions = st.session_state.quiz_data.questions
        correct_count = 0

        for idx, q in enumerate(questions):
            st.subheader(f"प्रश्न {idx + 1}")
            st.write(q.question)

            option_labels = [opt.text for opt in q.options]
            choice = st.radio(
                f"अपना उत्तर चुनें (प्रश्न {idx + 1}):",
                option_labels,
                index=None,
                key=f"q_{idx}",
            )

            if choice is not None:
                selected_idx = option_labels.index(choice)
                if selected_idx == q.correct_index:
                    st.success("✅ सही उत्तर!")
                    correct_count += 1
                else:
                    st.error(f"❌ गलत उत्तर! सही विकल्प है: {option_labels[q.correct_index]}")

                with st.expander("📖 सभी विकल्पों का स्पष्टीकरण देखें", expanded=True):
                    for o_idx, opt in enumerate(q.options):
                        mark = "✔️" if o_idx == q.correct_index else "✖️"
                        st.markdown(f"**{mark} {opt.text}:** {opt.explanation}")

            st.divider()

        st.info(f"📊 वर्तमान स्कोर: **{correct_count} / {len(questions)}**")

# ==========================================
# TAB 2: SAAM (PERSONAL AI ASSISTANT)
# ==========================================
with tab2:
    st.subheader("🤖 SAAM — आपका स्मार्ट सहायक")
    
    # त्वरित जॉब अलर्ट और काम के बटन
    col1, col2 = st.columns(2)
    with col1:
        check_jobs = st.button("🔔 नई सरकारी भर्ती (Gov Vacancy) चेक करें", use_container_width=True)
    with col2:
        clear_chat = st.button("🧹 नई बातचीत शुरू करें", use_container_width=True)

    if clear_chat:
        st.session_state.saam_messages = [st.session_state.saam_messages[0]]
        st.rerun()

    # यूज़र की यादें / पसंद दिखाना (जो SAAM ने सीखा है)
    with st.expander("🧠 SAAM की मेमोरी और आपके काम (To-Do List)"):
        new_task = st.text_input("कोई नया काम या रिमाइंडर जोड़ें:")
        if st.button("➕ जोड़ें") and new_task:
            st.session_state.tasks.append(new_task)
            st.session_state.saam_memory.append(f"यूज़र का काम: {new_task}")
            st.success("काम जोड़ दिया गया!")
        if st.session_state.tasks:
            for t in st.session_state.tasks:
                st.write(f"• {t}")
        else:
            st.caption("अभी कोई काम नहीं जोड़ा गया है।")

    # पुरानी बातचीत दिखाएं
    for msg in st.session_state.saam_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # यूज़र का नया संदेश या जॉब अलर्ट बटन
    user_prompt = st.chat_input("SAAM से कुछ भी कहें या पूछें...")
    if check_jobs:
        user_prompt = "आज की तारीख तक महाराष्ट्र (MPSC, महाभरती) और केंद्र सरकार (SSC, UPSC, Banking) की सबसे नई और ताज़ा सरकारी नौकरी (Government Vacancies) की पूरी लिस्ट, अंतिम तारीख और योग्यता बताओ।"

    if user_prompt:
        if not api_key:
            st.warning("⚠️ कृपया ऊपर अपनी Gemini API Key डालें।")
        else:
            st.session_state.saam_messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                with st.spinner("SAAM सोच रहा है और जानकारी ढूंढ रहा है..."):
                    try:
                        client = genai.Client(api_key=api_key.strip())
                        
                        # SAAM का इंसानी व्यवहार और सीखने वाला व्यक्तित्व
                        memory_text = "\n".join(st.session_state.saam_memory[-10:])
                        system_instruction = f"""तुम्हारा नाम SAAM है। तुम यूज़र के सबसे भरोसेमंद, समझदार और इंसानों की तरह बात करने वाले पर्सनल AI असिस्टेंट हो।
तुम्हारे नियम:
1. यूज़र जिस भाषा और लहजे (मराठी, हिंदी, Hinglish या English) में बात करे, तुम भी बिल्कुल उसी दोस्ताना और स्वाभाविक (Human-like) अंदाज़ में जवाब दो।
2. यूज़र की पसंद, व्यवहार और पिछली बातों को ध्यान में रखकर खुद को ढालते रहो।
