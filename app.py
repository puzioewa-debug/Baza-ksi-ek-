import streamlit as st
from pypdf import PdfReader
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from google import genai
import tempfile
import os
import re

st.set_page_config(page_title="Baza Książek", page_icon="📚", layout="centered")
st.title("📚 Twój Asystent Książkowy")

# Pobieranie i czyszczenie klucza z ewentualnych spacji lub cudzysłowów
raw_key = st.secrets.get("GEMINI_API_KEY", "")
if not raw_key or "TUTAJ_WKLEJ" in raw_key:
    raw_key = st.text_input("Wpisz swój klucz API Gemini (zaczyna się od AIza...):", type="password")

api_key = raw_key.strip().strip('"').strip("'")

def extract_chunks_from_pdf(file):
    reader = PdfReader(file)
    chunks = []
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text and page_text.strip():
            chunks.append(f"--- Strona {i+1} ---\n{page_text}")
    return chunks

def extract_chunks_from_epub(file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp:
        tmp.write(file.getvalue())
        tmp_path = tmp.name
    try:
        book = epub.read_epub(tmp_path)
        chunks = []
        section = 1
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                text = soup.get_text().strip()
                if text:
                    # Dzielimy długie rozdziały na mniejsze części po ok. 3000 znaków
                    for j in range(0, len(text), 3000):
                        part = text[j:j+3000]
                        chunks.append(f"--- Rozdział/Część {section} ---\n{part}")
                        section += 1
        return chunks
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def find_best_chunks(chunks, query, top_k=15):
    # Wyciągamy słowa kluczowe z pytania (minimum 3 litery)
    words = [w.lower() for w in re.findall(r'\w+', query) if len(w) >= 3]
    if not words:
        return "\n\n".join(chunks[:top_k])
    
    scored = []
    for idx, chunk in enumerate(chunks):
        chunk_lower = chunk.lower()
        # Liczymy ile razy słowa (lub ich rdzenie) pojawiają się na danej stronie
        score = sum(chunk_lower.count(w[:5]) for w in words)
        scored.append((score, idx, chunk))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    # Bierzemy 15 najbardziej trafnych stron i układamy je po kolei
    best = sorted(scored[:top_k], key=lambda x: x[1])
    return "\n\n".join(c[2] for c in best)

uploaded_file = st.file_uploader("Wybierz książkę z telefonu (PDF lub EPUB)", type=["pdf", "epub"])

if uploaded_file and api_key:
    if "book_chunks" not in st.session_state or st.session_state.get("file_name") != uploaded_file.name:
        with st.spinner("Wczytuję i indeksuję książkę... To potrwa kilka sekund."):
            if uploaded_file.name.lower().endswith(".pdf"):
                st.session_state.book_chunks = extract_chunks_from_pdf(uploaded_file)
            else:
                st.session_state.book_chunks = extract_chunks_from_epub(uploaded_file)
            st.session_state.file_name = uploaded_file.name
        st.success(f"Gotowe! Wczytano {len(st.session_state.book_chunks)} stron/części z '{uploaded_file.name}'.")

    query = st.text_input("O co chcesz zapytać tę książkę?")
    
    if query:
        with st.spinner("Przeszukuję książkę i przygotowuję odpowiedź..."):
            try:
                client = genai.Client(api_key=api_key)
                relevant_text = find_best_chunks(st.session_state.book_chunks, query)
                
                prompt = f"""Jesteś precyzyjnym asystentem badawczym. Odpowiedz na pytanie użytkownika, 
opierając się WYŁĄCZNIE na poniższych fragmentach książki. Podaj konkretne informacje 
oraz wskaż numery stron lub części, z których pochodzą.
Jeśli informacji nie ma w podanych fragmentach, napisz to wprost.

Pytanie: {query}

Wybrane fragmenty książki:
{relevant_text}"""
                
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                st.markdown("### Odpowiedź:")
                st.write(response.text)
                
                with st.expander("🔍 Zobacz fragmenty książki, z których skorzystano"):
                    st.text(relevant_text)
                    
            except Exception as e:
                st.error(f"Szczegóły błędu połączenia z AI: {e}")
                st.info("Wskazówka: Jeśli widzisz wyżej napis 'API_KEY_INVALID', oznacza to, że klucz w ustawieniach Secrets jest nieprawidłowy. Jeśli widzisz 'RESOURCE_EXHAUSTED', odczekaj 1 minutę i spróbuj ponownie.")
