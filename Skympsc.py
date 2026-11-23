import time
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from pypdf import PdfReader

st.set_page_config(page_title="SkyMPSC & SAAM AI", page_icon="📚", layout="centered")

class OptionDetail(BaseModel):
    text: str = Field(description="विकल्प का टेक्स्ट")
    explanation: str = Field(description="यह विकल्प सही या गलत क्यों है, इसकी संक्षिप्त व्याख्या")

class QuestionItem(BaseModel):
    question: str = Field(description="MPSC पैटर्न का प्रश्न (विधान अ, ब, क शैली में)")
    options: list[OptionDetail] = Field(description="ठीक 4 विकल्प")
    correct_index: int = Field(description="सही विकल्प का इंडेक्स (0, 1, 2, या 3)")

class MPSCTest(BaseModel):
    questions: list[QuestionItem]

def generate_with_fallback(client, contents, config=None):
    last_error = None
    for model_name in ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]:
        for _ in range(2):
            try:
                return client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
            except Exception as err:
                last_error = err
                if "503" in str(err) or "UNAVAILABLE" in str(err):
                    time.sleep(3)
                    continue
                break
    raise last_error

st.title("📚 SkyMPSC & SAAM AI")
st.caption("MPSC परीक्षा तैयारी, सरकारी भर्ती अपडेट्स और आपका पर्सनल असिस्टेंट SAAM")

api_key = st.text_input("🔑 अपनी Gemini API Key डालें:", type="password")

tab1, tab2, tab3 = st.tabs(["📝 MPSC टेस्ट", "🤖 SAAM असिस्टेंट", "📢 सरकारी भर्ती अलर्ट"])

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
        "विषय / टॉपिक:",
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

    if "quiz_data" not in st.session_state:
        st.session_state.quiz_data = None

    if st.button("🚀 नया टेस्ट शुरू करें", type="primary", use_container_width=True):
        if not api_key:
            st.warning("⚠️ कृपया ऊपर अपनी Gemini API Key डालें और Enter दबाएं।")
        else:
            with st.spinner("AI प्रश्न तैयार कर रहा है..."):
                try:
                    pyq_context = ""
                    if uploaded_files:
                        for f in uploaded_files:
                            reader = PdfReader(f)
                            for page in reader.pages[:8]:
                                pyq_context += (page.extract_text() or "") + "\n"
                        pyq_context = pyq_context[:12000]

                    prompt = (
                        f"तुम एक अनुभवी MPSC शिक्षक हो। परीक्षा: {exam_type}, विषय: {subject}, "
                        f"प्रकार: {question_mode}, भाषा: {language}, प्रश्नों की संख्या: {num_questions}। "
                        f"MPSC की शैली के अनुसार 'विधान अ, ब, क' वाले विश्लेषणात्मक प्रश्न बनाओ। "
                        f"हर प्रश्न के ठीक 4 विकल्प दो और हर विकल्प की संक्षिप्त व्याख्या {language} भाषा में लिखो। "
                        f"PYQ संदर्भ: {pyq_context if pyq_context else 'कोई PDF नहीं दी गई है।'}"
                    )

                    client = genai.Client(api_key=api_key.strip())
                    config = types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=MPSCTest,
                        temperature=0.4,
                    )
                    response = generate_with_fallback(client, prompt, config)
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
            choice = st.radio(f"उत्तर चुनें (प्रश्न {idx + 1}):", option_labels, index=None, key=f"q_{idx}")
            if choice is not None:
                selected_idx = option_labels.index(choice)
                if selected_idx == q.correct_index:
                    st.success("✅ सही उत्तर!")
                    correct_count += 1
                else:
                    st.error(f"❌ गलत उत्तर! सही विकल्प: {option_labels[q.correct_index]}")
                with st.expander("📖 सभी विकल्पों का स्पष्टीकरण", expanded=True):
                    for o_idx, opt in enumerate(q.options):
                        mark = "✔️" if o_idx == q.correct_index else "✖️"
                        st.markdown(f"**{mark} {opt.text}:** {opt.explanation}")
            st.divider()
        st.info(f"📊 वर्तमान स्कोर: **{correct_count} / {len(questions)}**")

with tab2:
    st.subheader("🤖 SAAM - आपका पर्सनल असिस्टेंट")
    if "saam_messages" not in st.session_state:
        st.session_state.saam_messages = [
            {"role": "assistant", "content": "नमस्ते! मैं SAAM हूँ। आज मैं आपकी पढ़ाई, प्लानिंग या किसी भी काम में कैसे मदद कर सकता हूँ?"}
        ]

    for msg in st.session_state.saam_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_msg = st.chat_input("SAAM से कुछ भी पूछें या काम बताएं...")
    if user_msg:
        if not api_key:
            st.warning("⚠️ कृपया सबसे ऊपर अपनी Gemini API Key डालें।")
        else:
            st.session_state.saam_messages.append({"role": "user", "content": user_msg})
            with st.chat_message("user"):
                st.write(user_msg)

            with st.chat_message("assistant"):
                with st.spinner("SAAM सोच रहा है..."):
                    try:
                        client = genai.Client(api_key=api_key.strip())
                        history_text = "\n".join(
                            [f"{m['role']}: {m['content']}" for m in st.session_state.saam_messages[-8:]]
                        )
                        saam_prompt = (
                            "तुम्हारा नाम SAAM है। तुम एक समझदार, दोस्ताना और मददगार पर्सनल AI असिस्टेंट हो। "
                            "तुम इंसान की तरह स्वाभाविक भाषा (हिंदी, मराठी या English—जिस भाषा में यूज़र बात करे) में बात करते हो, "
                            "पिछली बातचीत को याद रखते हो और यूज़र के हर आदेश या सवाल का सटीक और व्यावहारिक जवाब देते हो।\n\n"
                            f"पिछली बातचीत:\n{history_text}\n\nSAAM का जवाब:"
                        )
                        res = generate_with_fallback(client, saam_prompt)
                        reply = res.text
                        st.write(reply)
                        st.session_state.saam_messages.append({"role": "assistant", "content": reply})
                    except Exception as e:
                        st.error(f"SAAM को समस्या आई: {e}")

with tab3:
    st.subheader("📢 सरकारी भर्ती (Govt Vacancy) अपडेट्स")
    dept = st.selectbox(
        "विभाग चुनें:",
        ["MPSC (राज्यसेवा व गट ब/क)", "महाराष्ट्र पोलीस भरती", "तलाठी व जिल्हा परिषद भरती", "UPSC / SSC / बँकिंग"],
    )
    if st.button("🔍 ताज़ा भर्ती जानकारी देखें", use_container_width=True):
        if not api_key:
            st.warning("⚠️ कृपया सबसे ऊपर अपनी Gemini API Key डालें।")
        else:
            with st.spinner("भर्ती की जानकारी निकाली जा रही है..."):
                try:
                    client = genai.Client(api_key=api_key.strip())
                    vac_prompt = (
                        f"मुझे {dept} की प्रमुख परीक्षाओं, पात्रता, आयु सीमा, चयन प्रक्रिया और "
                        f"आधिकारिक वेबसाइट की पूरी जानकारी सरल हिंदी/मराठी में बिंदुवार बताएं।"
                    )
                    res = generate_with_fallback(client, vac_prompt)
                    st.markdown(res.text)
                except Exception as e:
                    st.error(f"समस्या आई: {e}")
