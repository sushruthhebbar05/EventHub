"""QR-code and downloadable ticket image generation (qrcode + Pillow)."""
import io

import qrcode
from PIL import Image, ImageDraw, ImageFont


def make_qr_png(code: str, box_size: int = 8) -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=2)
    qr.add_data(code)  # ONLY the random ticket code - no names, emails or other personal data
    qr.make(fit=True)
    img = qr.make_image(fill_color="#14112b", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def make_ticket_png(*, event_title: str, when: str, venue: str, seat: str, reference: str, code: str) -> bytes:
    """Draw a simple printable ticket: details on the left, QR on the right."""
    w, h = 900, 380
    img = Image.new("RGB", (w, h), "#14112b")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 14, h], fill="#8b5cf6")
    d.text((44, 34), "EVENTHUB E-TICKET", fill="#a78bfa", font=_font(20))
    title = event_title if len(event_title) <= 34 else event_title[:33] + "..."
    d.text((44, 72), title, fill="white", font=_font(36))
    d.text((44, 140), when, fill="#e5e7eb", font=_font(24))
    d.text((44, 178), venue, fill="#e5e7eb", font=_font(22))
    d.text((44, 238), f"Seat  {seat}", fill="white", font=_font(32))
    d.text((44, 300), f"Booking {reference}", fill="#a78bfa", font=_font(20))
    d.text((44, 330), "Show this QR code at the entrance. One entry per ticket.", fill="#9ca3af", font=_font(16))
    qr = Image.open(io.BytesIO(make_qr_png(code, box_size=7))).convert("RGB")
    qr = qr.resize((290, 290))
    d.rounded_rectangle([w - 340, 40, w - 30, 340], radius=18, fill="white")
    img.paste(qr, (w - 330, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
