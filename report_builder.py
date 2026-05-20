import re
"""
WFA Report Builder v3 — A3 landscape duplex PDF.
Exactly matches school template (reference: Y5 Hazel 2024-25).
Font: Liberation Sans (Calibri-equivalent). Falls back to Helvetica on Streamlit Cloud
      until packages.txt installs fonts-liberation.
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
BORD   = 6                       # border rect inset from column edge
PAD    = 14                      # content inset inside border
CX     = [BORD + PAD, COL_W + BORD + PAD]   # content left x per col
CW     = COL_W - 2*(BORD + PAD)             # ≈ 551 pt usable width
TOP    = PAGE_H - BORD - PAD
BOT    = BORD + PAD

# ── Colours ────────────────────────────────────────────────────────────────────
WFA   = colors.HexColor('#1798d3')
NAVY  = colors.HexColor('#0E2841')
WHITE = colors.white
DARK  = colors.HexColor('#1a1a1a')
LGREY = colors.HexColor('#f5f5f5')
MGREY = colors.HexColor('#cccccc')
DGREY = colors.HexColor('#888888')
CREAM = colors.HexColor('#fffdf5')

MM      = 72 / 25.4           # 1 mm in points
B_LW    = round(2  * MM, 2)  # border line width: 2mm
B_OUTER = round(12 * MM, 2)  # outer margin: 12mm
B_INNER = round(4  * MM, 2)  # inner margin from fold: 4mm
B_TOP   = round(8  * MM, 2)  # top margin: 8mm
B_BOT   = round(9  * MM, 2)  # bottom margin: 9mm
B_PAD   = round(5  * MM, 2)  # content padding inside border: 5mm

GRADE_FILL = {
    'D':colors.HexColor('#9DC3E6'), 'GD':colors.HexColor('#9DC3E6'),
    'O':colors.HexColor('#C6EFCE'), 'O1':colors.HexColor('#C6EFCE'),
    'O2':colors.HexColor('#C6EFCE'),
    'Y':colors.HexColor('#FFEB9C'),
    'A - Y2':colors.HexColor('#FFCCCC'),'A - Y3':colors.HexColor('#FFCCCC'),
}
GRADE_LABEL = {'D':'GD','GD':'GD','O':'O','O1':'O','O2':'O',
               'Y':'Y','A - Y2':'A-2','A - Y3':'A-3'}

# Attendance category colours (always shown regardless of pupil status)
ATT_CAT_FILL = {
    'Exceptional':      colors.HexColor('#1798d3'),
    'Expected':         colors.HexColor('#92D050'),
    'Below Expected':   colors.HexColor('#FFC000'),
    'Cause for Concern':colors.HexColor('#FF0000'),
}

# ── Font setup ─────────────────────────────────────────────────────────────────
_FONTS_DONE = False
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
                raise FileNotFoundError(path)
            pdfmetrics.registerFont(TTFont(alias, path))
        _F = {k: k for k in _F}
    except Exception:
        _F = {'C':'Helvetica','CB':'Helvetica-Bold',
              'CI':'Helvetica-Oblique','CBI':'Helvetica-BoldOblique'}
    _FONTS_DONE = True

# ── Paragraph helpers ──────────────────────────────────────────────────────────
def _style(size=8, bold=False, italic=False, colour=DARK, align=TA_LEFT, lm=1.25):
    fn = _F['CBI'] if bold and italic else (_F['CB'] if bold else (_F['CI'] if italic else _F['C']))
    return ParagraphStyle('s', fontName=fn, fontSize=size, leading=size*lm,
                          textColor=colour, alignment=align, spaceAfter=0, spaceBefore=0)

def _esc(t):
    return str(t).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br/>')

def _draw(c, text, x, y_top, width, size=8, bold=False, italic=False,
          colour=DARK, align=TA_LEFT, lm=1.25, escape=True):
    if not text or not str(text).strip(): return y_top
    html = _esc(text) if escape else str(text)
    p = Paragraph(html, _style(size, bold, italic, colour, align, lm))
    w, h = p.wrap(width, 9999)
    p.drawOn(c, x, y_top - h)
    return y_top - h

def _h(text, width, size=8, lm=1.25):
    if not text or not str(text).strip(): return 0
    p = Paragraph(_esc(text), _style(size, lm=lm))
    _, h = p.wrap(width, 9999)
    return h

# ── Letter renderer ───────────────────────────────────────────────────────────
def _render_letter(c, template, x, y, w, pupil_fn, teacher_name):
    import re as _re_
    if not template or not str(template).strip():
        return y
    text = (str(template)
            .replace('{pupil}', pupil_fn)
            .replace('{teacher}', teacher_name)
            .replace('xxxx', pupil_fn))
    # Both /// and blank lines act as paragraph breaks
    sep = chr(10) + chr(10)
    text = text.replace('///', sep)
    paras = [p.strip() for p in _re_.split(r'\n{2,}', text)]
    for para in paras:
        if not para:
            y -= 4
            continue
        # **bold** markup
        html = _re_.sub(r'\*\*(.+?)\*\*',
                        lambda m: '<b>' + m.group(1) + '</b>', para)
        # Single newlines within para become line breaks
        html = html.replace(chr(10), '<br/>')
        y = _draw(c, html, x, y, w, size=8, lm=1.3, escape=False)
        y -= 5
    return y


# ── Drawing primitives ─────────────────────────────────────────────────────────
def _border(c, col, lz):
    bx = B_OUTER if col == 0 else (COL_W + B_INNER)
    bw = COL_W - B_OUTER - B_INNER
    c.setStrokeColor(lz if col == 0 else WFA)
    c.setLineWidth(B_LW)
    c.rect(bx, B_BOT, bw, PAGE_H - B_TOP - B_BOT, fill=0, stroke=1)

def _badge(c, grade, x_right, y_mid, w=30, h=18):
    fill  = GRADE_FILL.get(grade, LGREY)
    label = GRADE_LABEL.get(grade, grade)
    bx = x_right - w; by = y_mid - h/2
    c.setFillColor(fill); c.setStrokeColor(MGREY); c.setLineWidth(0.5)
    c.roundRect(bx, by, w, h, 3, fill=1, stroke=1)
    c.setFillColor(DARK); c.setFont(_F['CB'], 8)
    tw = c.stringWidth(label, _F['CB'], 8)
    c.drawString(bx + (w - tw)/2, by + h*0.28, label)

def _res_path(*candidates):
    """Return first path that exists from candidates list."""
    for p in candidates:
        if p and os.path.exists(str(p)):
            return p
    return None

def _place_img(c, path, x, y_bot, w, h, preserve=True):
    if path:
        try:
            c.drawImage(path, x, y_bot, w, h,
                       preserveAspectRatio=preserve, anchor='c', mask='auto')
            return True
        except Exception:
            pass
    # Grey placeholder
    c.setFillColor(LGREY); c.setStrokeColor(MGREY); c.setLineWidth(0.4)
    c.rect(x, y_bot, w, h, fill=1, stroke=1)
    c.setFillColor(DGREY); c.setFont(_F['CI'], 7)
    c.drawCentredString(x + w/2, y_bot + h/2 - 3.5, 'Image')
    return False

def _static(filename):
    """Locate a static asset from data/static/ in the repo."""
    sd = os.path.dirname(os.path.abspath(__file__))
    return _res_path(
        os.path.join(sd, 'data', 'static', filename),
        os.path.join(sd, filename),
        os.path.join('/mount/src/wfa-reports/data/static', filename),
        os.path.join('/mount/src/wfa-reports', filename),
    )

def _fetch_img(url, pat=None):
    if not url: return None
    try:
        hdr = {'Authorization': f'token {pat}'} if pat and 'github' in url else {}
        r = requests.get(url, headers=hdr, timeout=8)
        if r.status_code == 200:
            ext = '.jpg' if b'\xff\xd8' in r.content[:4] else '.png'
            tf = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            tf.write(r.content); tf.close()
            return tf.name
    except Exception:
        pass
    return None

# ── FRONT LEFT — enquiry list ──────────────────────────────────────────────────
def _front_left(c, lz, settings, class_id, pat):
    col = 0; x = CX[col]; w = CW; y = TOP

    # Heading — LZ colour text on white background
    hdr_h = 28
    c.setFillColor(WHITE)
    c.rect(col*COL_W+BORD, TOP - hdr_h, COL_W-2*BORD, hdr_h, fill=1, stroke=0)
    c.setFillColor(lz); c.setFont(_F['CB'], 13)
    lz_name = settings.get('class_display', 'Maple Learning Zone')
    c.drawCentredString(col*COL_W + COL_W/2, TOP - hdr_h + 8,
                        f'{lz_name} Enquiries')
    y = TOP - hdr_h

    # Sub-heading — LZ colour fill band, dark bold text
    sub_h = 22
    c.setFillColor(lz)
    c.rect(col*COL_W+BORD, y - sub_h, COL_W-2*BORD, sub_h, fill=1, stroke=0)
    c.setFillColor(WHITE); c.setFont(_F['CBI'], 7.5)
    c.drawCentredString(col*COL_W + COL_W/2, y - sub_h + 7,
                        "Use this page to help your learner remember the "
                        "enquiries they have learnt about this year.")
    y -= sub_h + 2

    # 6 term rows
    term_label_w = 44
    n_rows = 6
    row_h = (y - BOT - 2) / n_rows

    for i in range(n_rows):
        row_top = y - i * row_h
        row_bot = row_top - row_h + 1

        # Row border
        c.setFillColor(WHITE); c.setStrokeColor(MGREY); c.setLineWidth(0.5)
        c.rect(x, row_bot, w, row_h - 1, fill=1, stroke=1)

        # Term label — white/cream bg, dark bold text
        c.setFillColor(CREAM); c.setStrokeColor(MGREY); c.setLineWidth(0.3)
        c.rect(x, row_bot, term_label_w, row_h - 1, fill=1, stroke=1)
        c.setFillColor(DARK); c.setFont(_F['CB'], 8)
        c.drawCentredString(x + term_label_w/2, row_bot + (row_h-1)*0.62, 'Term')
        c.setFont(_F['CB'], 13)
        c.drawCentredString(x + term_label_w/2, row_bot + (row_h-1)*0.32, str(i+1))

        # Enquiry image
        img_x = x + term_label_w + 2
        img_w = w - term_label_w - 2
        img_h = row_h - 5

        enq_url = (f"https://raw.githubusercontent.com/wallscourtfarm/wfa-reports/main"
                   f"/data/photos/{class_id}/enquiry_T{i+1}.jpg")
        path = _fetch_img(enq_url, pat)
        _place_img(c, path, img_x, row_bot + 2, img_w, img_h, preserve=True)

# ── FRONT RIGHT — cover (exact mm spec) ──────────────────────────────────────
def _front_right(c, lz, pupil, settings):
    fn      = pupil['first_name']; ln = pupil['last_name']
    full    = f"{fn} {ln}"
    lz_name = settings.get('class_display', 'Maple Learning Zone')
    yr      = settings.get('academic_year', '2025-26')[:4]

    # Right column border geometry (matches _border spec)
    bx     = COL_W + B_INNER            # border left x
    bw     = COL_W - B_OUTER - B_INNER  # border width ≈ 550pt
    col_cx = bx + bw / 2                # column centre x

    # White fill inside border
    c.setFillColor(WHITE)
    c.rect(bx, B_BOT, bw, PAGE_H - B_TOP - B_BOT, fill=1, stroke=0)

    # ── School photo: top edge 84mm from page top, 127×86mm, centred ──────────
    photo_w    = 127 * MM          # = 360pt
    photo_h    =  86 * MM          # = 244pt
    photo_top  = PAGE_H - 84 * MM  # y of photo top (from page bottom) = 603.8pt
    photo_x    = col_cx - photo_w / 2
    school_path = _static('school_front.jpg')
    _place_img(c, school_path, photo_x, photo_top - photo_h,
               photo_w, photo_h, preserve=False)

    # ── Logo: centred in space above photo, same width as photo ───────────────
    logo_path  = _static('sch_logo_rep.png')
    logo_w     = 127 * MM                # 360pt — same as photo
    logo_h     = round(logo_w / 2.131)  # 169pt — exact aspect ratio
    space_above = (PAGE_H - B_TOP) - photo_top   # ≈ 215pt
    logo_gap    = (space_above - logo_h) / 2     # ≈ 23pt margin top and bottom
    if logo_path:
        try:
            c.drawImage(logo_path, col_cx - logo_w/2, photo_top + logo_gap,
                        logo_w, logo_h, preserveAspectRatio=False, mask='auto')
        except Exception:
            pass

    # ── Text: Calibri Bold, centred, baselines measured from page bottom ──────
    # "Annual Report to Families" — 18pt at 116mm from page bottom
    c.setFillColor(WFA); c.setFont(_F['CB'], 18)
    c.drawCentredString(col_cx, 116 * MM, 'Annual Report to Families')

    # Pupil name — 24pt at 78mm from page bottom
    c.setFont(_F['CB'], 24)
    tw = c.stringWidth(full, _F['CB'], 24)
    if tw > bw - 2 * B_PAD:
        fs = round(24 * (bw - 2 * B_PAD) / tw, 1)
        c.setFont(_F['CB'], max(fs, 14))
    c.drawCentredString(col_cx, 78 * MM, full)

    # Learning zone name — 24pt at 53mm from page bottom, LZ colour
    c.setFont(_F['CB'], 24); c.setFillColor(lz)
    c.drawCentredString(col_cx, 53 * MM, lz_name)

    # Date — 18pt at 30mm from page bottom
    c.setFont(_F['CB'], 18); c.setFillColor(WFA)
    c.drawCentredString(col_cx, 30 * MM, f'July {yr}')


# ── BACK LEFT — letter, grade key, RWM ────────────────────────────────────────
def _back_left(c, pupil, settings):
    col = 0; x = CX[col]; w = CW; y = TOP
    fn     = pupil['first_name']
    grades = pupil.get('grades', {})
    coms   = pupil.get('comments', {})
    letter = settings.get('principals_letter', '')

    c.setFillColor(WHITE)
    c.rect(col*COL_W+BORD, BORD, COL_W-2*BORD, PAGE_H-2*BORD, fill=1, stroke=0)

    # Principal's letter
    teacher = settings.get('teacher_name', 'your class teacher')
    y = _render_letter(c, letter, x, y, w, fn, teacher); y -= 4

    # Attainment note
    y = _draw(c, "Learner's attainment is based on the expectations for their year "
              "group and is assessed in the following ways:",
              x, y, w, size=8, bold=True); y -= 4

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
         'have gaps within the curriculum from a previous year group. For example, A-2 '
         'means the learner is working within the Year 2 curriculum.'),
    ]
    c1w = w * 0.30; c2w = w - c1w
    for gi, (label, desc) in enumerate(grade_rows):
        fill = LGREY if gi % 2 == 0 else WHITE
        lh = max(_h(label, c1w - 6, 7.5), _h(desc, c2w - 6, 7.5)) + 6
        c.setFillColor(fill); c.setStrokeColor(MGREY); c.setLineWidth(0.3)
        c.rect(x, y - lh, w, lh, fill=1, stroke=1)
        _draw(c, label, x+3, y-3, c1w-6, size=7.5, bold=True)
        _draw(c, desc,  x+c1w+3, y-3, c2w-6, size=7.5)
        y -= lh
    y -= 10

    # "X as an Author and a Mathematician" heading
    c.setFillColor(WFA); c.setFont(_F['CB'], 14)
    c.drawCentredString(x + w/2, y, f'{fn} as an Author and a Mathematician')
    y -= 14
    c.setStrokeColor(WFA); c.setLineWidth(0.8)
    c.line(x, y, x+w, y); y -= 8

    # RWM sections
    for subj_key, label in [
        ('reader',       'Being a reader'),
        ('writer',       'Being a writer'),
        ('mathematician','Being a mathematician'),
    ]:
        grade = grades.get({'reader':'R','writer':'W','mathematician':'M'}[subj_key], '')
        text  = coms.get(subj_key, '')

        # Section header box
        hdr_h = 24
        c.setFillColor(WHITE); c.setStrokeColor(MGREY); c.setLineWidth(0.6)
        c.roundRect(x, y - hdr_h, w, hdr_h, 3, fill=1, stroke=1)

        # Icon area
        icon_w = 32
        c.setFillColor(LGREY)
        c.roundRect(x+1, y-hdr_h+1, icon_w-2, hdr_h-2, 3, fill=1, stroke=0)
        c.setFillColor(DARK); c.setFont(_F['CB'], 7)
        c.drawCentredString(x + icon_w/2, y - hdr_h + 9,
                           label.split()[-1][:3].upper())

        # Label
        c.setFont(_F['CB'], 9.5)
        c.drawString(x + icon_w + 6, y - hdr_h + 8, label)

        # Grade badge
        if grade:
            _badge(c, grade, x + w - 5, y - hdr_h/2, w=32, h=18)

        y -= hdr_h + 4

        if text.strip():
            y = _draw(c, text, x, y, w, size=8, align=TA_JUSTIFY, lm=1.25)
        y -= 10

# ── BACK RIGHT — photo, 21C, R&R, attendance ──────────────────────────────────
def _back_right(c, lz, pupil, settings, class_id, pat):
    col = 1; x = CX[col]; w = CW; cx_col = col*COL_W + COL_W/2
    fn       = pupil['first_name']
    lz_name  = settings.get('class_display', 'Maple Learning Zone')
    coms     = pupil.get('comments', {})
    pv       = str(pupil.get('pupil_voice') or '')
    att_code = str(pupil.get('att_code') or '')

    c.setFillColor(WHITE)
    c.rect(col*COL_W+BORD, BORD, COL_W-2*BORD, PAGE_H-2*BORD, fill=1, stroke=0)

    y = TOP

    # "My time in LZ" — large LZ colour centered
    c.setFillColor(lz); c.setFont(_F['CB'], 18)
    c.drawCentredString(cx_col, y, f'My time in {lz_name}')
    y -= 24

    # Photo (left 47%) + Pupil voice text (right 53%)
    box_h   = 150
    photo_w = w * 0.46
    pv_x    = x + photo_w + 8
    pv_w    = w - photo_w - 8

    script_dir = os.path.dirname(os.path.abspath(__file__))
    photo_url = (f"https://raw.githubusercontent.com/wallscourtfarm/wfa-reports/main"
                 f"/data/photos/{class_id}/{pupil.get('photo','')}")
    photo_path = _fetch_img(photo_url, pat)
    _place_img(c, photo_path, x, y - box_h, photo_w, box_h)

    # Pupil voice — no box, just text in the right portion
    if pv.strip():
        _draw(c, pv, pv_x, y - 4, pv_w, size=8, align=TA_JUSTIFY, lm=1.3)
    else:
        c.setFillColor(LGREY); c.setStrokeColor(MGREY); c.setLineWidth(0.4)
        c.roundRect(pv_x, y-box_h, pv_w, box_h, 3, fill=1, stroke=1)
        c.setFillColor(DGREY); c.setFont(_F['CI'], 7.5)
        c.drawCentredString(pv_x + pv_w/2, y - box_h/2 - 3.5, 'Learner voice')
    y -= box_h + 10

    # "X as a learner:" heading
    c.setFillColor(WFA); c.setFont(_F['CB'], 14)
    c.drawCentredString(cx_col, y, f'{fn} as a learner:')
    y -= 18

    # 21st Century Learning dispositions — 21st_report.png
    # 3685×774px, aspect 4.761:1 → at full CW=551pt: height=116pt
    disp_path = _static('21st_report.png')
    disp_w = w; disp_h = round(w / 4.761)   # = 116pt
    _place_img(c, disp_path, x, y - disp_h, disp_w, disp_h, preserve=False)
    y -= disp_h + 6

    # 21C comment
    c21 = coms.get('learner_21c', '')
    if c21.strip():
        y = _draw(c, c21, x, y, w, size=8, align=TA_JUSTIFY, lm=1.25); y -= 8

    # Rights & Responsibilities bunting — rr_report.png
    # 1164×372px, aspect 3.129:1 → at full CW=551pt: height=176pt
    rr_path = _static('rr_report.png')
    rr_w = w; rr_h = round(w / 3.129)   # = 176pt
    _place_img(c, rr_path, x, y - rr_h, rr_w, rr_h, preserve=False)
    y -= rr_h + 4

    # R&R comment
    rr = coms.get('rights', '')
    if rr.strip():
        y = _draw(c, rr, x, y, w, size=8, align=TA_JUSTIFY, lm=1.25); y -= 10

    # Attendance & Punctuality table
    hdr_h = 20; row_h = 17
    col_ws = [w*0.27, w*0.38, w*0.35]

    # Header
    hx = x
    for hdr_txt, cw_ in zip(['', 'Attendance', 'Punctuality'], col_ws):
        bg = WFA if hdr_txt else WHITE
        c.setFillColor(bg); c.setStrokeColor(MGREY); c.setLineWidth(0.3)
        c.rect(hx, y-hdr_h, cw_, hdr_h, fill=1, stroke=1)
        if hdr_txt:
            c.setFillColor(WHITE); c.setFont(_F['CB'], 8)
            c.drawCentredString(hx+cw_/2, y-hdr_h+5, hdr_txt)
        hx += cw_
    y -= hdr_h

    att_rows = [
        ('Exceptional',      'Attendance is 99% or higher',  'Always in school on time'),
        ('Expected',         'Attendance is 96% or higher',  'Very rarely late to school'),
        ('Below Expected',   'Attendance falls below 96%',   'Frequently late to school'),
        ('Cause for Concern','Attendance is below 90%',      'Persistently late to school'),
    ]
    punc_code = str(pupil.get('punc_code') or '')

    for cat, att_desc, punc_desc in att_rows:
        cat_col = ATT_CAT_FILL.get(cat, LGREY)

        # Left cell — always coloured by category
        c.setFillColor(cat_col); c.setStrokeColor(MGREY); c.setLineWidth(0.3)
        c.rect(x, y-row_h, col_ws[0], row_h, fill=1, stroke=1)
        c.setFillColor(WHITE); c.setFont(_F['CB'], 7)
        c.drawString(x+3, y-row_h+5, cat)

        # Middle cell — coloured if attendance category matches this row
        att_match = (cat == att_code)
        rx_mid = x + col_ws[0]
        bg_m = cat_col if att_match else WHITE
        tc_m = WHITE if att_match else DARK
        c.setFillColor(bg_m); c.setStrokeColor(MGREY); c.setLineWidth(0.3)
        c.rect(rx_mid, y-row_h, col_ws[1], row_h, fill=1, stroke=1)
        c.setFillColor(tc_m); c.setFont(_F['CB'] if att_match else _F['C'], 7)
        c.drawString(rx_mid+3, y-row_h+5, att_desc[:40])

        # Right cell — coloured if punctuality category matches this row
        punc_match = (cat == punc_code)
        rx_punc = x + col_ws[0] + col_ws[1]
        bg_p = cat_col if punc_match else WHITE
        tc_p = WHITE if punc_match else DARK
        c.setFillColor(bg_p); c.setStrokeColor(MGREY); c.setLineWidth(0.3)
        c.rect(rx_punc, y-row_h, col_ws[2], row_h, fill=1, stroke=1)
        c.setFillColor(tc_p); c.setFont(_F['CB'] if punc_match else _F['C'], 7)
        c.drawString(rx_punc+3, y-row_h+5, punc_desc[:40])

        y -= row_h

# ── Main ───────────────────────────────────────────────────────────────────────
def generate_reports_pdf(class_data, settings, class_id, pat=None,
                         pupil_ids=None, lz_colour_hex='#1798d3'):
    _fonts()
    lz = colors.HexColor(lz_colour_hex)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A3))
    c.setTitle('Annual Reports to Families')

    pupils = sorted(class_data.get('pupils', []), key=lambda p: p['last_name'])
    if pupil_ids:
        pupils = [p for p in pupils if p['id'] in pupil_ids]

    for pupil in pupils:
        # PAGE 1: Front
        _front_left(c, lz, settings, class_id, pat)
        _front_right(c, lz, pupil, settings)
        _border(c, 0, lz)
        _border(c, 1, lz)
        c.showPage()

        # PAGE 2: Back
        _back_left(c, pupil, settings)
        _back_right(c, lz, pupil, settings, class_id, pat)
        _border(c, 0, lz)
        _border(c, 1, lz)
        c.showPage()

    c.save()
    buf.seek(0)
    return buf
