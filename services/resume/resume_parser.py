import pypdf
import io

def extract_text(filename, content):
    filename = (filename or "").lower()

    if filename.endswith(".pdf"):
        pdf_file = io.BytesIO(content)
        reader = pypdf.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
        return text

    if filename.endswith(".docx"):
        raise ValueError("DOCX support is temporarily disabled. Please upload a PDF.")

    raise ValueError("Unsupported file type. Please upload a PDF.")
