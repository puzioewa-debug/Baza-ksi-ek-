import streamlit as st
from pypdf import PdfReader
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from google import genai
import tempfile
import os

st.set_page_config(page_title="Baza Książek", page_icon="📚", layout="centered")
st.title("📚 Twój Asystent Książkowy")

api_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Wpisz swój klucz API Gemini:", type="password")

def extract_text_from_pdf(file):
    reader = PdfReader(file)
    text = ""
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text:
            text += f"\n--- Strona {i+1} ---\n" + page_text
    return text

def extract_text_from_epub(file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp:
        tmp.write(file.getvalue())
        tmp_path = tmp.name
    try:
        book = epub.read_epub(tmp_path)
        text = ""
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                text += soup.get_text() + "\n"
        return text
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

uploaded_file = st.file_uploader("Wybierz książkę z telefonu (PDF lub EPUB)", type=["pdf", "epub"])

if uploaded_file and api_key:
    client = genai.Client(api_key=api_key)
    
    if "book_text" not in st.session_state or st.session_state.get("file_name") != uploaded_file.name:
        with st.spinner("Wczytuję całą książkę... To potrwa kilka sekund."):
            if uploaded_file.name.lower().endswith(".pdf"):
                st.session_state.book_text = extract_text_from_pdf(uploaded_file)
            else:
                st.session_state.book_text = extract_text_from_epub(uploaded_file)
            st.session_state.file_name = uploaded_file.name
        st.success(f"Książka '{uploaded_file.name}' jest gotowa do przeszukiwania!")

    query = st.text_input("O co chcesz zapytać tę książkę?")
    
    if query:
        with st.spinner("Szukam informacji w książce..."):
            prompt = f"""Jesteś precyzyjnym asystentem badawczym. Odpowiedz na pytanie użytkownika, 
            opierając się WYŁĄCZNIE na poniższej treści książki. Podaj konkretne informacje, 
            a jeśli w tekście są numery stron lub rozdziałów, wskaż je.
            Jeśli informacji nie ma w książce, napisz to wprost.
            
            Pytanie: {query}
            
            Treść książki:
            {st.session_state.book_text}"""
            
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            st.markdown("### Odpowiedź:")
            st.write(response.text)
