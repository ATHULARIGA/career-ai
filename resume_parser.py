import pypdf
import io

def extract_text(filename, content):
    if filename.endswith(".pdf"):
        pdf_file = io.BytesIO(content)
        reader = pypdf.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text

    elif filename.endswith(".docx"):
        # Temporary fallback for docx to avoid lxml issues
        return "Docx support temporarily disabled due to system library issues. Please use PDF."

    return ""
