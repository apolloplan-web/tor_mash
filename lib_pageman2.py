from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
import io


def add_page_numbers_to_reader(reader: PdfReader, *, cover_first: bool = True,
                               font_name: str = "Helvetica", font_size: int = 10,
                               y: float = 15) -> PdfWriter:
    """
    Take a pypdf.PdfReader object and return a new pypdf.PdfWriter with
    center-aligned page numbers drawn on each page (except the cover if
    cover_first is True).

    - reader: a PdfReader instance (can be created from a file path or a
      file-like object)
    - cover_first: if True the page at index 0 will be treated as a cover
      and will NOT receive a page number (keeps original behaviour)
    - font_name, font_size, y: reportlab drawing parameters for the footer

    Returns: PdfWriter containing the pages with page-number overlays applied.

    Note: This function does not write any files; the caller is responsible
    for saving the returned PdfWriter (writer.write(fileobj)).
    """
    if reader is None:
        raise ValueError("reader must be a PdfReader instance")

    writer = PdfWriter()

    for i, page in enumerate(reader.pages):
        # Keep first page as-is if requested
        if cover_first and i == 0:
            writer.add_page(page)
            continue

        width = float(page.mediabox.width)
        height = float(page.mediabox.height)

        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(width, height))

        # Page numbering: follow original behaviour where the loop index i is
        # used so that the page after the cover becomes "1" when cover_first is True.
        text = f"- {i} -"
        text_width = stringWidth(text, font_name, font_size)
        x = (width - text_width) / 2

        c.setFont(font_name, font_size)
        c.drawString(x, y, text)
        c.save()

        packet.seek(0)
        overlay = PdfReader(packet)

        # Merge overlay into the source page and add to writer
        page.merge_page(overlay.pages[0])
        writer.add_page(page)

    return writer
