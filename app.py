import streamlit as st
from pypdf import PdfReader
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import tempfile
import os
import re

st.set_page_config(page_title="Baza Książek", page_icon="📚", layout="centered")
st.title("📚 Twój Asystent Książkowy")
st.caption("Wersja bezpośrednia – działa od ręki bez kluczy API")

def extract_chunks_from_pdf(file):
    reader = PdfReader(file)
    chunks = []
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text and page_text.strip():
            chunks.append((f"Strona {i+1}", page_text))
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
                    for j in range(0, len(text), 2500):
                        part = text[j:j+2500]
                        chunks.append((f"Część {section}", part))
                        section += 1
        return chunks
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# Polskie słowa pomocnicze, które ignorujemy przy szukaniu, by trafiać w sedno
STOP_WORDS = {"jak", "jaki", "jaka", "jakie", "czy", "gdzie", "kiedy", "jest", "są", "dla", "przy", "oraz", "lub", "pod", "nad", "tym", "tego", "tej", "co", "to", "się", "nie", "tak", "który", "która", "które"}

def search_book(chunks, query, max_results=10):
    words = [w.lower() for w in re.findall(r'\w+', query) if len(w) >= 3 and w.lower() not in STOP_WORDS]
    if not words:
        words = [w.lower() for w in re.findall(r'\w+', query) if len(w) >= 2]
    
    results = []
    for label, text in chunks:
        text_lower = text.lower()
        # Szukamy rdzeni słów (pierwsze 4-5 liter), żeby uwzględnić polskie odmiany przez przypadki
        roots = [w[:5] if len(w) >= 6 else w[:4] if len(w) >= 4 else w for w in words]
        
        score = 0
        matched_roots = set()
        for r in roots:
            count = text_lower.count(r)
            if count > 0:
                score += count
                matched_roots.add(r)
        
        # Premia za strony, gdzie występuje kilka szukanych słów naraz
        score += len(matched_roots) * 10
        
        if score > 0:
            results.append((score, label, text, roots))
            
    results.sort(key=lambda x: x[0], reverse=True)
    return results[:max_results]

def highlight_text(text, roots):
    highlighted = text
    for r in set(roots):
        if len(r) >= 3:
            pattern = re.compile(f"({re.escape(r)}\\w*)", re.IGNORECASE)
            highlighted = pattern.sub(r"<mark style='background-color: #ffe066; padding: 1px 4px; border-radius: 3px;'>\1</mark>", highlighted)
    return highlighted

uploaded_file = st.file_uploader("Wybierz książkę z telefonu (PDF lub EPUB)", type=["pdf", "epub"])

if uploaded_file:
    if "book_chunks" not in st.session_state or st.session_state.get("file_name") != uploaded_file.name:
        with st.spinner("Wczytuję książkę... To potrwa kilka sekund."):
            if uploaded_file.name.lower().endswith(".pdf"):
                st.session_state.book_chunks = extract_chunks_from_pdf(uploaded_file)
            else:
                st.session_state.book_chunks = extract_chunks_from_epub(uploaded_file)
            st.session_state.file_name = uploaded_file.name
        st.success(f"Gotowe! Wczytano {len(st.session_state.book_chunks)} stron/części z '{uploaded_file.name}'.")

    query = st.text_input("Wpisz czego szukasz w książce (temat, objaw, punkt, pytanie):")
    
    if query:
        results = search_book(st.session_state.book_chunks, query)
        if not results:
            st.warning("Nie znaleziono dokładnych odpowiedników w tekście. Spróbuj wpisać pojedyncze słowo kluczowe (np. 'migrena' zamiast długiego zdania).")
        else:
            st.markdown(f"### Znaleziono {len(results)} najbardziej trafnych miejsc w książce:")
            for score, label, text, roots in results:
                with st.expander(f"📖 {label}", expanded=True):
                    clean_text = " ".join(text.split())
                    st.markdown(highlight_text(clean_text, roots), unsafe_allow_html=True)
