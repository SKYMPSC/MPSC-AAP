import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import pypdf

st.set_page_config(page_title="SkyMPSC AI Tutor", page_icon="📚", layout="centered")

class OptionDetail(BaseModel):
    option_text: str = Field(description="ऑप्शन का पूरा टेक्स्ट (जैसे: अ) केवल अ और ब)")
    is_correct: bool = Field(description="क्या यह ऑप्शन सही है? (True/False)")
    reason: str = Field(description="यह ऑप्शन क्यों सही है या किस हिसाब से गलत है, इसका स्पष्टीकरण")

class MPSCQuestion(BaseModel):
    question_text: str = Field(description="MPSC PYQ पैटर्न का प्रश्न (मल्टी-स्टेटमेंट या फैक्चुअल)")
    pyq_reference: str = Field(description="यह प्रश्न किस परीक्षा/वर्ष के PYQ पैटर्न या संभावित टॉपिक पर आधारित है")
    options: list[OptionDetail] = Field(description="कुल 4 ऑप्शंस की लिस्ट")
    overall_concept: str = Field(description="इस प्रश्न के पीछे का मुख्य कॉन्सेप्ट और परीक्षा के लिए टिप")

class MPSCTest(BaseModel):
    questions: list[MPSCQuestion]

def extract_text_from_pdfs(uploaded_files):
    combined_text = ""
    for file in uploaded_files:
        reader = pypdf.PdfReader(file)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                combined_text += text + "\n"
    return combined_text[:150000]

st.title("🎓 SkyMPSC AI Personal Tutor")
st.caption("PYQ पैटर्न टेस्ट, संभावित प्रश्न, लाइव GK और विस्तृत स्पष्टीकरण")

with st.expander("⚙️ 1. सेटिंग्स और PYQ पेपर्स अपलोड करें", expanded=True):
    api_key = st.text_input("अपनी Gemini API Key डालें:", type="password")
    uploaded_pdfs = st.file_uploader(
        "MPSC के पुराने प्रश्नपत्र (PDF) अपलोड करें (वैकल्पिक):",
        type=["pdf"],
        accept_multiple_files=True
    )
    if uploaded_pdfs:
        st.success(f"{len(uploaded_pdfs)} PDF फाइलें लोड हो गई हैं!")

    exam_type = st.selectbox("परीक्षा चुनें:", [
        "MPSC Rajyaseva (राज्यसेवा)",
        "MPSC Combine Group B & C (संयुक्त पूर्व परीक्षा)",
        "MPSC Technical / Other Exams"
    ])
    subject = st.text_input("विषय / टॉपिक (जैसे: महाराष्ट्राचा इतिहास, राज्यघटना, चालू घडामोडी):", value="भारतीय राज्यघटना (Indian Polity)")
    question_mode = st.radio("प्रश्नों का प्रकार:", [
        "PYQ पैटर्न + नए संभावित प्रश्न (Expected Questions)",
        "सिर्फ अपलोड किए गए PYQ पेपर्स पर आधारित",
        "लाइव चालू घडामोडी (Current Affairs & GK)"
    ])
    language = st.selectbox("भाषा चुनें:", ["मराठी (Marathi)", "हिंदी (Hindi)", "English"])
    num_questions = st.slider("प्रश्नों की संख्या:", min_value=3, max_value=15, value=5)

if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}

if st.button("🚀 नया टेस्ट शुरू करें", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ कृपया ऊपर सेटिंग्स में अपनी Gemini API Key डालें।")
    else:
        with st.spinner("AI आपके लिए MPSC पैटर्न के प्रश्न तैयार कर रहा है..."):
            try:
                client = genai.Client(api_key=api_key)
                pyq_context = extract_text_from_pdfs(uploaded_pdfs) if uploaded_pdfs else ""

                prompt = f"""
                तुम एक अनुभवी MPSC (Maharashtra Public Service Commission) शिक्षक और पेपर सेटर हो।
                परीक्षा: {exam_type}
                विषय: {subject}
                प्रश्नों का प्रकार: {question_mode}
                भाषा: {language}
                प्रश्नों की संख्या: {num_questions}

                निर्देश:
                1. यदि नीचे PYQ Context दिया है, तो उसके स्तर और पैटर्न का गहराई से उपयोग करो। साथ ही अपने ज्ञान से MPSC के पिछले वर्षों के पैटर्न के आधार पर नए संभावित (Expected) और कठिन प्रश्न भी बनाओ।
                2. MPSC की असली शैली के अनुसार 'विधान अ, ब, क' (Multi-statement), 'जोड्या जुळवा', और वैचारिक (Analytical) प्रश्न बनाओ।
                3. कुल {num_questions} प्रश्न बनाओ और हर प्रश्न के 4 ऑप्शन दो।
                4. सबसे ज़रूरी: हर ऑप्शन (सही और गलत दोनों) के लिए स्पष्ट कारण (reason) लिखो कि वह ऑप्शन सही क्यों है और बाकी गलत ऑप्शन किस तथ्य के कारण गलत हैं।
                5. पूरा आउटपुट {language} भाषा में लिखो।

                PYQ Context:
                {pyq_context if pyq_context else "कोई PDF अपलोड नहीं है, वास्तविक MPSC PYQ पैटर्न और लाइव सामान्य ज्ञान का उपयोग करें।"}
                """

                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=MPSCTest,
                        temperature=0.4,
                    ),
                )

                st.session_state.quiz_data = MPSCTest.model_validate_json(response.text)
                st.session_state.user_answers = {}
                st.rerun()

            except Exception as e:
                st.error(f"समस्या आई: {e}")

if st.session_state.quiz_data:
    st.divider()
    questions = st.session_state.quiz_data.questions
    correct_count = 0

    for idx, q in enumerate(questions):
        st.subheader(f"प्रश्न {idx + 1}")
        st.caption(f"📌 पैटर्न/संदर्भ: {q.pyq_reference}")
        st.markdown(f"**{q.question_text}**")

        option_texts = [opt.option_text for opt in q.options]
        selected_option = st.radio(
            f"उत्तर चुनें (प्रश्न {idx + 1}):",
            options=option_texts,
            index=None,
            key=f"radio_{idx}"
        )

        if selected_option is not None:
            st.session_state.user_answers[idx] = selected_option
            chosen_opt = next(opt for opt in q.options if opt.option_text == selected_option)
            correct_opt = next(opt for opt in q.options if opt.is_correct)

            if chosen_opt.is_correct:
                correct_count += 1
                st.success("✅ **सही जवाब!**")
            else:
                st.error(f"❌ **गलत जवाब!** आपने चुना: *{selected_option}*")
                st.info(f"✔️ **सही जवाब:** {correct_opt.option_text}")

            with st.expander("📖 पूरा स्पष्टीकरण देखें (सही और गलत क्यों है)", expanded=True):
                st.markdown(f"**💡 मुख्य कॉन्सेप्ट:** {q.overall_concept}")
                st.markdown("---")
                for opt in q.options:
                    if opt.is_correct:
                        st.markdown(f"🟢 **{opt.option_text}** — *(सही क्यों है)*: {opt.reason}")
                    else:
                        st.markdown(f"🔴 **{opt.option_text}** — *(गलत क्यों है)*: {opt.reason}")

        st.divider()

    if len(st.session_state.user_answers) > 0:
        st.success(f"📊 **आपका स्कोर:** {correct_count} / {len(questions)} सही")
