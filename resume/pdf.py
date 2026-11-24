"""Safe PDF text extraction for uploads (resumes and job descriptions)."""
from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfError(ValueError):
    pass


def extract_pdf_text(uploaded_file, max_bytes=5 * 1024 * 1024, max_pages=20, max_chars=60000):
    name = (uploaded_file.name or '').lower()
    if not name.endswith('.pdf'):
        raise PdfError('Only PDF files are supported.')
    if uploaded_file.size > max_bytes:
        raise PdfError(f'The file is too large (max {max_bytes // (1024 * 1024)} MB).')
    head = uploaded_file.read(5)
    uploaded_file.seek(0)
    if head != b'%PDF-':
        raise PdfError('This file is not a valid PDF.')
    try:
        reader = PdfReader(uploaded_file)
        if reader.is_encrypted:
            raise PdfError('Password-protected PDFs are not supported.')
        parts, total = [], 0
        for page in reader.pages[:max_pages]:
            text = page.extract_text() or ''
            parts.append(text)
            total += len(text)
            if total >= max_chars:
                break
    except PdfError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError):
        raise PdfError('Could not read this PDF. Try another file or paste the text.')
    text = '\n'.join(parts).strip()[:max_chars]
    if len(text) < 30:
        raise PdfError('No readable text found in this PDF (scanned PDFs are not supported).')
    return text
