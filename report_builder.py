"""
WFA Report Builder v2 — A3 landscape duplex PDF.
Matches school template exactly based on reference report analysis (Y5 Hazel 2024-25).
Font: Liberation Sans (Calibri-equivalent).
"""
import io, os, requests, tempfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Page geometry ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = landscape(A3)   # 1190.6 × 841.9 pt
COL_W  = PAGE_W / 2              # 595.3 pt per A4 column
BORD   = 6                       # border rect inset from column edge (pt)
PAD    = 14                      # content padding inside border (pt)
# Column content x and usable width
CX = [BORD + PAD,                COL_W + BORD + PAD]  # content x per col
CW = COL_W - 2 * (BORD + PAD)                          # ≈ 551 pt usable width
TOP    = PAGE_H - BORD - PAD     # content top y
BOT    = BORD + PAD              # content bottom y

# ── Colours ────────────────────────────────────────────────────────────────────
WFA    = colors.HexColor('#1798d3')
NAVY   = colors.HexColor('#0E2841')
WHITE  = colors.white
DARK   = colors.HexColor('#1a1a1a')
LGREY  = colors.HexColor('#f5f5f5')
MGREY  = colors.HexColor('#cccccc')
DGREY  = colors.HexColor('#888888')

GRADE_FILL  = {'D': colors.HexColor('#9DC3E6'), 'GD': colors.HexColor('#9DC3E6'),
               'O': colors.HexColor('#C6EFCE'), 'O1': colors.HexColor('#C6EFCE'),
               'O2': colors.HexColor('#C6EFCE'),
               'Y': colors.HexColor('#FFEB9C'),
               'A - Y2': colors.HexColor('#FFCCCC'), 'A - Y3': colors.HexColor('#FFCCCC')}
GRADE_LABEL = {'D':'GD','GD':'GD','O':'O','O1':'O','O2':'O',
               'Y':'Y','A - Y2':'A-2','A - Y3':'A-3'}

ATT_FILL = {
    'Exceptional':     colors.HexColor('#1798d3'),
    'Expected':        colors.HexColor('#92D050'),
    'Below Expected':  colors.HexColor('#FFC000'),
    'Cause for Concern': colors.HexColor('#FF0000'),
}

# ── Font setup ─────────────────────────────────────────────────────────────────
_FONTS_DONE = False

# Font name aliases — resolved at runtime
_F = {'C':'Helvetica','CB':'Helvetica-Bold','CI':'Helvetica-Oblique','CBI':'Helvetica-BoldOblique'}

def _fonts():
    global _FONTS_DONE, _F
    if _FONTS_DONE: return
    fdir = '/usr/share/fonts/truetype/liberation'
    variants = [('C','Regular'),('CB','Bold'),('CI','Italic'),('CBI','BoldItalic')]
    try:
        for alias, variant in variants:
            path = f'{fdir}/LiberationSans-{variant}.ttf'
            if not os.path.exists(path):
                raise FileNotFoundError(f"Font not found: {path}")
            pdfmetrics.registerFont(TTFont(alias, path))
        # All registered — update map to use our aliases
        _F = {k: k for k in _F}
    except Exception:
        # Fallback: use ReportLab built-in Helvetica (no registration needed)
        _F = {'C':'Helvetica','CB':'Helvetica-Bold','CI':'Helvetica-Oblique','CBI':'Helvetica-BoldOblique'}
    _FONTS_DONE = True

# ── Paragraph helpers ──────────────────────────────────────────────────────────
def _style(size=8, bold=False, italic=False, colour=DARK, align=TA_LEFT, leading_mult=1.25):
    font = _F['CBI'] if bold and italic else ('CB' if bold else ('CI' if italic else 'C'))
    return ParagraphStyle('s', fontName=font, fontSize=size,
                          leading=size*leading_mult, textColor=colour,
                          alignment=align, spaceAfter=0, spaceBefore=0)

def _esc(text):
    return (str(text).replace('&','&amp;').replace('<','&lt;')
            .replace('>','&gt;').replace('\n','<br/>'))

def _draw(c, text, x, y_top, width, size=8, bold=False, italic=False,
          colour=DARK, align=TA_LEFT, leading_mult=1.25):
    if not text or not str(text).strip(): return y_top
    p = Paragraph(_esc(text), _style(size, bold, italic, colour, align, leading_mult))
    w, h = p.wrap(width, 9999)
    p.drawOn(c, x, y_top - h)
    return y_top - h

def _h(text, width, size=8, leading_mult=1.25):
    if not text or not str(text).strip(): return 0
    p = Paragraph(_esc(text), _style(size, leading_mult=leading_mult))
    _, h = p.wrap(width, 9999)
    return h

# ── Drawing helpers ────────────────────────────────────────────────────────────
def _border(c, col, lz, radius=5, lw=1.5):
    """Rounded border rect around an entire column."""
    bx = col * COL_W + BORD
    c.setStrokeColor(lz if col == 0 else WFA)
    c.setLineWidth(lw)
    c.roundRect(bx, BORD, COL_W - 2*BORD, PAGE_H - 2*BORD, radius, fill=0, stroke=1)

def _hline(c, col, y, colour=MGREY, lw=0.4, indent=0):
    c.setStrokeColor(colour); c.setLineWidth(lw)
    c.line(CX[col]+indent, y, CX[col]+CW-indent, y)

def _badge(c, grade, x_right, y_mid, w=30, h=18):
    fill = GRADE_FILL.get(grade, LGREY)
    label = GRADE_LABEL.get(grade, grade)
    bx = x_right - w; by = y_mid - h/2
    c.setFillColor(fill); c.setStrokeColor(MGREY); c.setLineWidth(0.5)
    c.roundRect(bx, by, w, h, 3, fill=1, stroke=1)
    c.setFillColor(DARK); c.setFont(_F['CB'], 8)
    tw = c.stringWidth(label, _F['CB'], 8)
    c.drawString(bx+(w-tw)/2, by+h*0.28, label)

def _img(url_or_path, pat=None):
    """Fetch image to temp file, return path or None."""
    if url_or_path and os.path.exists(str(url_or_path)):
        return url_or_path
    if not url_or_path: return None
    try:
        headers = {}
        if pat and 'github' in str(url_or_path):
            headers['Authorization'] = f'token {pat}'
        r = requests.get(url_or_path, headers=headers, timeout=8)
        if r.status_code == 200:
            ext = '.jpg' if b'\xff\xd8' in r.content[:4] else '.png'
            tf = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            tf.write(r.content); tf.close()
            return tf.name
    except Exception:
        pass
    return None

def _place_img(c, path, x, y_bottom, w, h, preserve=True):
    """Draw image if path exists, else grey placeholder."""
    if path and os.path.exists(path):
        try:
            c.drawImage(path, x, y_bottom, w, h,
                       preserveAspectRatio=preserve, anchor='c', mask='auto')
            return
        except Exception:
            pass
    c.setFillColor(LGREY); c.setStrokeColor(MGREY); c.setLineWidth(0.5)
    c.rect(x, y_bottom, w, h, fill=1, stroke=1)
    c.setFillColor(DGREY); c.setFont(_F['CI'], 7)
    c.drawCentredString(x+w/2, y_bottom+h/2-3, 'Image')

# ── FRONT LEFT — enquiry list ──────────────────────────────────────────────────
def _front_left(c, lz, settings, class_id, pat):
    col = 0; x = CX[col]; w = CW; y = TOP

    # "LZ Enquiries" heading — LZ colour text, white background
    c.setFillColor(WHITE)
    c.rect(col*COL_W+BORD, PAGE_H-BORD-32, COL_W-2*BORD, 32, fill=1, stroke=0)
    lz_name = settings.get('class_display', 'Maple Learning Zone')
    c.setFillColor(lz); c.setFont(_F['CB'], 13)
    c.drawCentredString(col*COL_W + COL_W/2, PAGE_H-BORD-20, f'{lz_name} Enquiries')
    y = PAGE_H - BORD - 32

    # Sub-heading band — LZ colour fill, dark bold italic text
    band_h = 20
    c.setFillColor(lz)
    c.rect(col*COL_W+BORD, y-band_h, COL_W-2*BORD, band_h, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont(_F['CBI'], 7.5)
    c.drawCentredString(col*COL_W + COL_W/2, y-band_h+6,
                       "Use this page to help your learner remember the enquiries they have learnt about this year.")
    y -= band_h + 4

    # 6 term rows
    term_h = (y - BOT - 4) / 6
    term_label_w = 46

    for i in range(6):
        row_top = y - i * term_h
        row_bot = row_top - term_h + 3

        # Term label strip (LZ colour)
        c.setFillColor(lz)
        c.rect(x, row_bot, term_label_w, term_h-3, fill=1, stroke=0)
        c.setFillColor(WHITE); c.setFont(_F['CB'], 8)
        c.drawCentredString(x + term_label_w/2, row_bot + term_h/2 - 4, 'Term')
        c.setFont(_F['CB'], 11)
        c.drawCentredString(x + term_label_w/2, row_bot + term_h/2 - 14, str(i+1))

        # Enquiry image area
        img_x = x + term_label_w + 3
        img_w = w - term_label_w - 3
        img_h = term_h - 5

        enq_url = (f"https://raw.githubusercontent.com/wallscourtfarm/wfa-reports/main"
                   f"/data/photos/{class_id}/enquiry_T{i+1}.jpg")
        path = _img(enq_url, pat)
        _place_img(c, path, img_x, row_bot+1, img_w, img_h, preserve=True)

        # Row border
        c.setStrokeColor(MGREY); c.setLineWidth(0.4)
        c.rect(x, row_bot, w, term_h-3, fill=0, stroke=1)

# ── FRONT RIGHT — cover ────────────────────────────────────────────────────────
def _front_right(c, lz, pupil, settings):
    col = 1
    full = f"{pupil['first_name']} {pupil['last_name']}"
    lz_name = settings.get('class_display', 'Maple Learning Zone')
    yr = settings.get('academic_year','2025-26')[:4]
    cx = col*COL_W + COL_W/2   # centre x of right column

    # White background inside border
    c.setFillColor(WHITE)
    c.rect(col*COL_W+BORD, BORD, COL_W-2*BORD, PAGE_H-2*BORD, fill=1, stroke=0)

    # WFA logo — top, centered
    logo_w = 200; logo_h = 94
    logo_y = PAGE_H - BORD - PAD - 10
    logo_path = '/home/claude/wfa_reports/wfa_logo.png'
    _place_img(c, logo_path, cx-logo_w/2, logo_y-logo_h, logo_w, logo_h)

    # School cover photo
    cover_y = logo_y - logo_h - 8
    cover_h = 170; cover_w = COL_W - 2*(BORD+PAD)
    cover_path = '/home/claude/wfa_reports/school_photo.jpg'
    _place_img(c, cover_path, CX[col], cover_y-cover_h, cover_w, cover_h)

    y = cover_y - cover_h - 16

    # "Annual Report to Families"
    c.setFillColor(WFA); c.setFont(_F['CB'], 13)
    c.drawCentredString(cx, y, 'Annual Report to Families')
    y -= 20

    # Thin rule
    c.setStrokeColor(WFA); c.setLineWidth(1)
    c.line(cx-60, y, cx+60, y); y -= 22

    # Pupil name — large, WFA blue
    name_sz = 26
    tw = c.stringWidth(full, 'CB', name_sz)
    if tw > CW - 10:
        name_sz = max(16, int(name_sz * (CW-10)/tw))
    c.setFillColor(WFA); c.setFont(_F['CB'], name_sz)
    c.drawCentredString(cx, y, full)
    y -= name_sz + 6

    # Learning zone name — LZ colour
    c.setFillColor(lz); c.setFont(_F['CB'], 17)
    c.drawCentredString(cx, y, lz_name)
    y -= 28

    # Date — WFA blue
    c.setFillColor(WFA); c.setFont(_F['CB'], 14)
    c.drawCentredString(cx, y, f'July {yr}')

# ── BACK LEFT — letter, grade key, RWM sections ────────────────────────────────
def _back_left(c, pupil, settings):
    col = 0; x = CX[col]; w = CW; y = TOP
    fn = pupil['first_name']
    grades = pupil.get('grades', {})
    comments = pupil.get('comments', {})
    letter = settings.get('principals_letter','')

    # White bg
    c.setFillColor(WHITE)
    c.rect(col*COL_W+BORD, BORD, COL_W-2*BORD, PAGE_H-2*BORD, fill=1, stroke=0)

    # Dear Families letter (already starts with 'Dear Families,')
    if letter.strip():
        y = _draw(c, letter.strip(), x, y, w, size=7.5, leading_mult=1.3); y -= 6

    # Attainment note
    y = _draw(c, "Learner's attainment is based on the expectations for their year group "
              "and is assessed in the following ways:", x, y, w, size=7.5, bold=True)
    y -= 4

    # Grade key table
    grade_rows = [
        ('GD - Greater Depth',
         'Learners who have achieved the age-related standard for their year group and '
         'in some aspects have been learning at greater depth.'),
        ('O - On Track',
         'Learners who have achieved the age-related standard.'),
        ('Y - Yet to be on track',
         'Learners who have not yet achieved the age-related standard and are having '
         'additional support and provision to develop their skills.'),
        ('A - At an earlier stage\n(A - Year Group)',
         'Learners who are below the age-related standard for their year group and still '
         'have gaps within the curriculum from a previous year group. For example, A-2 means '
         'the learner is working within the Year 2 curriculum.'),
    ]
    col1_w = w * 0.30; col2_w = w - col1_w
    for gi, (label, desc) in enumerate(grade_rows):
        fill = colors.HexColor('#f9f9f9') if gi % 2 == 0 else WHITE
        lh = max(_h(label, col1_w, 7.5), _h(desc, col2_w-4, 7.5)) + 6
        c.setFillColor(fill); c.setStrokeColor(MGREY); c.setLineWidth(0.3)
        c.rect(x, y-lh, w, lh, fill=1, stroke=1)
        _draw(c, label, x+3, y-3, col1_w-6, size=7.5, bold=True)
        _draw(c, desc,  x+col1_w+3, y-3, col2_w-6, size=7.5)
        y -= lh
    y -= 10

    # "X as an Author and a Mathematician" — centred, large, WFA blue
    c.setFillColor(WFA); c.setFont(_F['CB'], 14)
    c.drawCentredString(x+w/2, y, f'{fn} as an Author and a Mathematician')
    y -= 16; _hline(c, col, y, WFA, lw=0.8); y -= 8

    # RWM sections
    for subj_key, label, icon_char in [
        ('reader',       'Being a reader',       '📖'),
        ('writer',       'Being a writer',       '✏'),
        ('mathematician','Being a mathematician', '🔢'),
    ]:
        grade = grades.get({'reader':'R','writer':'W','mathematician':'M'}[subj_key], '')
        text  = comments.get(subj_key, '')

        # Section header box
        hdr_h = 22
        c.setFillColor(WHITE); c.setStrokeColor(MGREY); c.setLineWidth(0.6)
        c.roundRect(x, y-hdr_h, w, hdr_h, 3, fill=1, stroke=1)

        # Icon area (grey bg, left)
        icon_w = 30
        c.setFillColor(LGREY)
        c.roundRect(x+1, y-hdr_h+1, icon_w-2, hdr_h-2, 3, fill=1, stroke=0)
        c.setFillColor(DGREY); c.setFont(_F['C'], 9)
        # Simple icon fallback (unicode might not render — use text abbrev)
        abbrev = {'reader':'📖','writer':'✍','mathematician':'🔢'}
        c.setFont(_F['C'], 7.5)
        c.drawCentredString(x+icon_w/2, y-hdr_h+7, label.split()[-1][:3].upper())

        # Label text
        c.setFillColor(DARK); c.setFont(_F['CB'], 9)
        c.drawString(x+icon_w+6, y-hdr_h+7, label)

        # Grade badge
        if grade:
            _badge(c, grade, x+w-4, y-hdr_h/2, w=28, h=16)

        y -= hdr_h + 4

        # Comment text — justified, 8pt
        if text.strip():
            y = _draw(c, text, x, y, w, size=8, align=TA_JUSTIFY, leading_mult=1.25)
        y -= 10

# ── BACK RIGHT — photo, 21C, R&R, attendance ──────────────────────────────────
def _back_right(c, lz, pupil, settings, class_id, pat):
    col = 1; x = CX[col]; w = CW; cx_col = col*COL_W + COL_W/2
    fn = pupil['first_name']
    lz_name = settings.get('class_display', 'Maple Learning Zone')
    comments = pupil.get('comments', {})
    pv = pupil.get('pupil_voice','')
    att_code = pupil.get('att_code','')

    # White bg
    c.setFillColor(WHITE)
    c.rect(col*COL_W+BORD, BORD, COL_W-2*BORD, PAGE_H-2*BORD, fill=1, stroke=0)

    y = TOP

    # "My time in LZ" — very large, LZ colour, centred
    c.setFillColor(lz); c.setFont(_F['CB'], 17)
    c.drawCentredString(cx_col, y, f'My time in {lz_name}')
    y -= 22

    # Photo (left 48%) + Pupil voice (right 52%)
    box_h = 120
    photo_w = w * 0.46; pv_w = w - photo_w - 6
    photo_path = _img(
        f"https://raw.githubusercontent.com/wallscourtfarm/wfa-reports/main"
        f"/data/photos/{class_id}/{pupil.get('photo','')}",
        pat
    )
    _place_img(c, photo_path, x, y-box_h, photo_w, box_h)
    # PV box
    c.setFillColor(WHITE); c.setStrokeColor(MGREY); c.setLineWidth(0.5)
    c.rect(x+photo_w+6, y-box_h, pv_w, box_h, fill=1, stroke=1)
    if pv.strip():
        _draw(c, pv, x+photo_w+9, y-5, pv_w-6, size=7.5, align=TA_JUSTIFY, leading_mult=1.3)
    else:
        c.setFillColor(DGREY); c.setFont(_F['CI'], 7)
        c.drawCentredString(x+photo_w+6+pv_w/2, y-box_h/2-3, 'Learner voice')
    y -= box_h + 10

    # "X as a learner:" — centred, WFA blue
    c.setFillColor(WFA); c.setFont(_F['CB'], 13)
    c.drawCentredString(cx_col, y, f'{fn} as a learner:')
    y -= 16

    # 4 disposition placeholder boxes
    disp_labels = ['Collaboration', 'Independence', 'Resilience', 'Curiosity &\nImagination']
    disp_h = 72; n = len(disp_labels)
    disp_w = (w - (n-1)*4) / n
    disp_colours = [colors.HexColor('#e8f4fb'), colors.HexColor('#eef9ee'),
                    colors.HexColor('#fff8e8'), colors.HexColor('#fef0f0')]
    for i, (lbl, fill) in enumerate(zip(disp_labels, disp_colours)):
        dx = x + i*(disp_w+4)
        c.setFillColor(fill); c.setStrokeColor(MGREY); c.setLineWidth(0.4)
        c.roundRect(dx, y-disp_h, disp_w, disp_h, 4, fill=1, stroke=1)
        c.setFillColor(DARK); c.setFont(_F['CB'], 6.5)
        for li, line in enumerate(lbl.split('\n')):
            c.drawCentredString(dx+disp_w/2, y-disp_h+8+(1-li)*9, line)
    y -= disp_h + 8

    # 21C Learner comment
    c21 = comments.get('learner_21c','')
    if c21.strip():
        y = _draw(c, c21, x, y, w, size=8, align=TA_JUSTIFY, leading_mult=1.25)
        y -= 8

    # R&R section — simple styled divider
    c.setFillColor(lz); c.setLineWidth(0); 
    c.roundRect(x, y-14, w, 14, 3, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont(_F['CB'], 7.5)
    c.drawCentredString(cx_col, y-10, 'Rights and Responsibilities')
    y -= 20

    rr = comments.get('rights','')
    if rr.strip():
        y = _draw(c, rr, x, y, w, size=8, align=TA_JUSTIFY, leading_mult=1.25)
        y -= 10

    # Attendance table
    hdr_h = 18; row_h = 16
    col_ws = [w*0.28, w*0.37, w*0.35]

    # Header row
    hx = x
    for hi, (hdr, cw_) in enumerate(zip(['', 'Attendance', 'Punctuality'], col_ws)):
        bg = WFA if hdr else WHITE
        tc = WHITE if hdr else DARK
        c.setFillColor(bg); c.setStrokeColor(MGREY); c.setLineWidth(0.3)
        c.rect(hx, y-hdr_h, cw_, hdr_h, fill=1, stroke=1)
        if hdr:
            c.setFillColor(tc); c.setFont(_F['CB'], 7.5)
            c.drawCentredString(hx+cw_/2, y-hdr_h+5, hdr)
        hx += cw_
    y -= hdr_h

    att_rows = [
        ('Exceptional',     'Attendance is 99% or higher',  'Always in school on time'),
        ('Expected',        'Attendance is 96% or higher',  'Very rarely late to school'),
        ('Below Expected',  'Attendance falls below 96%',   'Frequently late to school'),
        ('Cause for Concern','Attendance is below 90%',     'Persistently late to school'),
    ]
    for cat, att_desc, punc_desc in att_rows:
        is_cur = (cat == att_code)
        cat_fill = ATT_FILL.get(cat, LGREY) if is_cur else LGREY
        cat_tc   = WHITE if is_cur else DARK
        row_data = [(cat, cat_fill, cat_tc, True),
                    (att_desc, WHITE, DARK, False),
                    (punc_desc, WHITE, DARK, False)]
        hx = x
        for (txt, bg, tc, bold), cw_ in zip(row_data, col_ws):
            c.setFillColor(bg); c.setStrokeColor(MGREY); c.setLineWidth(0.3)
            c.rect(hx, y-row_h, cw_, row_h, fill=1, stroke=1)
            c.setFillColor(tc); c.setFont('CB' if bold else _F['C'], 7)
            c.drawString(hx+4, y-row_h+5, txt[:38])
            hx += cw_
        y -= row_h

# ── Main ───────────────────────────────────────────────────────────────────────
def generate_reports_pdf(class_data, settings, class_id, pat=None,
                         pupil_ids=None, lz_colour_hex='#1798d3'):
    _fonts()
    lz = colors.HexColor(lz_colour_hex)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A3))
    c.setTitle('Annual Reports to Families')

    pupils = sorted(class_data.get('pupils',[]), key=lambda p: p['last_name'])
    if pupil_ids:
        pupils = [p for p in pupils if p['id'] in pupil_ids]

    for pupil in pupils:
        # ── PAGE 1: FRONT ──────────────────────────────────────────────────────
        _front_left(c, lz, settings, class_id, pat)
        _front_right(c, lz, pupil, settings)
        _border(c, 0, lz); _border(c, 1, lz)
        c.showPage()

        # ── PAGE 2: BACK ───────────────────────────────────────────────────────
        _back_left(c, pupil, settings)
        _back_right(c, lz, pupil, settings, class_id, pat)
        _border(c, 0, lz); _border(c, 1, lz)
        c.showPage()

    c.save(); buf.seek(0)
    return buf
