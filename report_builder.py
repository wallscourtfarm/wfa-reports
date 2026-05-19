"""
WFA Report Builder — generates A3 landscape duplex PDF.
Each pupil = 2 pages (front + back of one A3 sheet).
Font: Liberation Sans (Calibri-equivalent, metric-compatible).
"""
import io, os, tempfile, requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Page geometry ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = landscape(A3)   # 1190.6 × 841.9 pt
COL_W  = PAGE_W / 2              # 595.3 pt — one A4 portrait width
MARGIN = 15 * mm                 # 42.5 pt side margin within each column
CW     = COL_W - 2 * MARGIN      # 510.3 pt — usable column width
TOP    = PAGE_H - 12 * mm        # top usable y (12mm from page top)
BOT    = 10 * mm                 # bottom usable y

# ── Colours ────────────────────────────────────────────────────────────────────
WFA_BLUE  = colors.HexColor('#1798d3')
NAVY      = colors.HexColor('#0E2841')
WHITE     = colors.white
DARK      = colors.HexColor('#1a1a1a')
LGREY     = colors.HexColor('#f2f2f2')
MGREY     = colors.HexColor('#cccccc')

GRADE_FILL = {
    'D': colors.HexColor('#9DC3E6'), 'O': colors.HexColor('#C6EFCE'),
    'O1': colors.HexColor('#C6EFCE'), 'O2': colors.HexColor('#C6EFCE'),
    'Y': colors.HexColor('#FFEB9C'), 'A - Y2': colors.HexColor('#FFCCCC'),
    'A - Y3': colors.HexColor('#FFCCCC'),
}
GRADE_LABEL = {
    'D': 'GD', 'O': 'O', 'O1': 'O', 'O2': 'O',
    'Y': 'Y', 'A - Y2': 'A-2', 'A - Y3': 'A-3',
}

# ── Fonts ──────────────────────────────────────────────────────────────────────
_FONT_DIR = '/usr/share/fonts/truetype/liberation'
_FONTS_REGISTERED = False

def _ensure_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    pdfmetrics.registerFont(TTFont('Cal',     f'{_FONT_DIR}/LiberationSans-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Cal-B',   f'{_FONT_DIR}/LiberationSans-Bold.ttf'))
    pdfmetrics.registerFont(TTFont('Cal-I',   f'{_FONT_DIR}/LiberationSans-Italic.ttf'))
    pdfmetrics.registerFont(TTFont('Cal-BI',  f'{_FONT_DIR}/LiberationSans-BoldItalic.ttf'))
    _FONTS_REGISTERED = True

# ── Paragraph helper ───────────────────────────────────────────────────────────
def _para(text, size=8, bold=False, colour=DARK, leading_mult=1.25, italic=False):
    font = 'Cal-BI' if bold and italic else ('Cal-B' if bold else ('Cal-I' if italic else 'Cal'))
    return ParagraphStyle(
        'auto', fontName=font, fontSize=size,
        leading=size * leading_mult, textColor=colour,
        spaceAfter=0, spaceBefore=0,
    )

def _draw_para(c, text, x, y_top, width, size=8, bold=False, colour=DARK,
               leading_mult=1.25, italic=False):
    """Draw wrapped paragraph, return new y (bottom edge)."""
    if not text or not text.strip():
        return y_top
    style = _para(text, size, bold, colour, leading_mult, italic)
    escaped = (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
               .replace('\n', '<br/>'))
    para = Paragraph(escaped, style)
    w, h = para.wrap(width, 9999)
    para.drawOn(c, x, y_top - h)
    return y_top - h

def _text_height(text, width, size=8, leading_mult=1.25):
    """Return the height a paragraph would occupy."""
    if not text or not text.strip():
        return 0
    style = _para(text, size, leading_mult=leading_mult)
    escaped = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    para = Paragraph(escaped, style)
    _, h = para.wrap(width, 9999)
    return h

# ── Drawing primitives ─────────────────────────────────────────────────────────
def _col_x(col):
    """Left x of column content (col 0=left, col 1=right)."""
    return col * COL_W + MARGIN

def _band(c, col, y_top, height, fill=WFA_BLUE, stroke=False):
    """Full-column-width coloured band."""
    c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(fill)
        c.rect(col * COL_W, y_top - height, COL_W, height, fill=1, stroke=1)
    else:
        c.rect(col * COL_W, y_top - height, COL_W, height, fill=1, stroke=0)

def _box(c, x, y_top, w, h, fill=WHITE, stroke_color=MGREY, lw=0.5):
    """Rectangle with optional fill and border."""
    c.setFillColor(fill)
    c.setStrokeColor(stroke_color)
    c.setLineWidth(lw)
    c.rect(x, y_top - h, w, h, fill=1, stroke=1)

def _grade_badge(c, grade, x_right, y_centre, w=28, h=16):
    """Draw a grade badge (right-aligned at x_right)."""
    fill = GRADE_FILL.get(grade, LGREY)
    label = GRADE_LABEL.get(grade, grade)
    bx = x_right - w
    by = y_centre - h / 2
    c.setFillColor(fill)
    c.setStrokeColor(colors.HexColor('#999999'))
    c.setLineWidth(0.5)
    c.roundRect(bx, by, w, h, 3, fill=1, stroke=1)
    c.setFillColor(DARK)
    c.setFont('Cal-B', 7)
    tw = c.stringWidth(label, 'Cal-B', 7)
    c.drawString(bx + (w - tw) / 2, by + h * 0.25, label)

def _section_header(c, col, y_top, title, grade=None, fill=WFA_BLUE, h=18):
    """Blue header band with title and optional grade badge. Returns new y."""
    cx = col * COL_W
    cw = COL_W
    # Band
    c.setFillColor(fill)
    c.rect(cx, y_top - h, cw, h, fill=1, stroke=0)
    # Title
    c.setFillColor(WHITE)
    c.setFont('Cal-B', 8.5)
    c.drawString(cx + MARGIN, y_top - h * 0.65, title)
    # Grade badge
    if grade:
        _grade_badge(c, grade, cx + cw - MARGIN * 0.5, y_top - h / 2)
    return y_top - h

def _divider(c, col, y, colour=MGREY, lw=0.4):
    c.setStrokeColor(colour)
    c.setLineWidth(lw)
    c.line(col * COL_W + MARGIN, y, col * COL_W + COL_W - MARGIN, y)

# ── Image loading ──────────────────────────────────────────────────────────────
_img_cache = {}

def _fetch_image(url, fallback_size=(100, 80)):
    """Fetch image from URL to temp file, return path or None."""
    if url in _img_cache:
        return _img_cache[url]
    try:
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            suffix = '.jpg' if 'jpeg' in r.headers.get('content-type','') else '.png'
            tf = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tf.write(r.content); tf.close()
            _img_cache[url] = tf.name
            return tf.name
    except Exception:
        pass
    _img_cache[url] = None
    return None

# ── Front page ─────────────────────────────────────────────────────────────────
def _front_page(c, pupil, settings, class_id, lz_colour, pat):
    fn = pupil['first_name']; ln = pupil['last_name']
    full = f"{fn} {ln}"
    year = settings.get('academic_year', '2025-26')
    lz_name = settings.get('class_display', 'Maple Learning Zone')

    # ── LEFT COLUMN: Enquiry list ──────────────────────────────────────────────
    y = TOP
    col = 0; cx = _col_x(col)

    # Header band
    _band(c, col, y, 26, fill=lz_colour)
    c.setFillColor(WHITE); c.setFont('Cal-B', 10)
    c.drawString(cx, y - 18, f'{lz_name} Enquiries')
    y -= 26

    # Sub-text
    y -= 5
    y = _draw_para(c, "Use this page to help your learner remember the enquiries they have learnt about this year.",
                   cx, y, CW, size=7.5, colour=colors.HexColor('#444444'))
    y -= 8

    # 6 term boxes — 2 cols × 3 rows
    bw = (CW - 8) / 2   # box width
    bh = (y - BOT - 12) / 3  # box height per row
    bh = min(bh, 175)

    for i in range(6):
        row = i // 2; col_i = i % 2
        bx = cx + col_i * (bw + 8)
        by_top = y - row * (bh + 6)

        # Box background
        c.setFillColor(LGREY); c.setStrokeColor(MGREY); c.setLineWidth(0.5)
        c.roundRect(bx, by_top - bh, bw, bh, 4, fill=1, stroke=1)

        # Term label band
        c.setFillColor(lz_colour)
        c.roundRect(bx, by_top - 16, bw, 16, 4, fill=1, stroke=0)
        c.setFillColor(WHITE); c.setFont('Cal-B', 8)
        c.drawString(bx + 6, by_top - 11, f'Term {i + 1}')

        # Try to load enquiry image
        img_url = (f"https://raw.githubusercontent.com/wallscourtfarm/wfa-reports/main"
                   f"/data/photos/{class_id}/enquiry_T{i+1}.jpg")
        img_path = _fetch_image(img_url) if pat else None
        if img_path and os.path.exists(img_path):
            img_h = bh - 20; img_w = bw - 8
            try:
                c.drawImage(img_path, bx + 4, by_top - bh + 4, img_w, img_h,
                           preserveAspectRatio=True, mask='auto')
            except Exception:
                pass
        else:
            # Placeholder
            c.setFillColor(colors.HexColor('#dddddd'))
            c.rect(bx + 4, by_top - bh + 4, bw - 8, bh - 22, fill=1, stroke=0)
            c.setFillColor(colors.HexColor('#999999'))
            c.setFont('Cal-I', 7)
            c.drawCentredString(bx + bw / 2, by_top - bh/2 - 4, 'Enquiry image')

    # ── RIGHT COLUMN: Cover ────────────────────────────────────────────────────
    col = 1; cx = _col_x(col)
    col_cx = col * COL_W + COL_W / 2   # centre of right column

    # WFA Logo — vertically centre all cover content
    # Estimate total content height: logo(75) + gaps + text blocks ≈ 240pt
    content_h = 280
    start_y = PAGE_H / 2 + content_h / 2   # centre in page height
    logo_w = 160; logo_h = 75
    logo_y = start_y
    logo_path = '/home/claude/wfa_reports/wfa_logo.png'
    if os.path.exists(logo_path):
        c.drawImage(logo_path, col_cx - logo_w / 2, logo_y - logo_h,
                   logo_w, logo_h, preserveAspectRatio=True, mask='auto')

    # Decorative rule
    y_r = logo_y - logo_h - 12
    c.setStrokeColor(lz_colour); c.setLineWidth(2)
    c.line(col_cx - 80, y_r, col_cx + 80, y_r)
    y_r -= 20

    # "Annual Report to Families"
    c.setFillColor(NAVY); c.setFont('Cal-B', 14)
    tw = c.stringWidth('Annual Report to Families', 'Cal-B', 14)
    c.drawString(col_cx - tw / 2, y_r, 'Annual Report to Families')
    y_r -= 22

    c.setStrokeColor(lz_colour); c.setLineWidth(1)
    c.line(col_cx - 60, y_r, col_cx + 60, y_r)
    y_r -= 28

    # Pupil name
    c.setFillColor(NAVY); c.setFont('Cal-B', 18)
    tw = c.stringWidth(full, 'Cal-B', 18)
    # Scale down if too wide
    if tw > CW - 20:
        sz = 18 * (CW - 20) / tw
        c.setFont('Cal-B', sz)
        tw = c.stringWidth(full, 'Cal-B', sz)
    c.drawString(col_cx - tw / 2, y_r, full)
    y_r -= 20

    # Learning zone name in LZ colour
    c.setFillColor(lz_colour); c.setFont('Cal-B', 12)
    tw = c.stringWidth(lz_name, 'Cal-B', 12)
    c.drawString(col_cx - tw / 2, y_r, lz_name)
    y_r -= 50

    # Date / year
    date_str = f'July {year[:4]}'
    c.setFillColor(colors.HexColor('#555555')); c.setFont('Cal', 10)
    tw = c.stringWidth(date_str, 'Cal', 10)
    c.drawString(col_cx - tw / 2, y_r, date_str)

    # Column separator line
    c.setStrokeColor(MGREY); c.setLineWidth(0.5)
    c.line(COL_W, BOT + 10, COL_W, TOP)


# ── Back page ──────────────────────────────────────────────────────────────────
def _back_page(c, pupil, settings, lz_colour):
    fn = pupil['first_name']
    full = f"{fn} {pupil['last_name']}"
    grades = pupil.get('grades', {})
    comments = pupil.get('comments', {})
    letter = settings.get('principals_letter', '')
    lz_name = settings.get('class_display', 'Maple Learning Zone')

    att      = pupil.get('attendance', '')
    att_code = pupil.get('att_code', '')
    punc     = pupil.get('punctuality', '')
    punc_code = pupil.get('punc_code', '')
    pv       = pupil.get('pupil_voice', '')

    # ── LEFT COLUMN ────────────────────────────────────────────────────────────
    col = 0; cx = _col_x(col); y = TOP

    # Heading: "[Name] as a learner:"
    _band(c, col, y, 22, fill=lz_colour)
    c.setFillColor(WHITE); c.setFont('Cal-B', 10)
    c.drawString(cx, y - 15, f'{fn} as a learner:')
    y -= 22; y -= 6

    # Dear Families letter
    if letter.strip():
        y = _draw_para(c, letter.strip(), cx, y, CW, size=7.5)
        y -= 6
        _divider(c, col, y); y -= 8

    # Attainment explanation
    att_text = ("A learner's attainment is based on the expectations for their year group "
                "and is assessed in the following ways:")
    y = _draw_para(c, att_text, cx, y, CW, size=7, colour=colors.HexColor('#555555'), italic=True)
    y -= 10

    # R&R section
    rr_text = comments.get('rights', '')
    if rr_text.strip():
        y = _section_header(c, col, y, 'As a learner in our community:', fill=lz_colour)
        y -= 5
        y = _draw_para(c, rr_text, cx, y, CW, size=8)
        y -= 8

    # "X as an Author and a Mathematician"
    _band(c, col, y, 22, fill=WFA_BLUE)
    c.setFillColor(WHITE); c.setFont('Cal-B', 10)
    c.drawString(cx, y - 15, f'{fn} as an Author and a Mathematician')
    y -= 22; y -= 6

    # Reader
    r_text = comments.get('reader', '')
    if r_text.strip():
        y = _section_header(c, col, y, 'Being a reader', grade=grades.get('R'))
        y -= 5
        y = _draw_para(c, r_text, cx, y, CW, size=8)
        y -= 8

    # Writer
    w_text = comments.get('writer', '')
    if w_text.strip():
        y = _section_header(c, col, y, 'Being a writer', grade=grades.get('W'))
        y -= 5
        y = _draw_para(c, w_text, cx, y, CW, size=8)
        y -= 8

    # Mathematician
    m_text = comments.get('mathematician', '')
    if m_text.strip():
        y = _section_header(c, col, y, 'Being a mathematician', grade=grades.get('M'))
        y -= 5
        y = _draw_para(c, m_text, cx, y, CW, size=8)

    # ── RIGHT COLUMN ───────────────────────────────────────────────────────────
    col = 1; cx = _col_x(col); y = TOP

    # Heading: "My time in [LZ]"
    _band(c, col, y, 22, fill=lz_colour)
    c.setFillColor(WHITE); c.setFont('Cal-B', 10)
    c.drawString(cx, y - 15, f'My time in {lz_name}')
    y -= 22; y -= 6

    # Photo + Pupil voice (side by side)
    box_h = 100
    photo_w = CW * 0.42; pv_w = CW - photo_w - 6

    # Photo box
    _box(c, cx, y, photo_w, box_h, fill=LGREY, stroke_color=MGREY)
    c.setFillColor(colors.HexColor('#aaaaaa')); c.setFont('Cal-I', 7)
    c.drawCentredString(cx + photo_w / 2, y - box_h / 2 - 3, 'Photo')

    # Pupil voice box
    pv_x = cx + photo_w + 6
    _box(c, pv_x, y, pv_w, box_h, fill=WHITE, stroke_color=MGREY)
    # PV label
    c.setFillColor(lz_colour); c.setFont('Cal-B', 7)
    c.drawString(pv_x + 4, y - 11, 'Pupil voice')
    # PV text
    if pv.strip():
        _draw_para(c, pv, pv_x + 4, y - 16, pv_w - 8, size=7)
    y -= box_h + 8

    # 21C Learner
    c21_text = comments.get('learner_21c', '')
    if c21_text.strip():
        y = _section_header(c, col, y, f'{fn} as a 21st Century Learner:', fill=lz_colour)
        y -= 5
        y = _draw_para(c, c21_text, cx, y, CW, size=8)
        y -= 10

    # Attendance table
    _band(c, col, y, 18, fill=WFA_BLUE)
    c.setFillColor(WHITE); c.setFont('Cal-B', 8.5)
    c.drawString(cx, y - 13, 'Attendance & Punctuality')
    y -= 18

    att_rows = [
        ('Exceptional',    'Attendance 99%+',      'Always on time'),
        ('Expected',       'Attendance 96%+',      'Very rarely late'),
        ('Below Expected', 'Attendance below 96%', 'Occasionally late'),
        ('Cause for Concern','Attendance below 90%','Frequently late'),
    ]
    att_col_fills = {
        'Exceptional':     colors.HexColor('#C6EFCE'),
        'Expected':        colors.HexColor('#C6EFCE'),
        'Below Expected':  colors.HexColor('#FFEB9C'),
        'Cause for Concern': colors.HexColor('#FFCCCC'),
    }

    row_h = 14; col_widths = [CW * 0.28, CW * 0.40, CW * 0.32]
    for label, att_desc, punc_desc in att_rows:
        is_current = (att_code == label or punc_code == label)
        fill = att_col_fills.get(label, WHITE) if is_current else WHITE
        xc = cx
        for ci, (txt, cw_) in enumerate(zip([label, att_desc, punc_desc], col_widths)):
            _box(c, xc, y, cw_, row_h, fill=fill, stroke_color=MGREY, lw=0.3)
            c.setFillColor(DARK if not is_current else colors.HexColor('#333333'))
            font = 'Cal-B' if is_current else 'Cal'
            c.setFont(font, 6.5)
            c.drawString(xc + 3, y - row_h * 0.65, txt[:30])
            xc += cw_
        y -= row_h

    y -= 8

    # Grade key
    _band(c, col, y, 16, fill=WFA_BLUE)
    c.setFillColor(WHITE); c.setFont('Cal-B', 8)
    c.drawString(cx, y - 11, 'Attainment key')
    y -= 16

    grade_key = [
        ('GD', 'Greater Depth',  'GRADE_D', 'Achieved age-related standard — learning at greater depth in some aspects'),
        ('O',  'On Track',       'GRADE_O', 'Achieved the age-related standard'),
        ('Y',  'Yet to meet',    'GRADE_Y', 'Not yet achieved age-related standard — additional support in place'),
        ('A',  'At earlier stage','GRADE_A','Working within an earlier year group curriculum'),
    ]
    grade_fills_key = ['#9DC3E6','#C6EFCE','#FFEB9C','#FFCCCC']

    for (badge, label, _, desc), gf in zip(grade_key, grade_fills_key):
        row_y = y
        key_row_h = 18
        # Badge cell
        _box(c, cx, row_y, 28, key_row_h, fill=colors.HexColor(gf), stroke_color=MGREY, lw=0.3)
        c.setFillColor(DARK); c.setFont('Cal-B', 7.5)
        c.drawCentredString(cx + 14, row_y - key_row_h * 0.6, badge)
        # Label + description
        _box(c, cx + 28, row_y, CW - 28, key_row_h, fill=WHITE, stroke_color=MGREY, lw=0.3)
        c.setFillColor(DARK)            # ← must reset after _box sets fill to WHITE
        c.setFont('Cal-B', 7)
        c.drawString(cx + 32, row_y - 7, label)
        c.setFont('Cal', 6.5)
        c.drawString(cx + 32, row_y - 14.5, desc[:80])
        y -= key_row_h

    # Pupil attendance values at bottom if present
    if att or punc:
        y -= 6
        c.setFillColor(colors.HexColor('#555555')); c.setFont('Cal', 7.5)
        att_display = f"Attendance: {att}  ({att_code})" if att else ""
        punc_display = f"  |  Punctuality: {punc} late(s)  ({punc_code})" if punc else ""
        c.drawString(cx, y - 10, att_display + punc_display)

    # Column separator line
    c.setStrokeColor(MGREY); c.setLineWidth(0.5)
    c.line(COL_W, BOT + 10, COL_W, TOP)


# ── Main entry point ───────────────────────────────────────────────────────────
def generate_reports_pdf(class_data, settings, class_id, pat=None,
                         pupil_ids=None, lz_colour_hex='#1798d3'):
    """
    Generate A3 landscape duplex PDF for one or all pupils.
    Returns BytesIO containing the PDF.
    pupil_ids: list of IDs to include, or None for all.
    """
    _ensure_fonts()

    lz_colour = colors.HexColor(lz_colour_hex)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A3))
    c.setTitle('Annual Reports to Families')

    pupils = class_data.get('pupils', [])
    if pupil_ids:
        pupils = [p for p in pupils if p['id'] in pupil_ids]
    pupils = sorted(pupils, key=lambda p: p['last_name'])

    for pupil in pupils:
        # Page 1: Front
        _front_page(c, pupil, settings, class_id, lz_colour, pat)
        c.showPage()

        # Page 2: Back
        _back_page(c, pupil, settings, lz_colour)
        c.showPage()

    c.save()
    buf.seek(0)
    return buf
