import io
import time
import streamlit as st
from gtts import gTTS
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from pypdf import PdfReader

st.set_page_config(page_title="SkyMPSC & SAAM AI", page_icon="📚", layout="centered")

class OptionDetail(BaseModel):
    text: str = Field(description="विकल्प का टेक्स्ट (बिना 1/2/3 या A/B/C के)")
    explanation: str = Field(description="यह विकल्प सही या गलत क्यों है, इसकी संक्षिप्त व्याख्या")

class QuestionItem(BaseModel):
    question_intro: str = Field(description="प्रश्न की मुख्य पहली लाइन")
    statements: list[str] = Field(description="विधान अ, ब, क की अलग-अलग सूची। यदि विधान नहीं हैं तो खाली रखें []")
    question_ask: str = Field(description="अंतिम सवाल")
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

def text_to_audio(text, lang_code="hi"):
    clean_text = text.replace("*", "").replace("#", "").replace("-", " ")[:1500]
    tts = gTTS(text=clean_text, lang=lang_code, slow=False)
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp

st.title("📚 SkyMPSC & SAAM AI")
st.caption("इंटरैक्टिव MPSC क्विज़, PDF ऑडियो रीडर और वॉयस असिस्टेंट SAAM")

api_key = st.text_input("🔑 अपनी Gemini API Key डालें:", type="password")

tab1, tab2, tab3, tab4 = st.tabs([
    "📝 MPSC क्विज़",
    "🤖 SAAM वॉयस असिस्टेंट",
    "📄 PDF पढ़कर सुनें",
    "📢 सरकारी भर्ती",
])

with tab1:
    uploaded_files = st.file_uploader(
        "📄 पुराने प्रश्नपत्र या नोट्स की PDF अपलोड करें (वैकल्पिक)",
        type=["pdf"],
        accept_multiple_files=True,
        key="quiz_pdf",
    )
    exam_type = st.selectbox(
        "परीक्षा चुनें:",
        ["MPSC Rajyaseva (राज्यसेवा)", "MPSC Combine Group B & C (संयुक्त गट ब व क)", "MPSC Technical / Engineering"],
    )
    subject = st.text_input("विषय / टॉपिक:", value="भारतीय राज्यघटना (Indian Polity)")
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
    if "locked_answers" not in st.session_state:
        st.session_state.locked_answers = {}

    if st.button("🚀 नया टेस्ट शुरू करें", type="primary", use_container_width=True):
        if not api_key:
            st.warning("⚠️ कृपया ऊपर अपनी Gemini API Key डालें और Enter दबाएं।")
        else:
            with st.spinner("AI आपके लिए इंटरैक्टिव प्रश्न तैयार कर रहा है..."):
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
                        f"हर प्रश्न को 3 साफ हिस्सों में बांटो: question_intro (मुख्य भूमिका), statements (अ, ब, क विधाने अलग-अलग आइटम में), "
                        f"और question_ask (मुख्य सवाल)। हर प्रश्न के ठीक 4 विकल्प (options) दो और हर विकल्प की संक्षिप्त व्याख्या {language} भाषा में लिखो। "
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
                    st.session_state.locked_answers = {}
                    st.rerun()
                except Exception as e:
                    st.error(f"समस्या आई: {e}")

    if st.session_state.quiz_data:
        st.divider()
        questions = st.session_state.quiz_data.questions
        total_q = len(questions)
        correct_count = 0

        for idx, q in enumerate(questions):
            with st.container(border=True):
                st.markdown(f"### 📌 प्रश्न {idx + 1} / {total_q}")
                st.markdown(f"**{q.question_intro}**")

                if q.statements:
                    for stmt in q.statements:
                        st.markdown(f"- {stmt}")

                if q.question_ask:
                    st.markdown(f"**{q.question_ask}**")

                st.write("")
                option_labels = [f"({i+1}) {opt.text}" for i, opt in enumerate(q.options)]
                is_locked = idx in st.session_state.locked_answers
                saved_idx = st.session_state.locked_answers.get(idx, None)

                choice = st.radio(
                    "एक बार विकल्प चुनने के बाद उत्तर लॉक हो जाएगा:",
                    option_labels,
                    index=saved_idx,
                    key=f"radio_q_{idx}",
                    disabled=is_locked,
                )

                if choice is not None and not is_locked:
                    st.session_state.locked_answers[idx] = option_labels.index(choice)
                    st.rerun()

                if is_locked:
                    selected_idx = st.session_state.locked_answers[idx]
                    if selected_idx == q.correct_index:
                        st.success(f"✅ सही उत्तर! आपने चुना: {option_labels[selected_idx]}")
                        correct_count += 1
                    else:
                        st.error(
                            f"❌ गलत उत्तर! आपने चुना: {option_labels[selected_idx]} | "
                            f"सही उत्तर है: {option_labels[q.correct_index]}"
                        )

                    with st.expander("📖 सभी विकल्पों का विस्तृत विश्लेषण देखें", expanded=True):
                        for o_idx, opt in enumerate(q.options):
                            if o_idx == q.correct_index:
                                st.markdown(f"✔️ **({o_idx+1}) {opt.text} (सही):** {opt.explanation}")
                            elif o_idx == selected_idx:
                                st.markdown(f"❌ **({o_idx+1}) {opt.text} (आपका गलत चुनाव):** {opt.explanation}")
                            else:
                                st.markdown(f"✖️ **({o_idx+1}) {opt.text}:** {opt.explanation}")

        attempted = len(st.session_state.locked_answers)
        if attempted == total_q:
            percentage = round((correct_count / total_q) * 100, 1)
            st.success(
                f"🏆 **टेस्ट पूरा हुआ! आपका अंतिम स्कोर: {correct_count} / {total_q} ({percentage}%)**"
            )
        else:
            st.info(f"📊 प्रगति: **{attempted} / {total_q}** प्रश्न हल किए गए | वर्तमान सही उत्तर: **{correct_count}**")

with tab2:
    st.subheader("🤖 SAAM - वॉयस और चैट असिस्टेंट")
    voice_lang = st.selectbox("SAAM की आवाज़ की भाषा:", ["हिंदी (hi)", "मराठी (mr)", "English (en)"])
    lang_code = voice_lang.split("(")[1].replace(")", "")

    if "saam_messages" not in st.session_state:
        st.session_state.saam_messages = [
            {"role": "assistant", "content": "नमस्ते! मैं SAAM हूँ। आप नीचे माइक दबाकर बोल सकते हैं या लिखकर पूछ सकते हैं।"}
        ]

    for i, msg in enumerate(st.session_state.saam_messages):
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg["role"] == "assistant" and "audio" in msg:
                st.audio(msg["audio"], format="audio/mp3")

    audio_val = st.audio_input("🎙️ माइक दबाकर बोलें (बोलने के बाद Stop दबाएं)")
    text_val = st.chat_input("या यहाँ लिखकर SAAM से बात करें...")

    if audio_val is not None or text_val:
        if not api_key:
            st.warning("⚠️ कृपया सबसे ऊपर अपनी Gemini API Key डालें।")
        else:
            client = genai.Client(api_key=api_key.strip())
            user_prompt_text = text_val

            if audio_val is not None and not text_val:
                audio_bytes = audio_val.getvalue()
                if st.session_state.get("last_audio") != audio_bytes:
                    st.session_state.last_audio = audio_bytes
                    with st.spinner("आपकी आवाज़ समझी जा रही है..."):
                        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
                        transcribe_res = generate_with_fallback(
                            client,
