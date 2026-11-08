import streamlit as st
from pypdf import PdfReader
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from google import genai
import json

# Konfiguracja ściśle pod ekran telefonu (wąski układ, schowane menu boczne)
st.set_page_config(
    page_title="Czytnik AI",
    page_icon="📱",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Stylizacja CSS powiększająca przyciski i dopasowująca czcionki pod iPhone'a
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        height: 3.2em;
        font-size: 16px !important;
        font-weight: 600;
        border-radius: 12px;
        margin-bottom: 6px;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 5rem;
    }
    </style>
""", unsafe_allow_html=True)

st.subheader("📚 Twój Mobilny Asystent Książek")

# 1. Sprawdzanie klucza API
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Brakuje klucza API! Dodaj GEMINI_API_KEY w ustawieniach Secrets w Streamlit.")
    st.stop()

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# Automatyczne wykrywanie działającego modelu dla Twojego klucza
@st.cache_resource
def znajdz_najlepszy_model():
    try:
         dostepne = []
        for m in client.models.list():
            nazwa = m.name.replace("models/", "")
            if "gemini" in nazwa and "flash" in nazwa and "vision" not in nazwa:
                dostepne.append(nazwa)
        # Sortujemy tak, aby wybrać najnowszą wersję (np. 3.x przed 2.x)
        if dostepne:
            dostepne.sort(reverse=True)
            return dostepne
    except Exception:
        pass
    # Lista zapasowa, gdyby pobieranie listy się nie powiodło
    return ["gemini-3-flash-preview", "gemini-3.8-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

lista_modeli = znajdz_najlepszy_model()

# 2. Inicjalizacja pamięci w sesji
if "messages" not in st.session_state:
    st.session_state.messages = []
if "book_text" not in st.session_state:
    st.session_state.book_text = ""
if "book_name" not in st.session_state:
    st.session_state.book_name = ""

# Funkcje czytające książki
def extract_pdf(file):
    reader = PdfReader(file)
    text = []
    for i, page in enumerate(reader.pages):
        content = page.extract_text()
        if content:
            text.append(f"--- Strona {i+1} ---\n{content}")
    return "\n".join(text)

def extract_epub(file):
    book = ebooklib.epub.read_epub(file)
    text = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text.append(soup.get_text())
    return "\n".join(text)

# 3. KAFELEK 1: Wgrywanie książki (zwija się automatycznie po wgraniu)
with st.expander("📂 1. Wgraj książkę (PDF / EPUB)", expanded=(st.session_state.book_text == "")):
    uploaded_file = st.file_uploader("Wybierz plik z telefonu", type=["pdf", "epub"])
    if uploaded_file is not None and uploaded_file.name != st.session_state.book_name:
        with st.spinner("Przetwarzam książkę..."):
            if uploaded_file.name.endswith(".pdf"):
                st.session_state.book_text = extract_pdf(uploaded_file)
            elif uploaded_file.name.endswith(".epub"):
                st.session_state.book_text = extract_epub(uploaded_file)
            st.session_state.book_name = uploaded_file.name
            st.rerun()

    if st.session_state.book_name:
        st.success(f"Aktywna książka: **{st.session_state.book_name}**")

# 4. KAFELEK 2: Zapisywanie i wczytywanie pamięci na telefon
with st.expander("💾 2. Pamięć rozmowy (Zapisz / Wczytaj)", expanded=False):
    if st.session_state.messages:
        txt_export = f"Rozmowa o książce: {st.session_state.book_name}\n\n"
        for m in st.session_state.messages:
            rola = "Ty" if m["role"] == "user" else "AI"
            txt_export += f"{rola}:\n{m['content']}\n\n---\n\n"
        
        st.download_button(
            label="📄 Pobierz notatki (TXT do czytania)",
            data=txt_export,
            file_name="notatki_z_ksiazki.txt",
            mime="text/plain"
        )
        
        json_export = json.dumps(st.session_state.messages, ensure_ascii=False, indent=2)
        st.download_button(
            label="📥 Zapisz pamięć czatu (JSON)",
            data=json_export,
            file_name="pamiec_czatu.json",
            mime="application/json"
        )
        
        if st.button("🗑️ Wyczyść obecną rozmowę"):
            st.session_state.messages = []
            st.rerun()
    else:
        st.info("Napisz pierwszą wiadomość na dole, aby móc zapisać rozmowę.")

    st.write("---")
    uploaded_memory = st.file_uploader("Wczytaj zapisaną wcześniej pamięć (plik JSON)", type=["json"])
    if uploaded_memory is not None:
        if st.button("🔄 Przywróć tę rozmowę"):
            st.session_state.messages = json.load(uploaded_memory)
            st.success("Rozmowa przywrócona!")
            st.rerun()

# 5. Główny ekran czatu
st.write("---")

if not st.session_state.book_text:
    st.info("👆 Najpierw wgraj książkę w pierwszym kafelku na górze, aby rozpocząć rozmowę.")
else:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("O co chcesz zapytać? Np. 'Wyszukaj fragmenty o...'")

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Szukam w książce..."):
                historia_tekst = "\n".join(
                    [f"{m['role']}: {m['content']}" for m in st.session_state.messages[-6:]]
                )
                
                prompt = f"""Jesteś pomocnym i konkretnym asystentem analizującym książkę '{st.session_state.book_name}'.
Odpowiadaj jasno, po ludzku i konkretnie, opierając się na poniższym tekście książki. 
Jeśli proszono o wyszukanie informacji, wskaż dokładne wnioski i cytaty (lub numery stron, jeśli są widoczne).

DOTYCHCZASOWA ROZMOWA:
{historia_tekst}

TEKST KSIĄŻKI:
{st.session_state.book_text[:400000]}

POLECENIE UŻYTKOWNICZKI:
{user_input}"""

                reply = None
                ostatni_blad = ""
                
                # Próbujemy kolejne dostępne modele aż do skutku
                for model_name in lista_modeli:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt
                        )
                        reply = response.text
                        break
                    except Exception as e:
                        ostatni_blad = str(e)
                        continue

                if reply is None:
                    reply = f"Nie udało się połączyć z żadnym modelem. Ostatni komunikat: {ostatni_blad}"

                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
