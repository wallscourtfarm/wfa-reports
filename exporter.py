"""
Export class data to report-data.xlsx format for use with the school's print workflow.
Matches the column structure of the existing report-data.xlsx template exactly.
"""
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# ── Grade mapping: app format → Excel format ───────────────────────────────────
GRADE_MAP = {
    'D':      'D',
    'GD':     'D',
    'O':      'O',
    'O1':     'O',
    'O2':     'O',
    'Y':      'Y',
    'A - Y2': 'A Y2',
    'A - Y3': 'A Y3',
    'A - Y4': 'A Y4',
    'A - Y5': 'A Y5',
}


def _grade(raw):
    return GRADE_MAP.get(str(raw or '').strip(), str(raw or ''))


def _att_code(pct_str):
    try:
        v = float(str(pct_str or '').replace('%', '').strip())
        if v >= 99: return 'Exceptional'
        if v >= 96: return 'Expected'
        if v >= 90: return 'Below Expected'
        return 'Cause for Concern'
    except (ValueError, TypeError):
        return ''


def _punc_code(lates_str):
    try:
        n = int(str(lates_str or '').strip())
        if n == 0:  return 'Exceptional'
        if n <= 5:  return 'Expected'
        if n <= 15: return 'Below Expected'
        return 'Cause for Concern'
    except (ValueError, TypeError):
        return ''


# ── Column definitions (matches report-data.xlsx exactly) ─────────────────────
COLUMNS = [
    ('ID',                                        16),
    ('First Name',                                14),
    ('Last Name',                                 18),
    ('Full Name',                                 24),
    ('R',                                          8),
    ('W',                                          8),
    ('M',                                          8),
    ('Attendance',                                14),
    ('Att Code',                                  18),
    ('Punctuality (Lates) #',                     20),
    ('Punc Code',                                 18),
    ('Reader Teacher comments',                   60),
    ('Writer Teacher comments',                   60),
    ('Mathematician Teacher comments',            60),
    ('21st C learner Teacher comments',           60),
    ('Rights and Responsibilities Teacher comments', 60),
    ('Pupil Voice',                               60),
]

HEADERS = [col for col, _ in COLUMNS]
WIDTHS  = [w   for _, w  in COLUMNS]

# Colour palette
HDR_FILL  = PatternFill('solid', start_color='1798D3')  # WFA blue
HDR_FONT  = Font(name='Calibri', bold=True, color='FFFFFF', size=10)
BOLD_FONT = Font(name='Calibri', bold=True, size=10)
STD_FONT  = Font(name='Calibri', size=10)
WRAP_ALIGN = Alignment(wrap_text=True, vertical='top')
CTR_ALIGN  = Alignment(horizontal='center', vertical='center')
THIN_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'),  bottom=Side(style='thin'),
)


def _cell(ws, row, col, value, font=None, fill=None, align=None, border=None):
    cell = ws.cell(row=row, column=col, value=value)
    if font:   cell.font   = font
    if fill:   cell.fill   = fill
    if align:  cell.alignment = align
    if border: cell.border = border
    return cell


def export_excel(class_data: dict) -> io.BytesIO:
    """
    Build the report-data.xlsx output from class_data.
    Returns BytesIO ready for st.download_button.
    """
    pupils = sorted(
        class_data.get('pupils', []),
        key=lambda p: (p.get('last_name', ''), p.get('first_name', ''))
    )

    wb = Workbook()
    ws = wb.active
    ws.title = 'Data'

    # ── Row 1: source notes (matches original template row 1) ─────────────────
    ws.cell(1, 2, 'WFA Reports Manager export').font = Font(name='Calibri', italic=True,
                                                            color='888888', size=9)

    # ── Row 2: column headers ──────────────────────────────────────────────────
    for ci, header in enumerate(HEADERS, start=1):
        _cell(ws, 2, ci, header,
              font=HDR_FONT, fill=HDR_FILL,
              align=CTR_ALIGN, border=THIN_BORDER)

    # ── Rows 3+: one row per pupil ─────────────────────────────────────────────
    for ri, pupil in enumerate(pupils, start=3):
        pid       = f"ch{ri-2:02d}"
        fn        = (pupil.get('first_name') or '').strip()
        ln        = (pupil.get('last_name')  or '').strip()
        full      = f"{fn} {ln}".strip()
        grades    = pupil.get('grades', {})
        coms      = pupil.get('comments', {})
        att_raw   = str(pupil.get('attendance')  or '')
        lates_raw = str(pupil.get('punctuality') or '')

        row_data = [
            pid,
            fn,
            ln,
            full,
            _grade(grades.get('R', '')),
            _grade(grades.get('W', '')),
            _grade(grades.get('M', '')),
            att_raw   if att_raw   else None,
            pupil.get('att_code')  or _att_code(att_raw),
            int(lates_raw) if lates_raw.isdigit() else (None if not lates_raw else lates_raw),
            pupil.get('punc_code') or _punc_code(lates_raw),
            coms.get('reader',        '') or '',
            coms.get('writer',        '') or '',
            coms.get('mathematician', '') or '',
            coms.get('learner_21c',   '') or '',
            coms.get('rights',        '') or '',
            (pupil.get('pupil_voice') or '').strip(),
        ]

        for ci, value in enumerate(row_data, start=1):
            is_comment = ci >= 12   # comment columns need wrapping
            _cell(ws, ri, ci, value,
                  font=STD_FONT,
                  align=WRAP_ALIGN if is_comment else Alignment(vertical='center'),
                  border=THIN_BORDER)

        # Row height — tall enough for wrapped comment text
        ws.row_dimensions[ri].height = 80

    # ── Column widths ──────────────────────────────────────────────────────────
    for ci, width in enumerate(WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(ci)].width = width

    # Freeze the header row
    ws.freeze_panes = 'A3'

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
