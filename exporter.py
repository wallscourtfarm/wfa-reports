"""
Export class data to report-data.xlsx.
Generates a clean two-sheet workbook from scratch — no template copying,
no style ID conflicts, no calcChain, no drawings.
Sheet 1: Set up Report (threshold values preserved from original template)
Sheet 2: Data
"""
import io
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

# ── Grade mapping ──────────────────────────────────────────────────────────────
GRADE_MAP = {
    'D':'D', 'GD':'D', 'O':'O', 'O1':'O', 'O2':'O', 'Y':'Y',
    'A - Y2':'A Y2', 'A - Y3':'A Y3', 'A - Y4':'A Y4', 'A - Y5':'A Y5',
}
def _grade(v): return GRADE_MAP.get(str(v or '').strip(), str(v or ''))

# ── Formulas (row-specific) ────────────────────────────────────────────────────
def _att_formula(row):
    r = str(row)
    return (f"=IF(H{r}>='Set up Report'!$B$46,\"A\","
            f"IF(H{r}>='Set up Report'!$B$47,\"B\","
            f"IF(H{r}<'Set up Report'!$B$49,\"D\",\"C\")))")

def _punc_formula(row):
    r = str(row)
    return (f"=IF(AND(J{r}='Set up Report'!$C$46),\"A\","
            f"IF(AND(J{r}<='Set up Report'!$C$47),\"B\","
            f"IF(AND(J{r}<='Set up Report'!$C$48),\"C\","
            f"IF(AND(J{r}>'Set up Report'!$C$48),\"D\"))))")

# ── Styles ─────────────────────────────────────────────────────────────────────
THIN     = Border(left=Side(style='thin'), right=Side(style='thin'),
                  top=Side(style='thin'),  bottom=Side(style='thin'))
WRAP     = Alignment(wrap_text=True, vertical='top')
TOP      = Alignment(vertical='top')
BODY     = Font(name='Calibri', size=10, bold=False)
HDR_FONT = Font(name='Calibri', size=10, bold=True, color='FFFFFF')
HDR_FILL = PatternFill('solid', fgColor='1798D3')
HDR_ALIGN = Alignment(horizontal='center', vertical='center', wrap_text=True)

WIDTHS  = [16, 14, 18, 24, 8, 8, 8, 14, 18, 20, 18, 60, 60, 60, 60, 60, 60]
HEADERS = [
    'ID', 'First Name', 'Last Name', 'Full Name',
    'R', 'W', 'M',
    'Attendance', 'Att Code', 'Punctuality (Lates) #', 'Punc Code',
    'Reader Teacher comments', 'Writer Teacher comments',
    'Mathematician Teacher comments', '21st C learner Teacher comments',
    'Rights and Responsibilities Teacher comments', 'Pupil Voice',
]


def _build_setup_sheet(wb):
    """
    Recreates the Set up Report thresholds exactly as in the original template.
    Cells B46:B49 = attendance thresholds; C46:C48 = lates thresholds.
    These are referenced by the formulas in the Data sheet columns I and K.
    """
    ws = wb.create_sheet('Set up Report', 0)
    label_font = Font(name='Calibri', size=10)

    ws['A1'] = 'Attendance and punctuality thresholds — do not edit'
    ws['A1'].font = Font(name='Calibri', size=10, bold=True)
    ws['A44'] = 'Attendance'
    ws['B44'] = '% threshold'
    ws['C44'] = 'Lates threshold'
    for cell in ['A44', 'B44', 'C44']:
        ws[cell].font = Font(name='Calibri', size=10, bold=True)

    # Attendance % thresholds (cols A label, B value)
    att_rows = [
        (45, 'Header row', None, None),
        (46, 'Exceptional',     99, 0),   # B46=99, C46=0
        (47, 'Expected',        96, 2),   # B47=96, C47=2
        (48, 'Below Expected',  96, 7),   # B48=96, C48=7
        (49, 'Cause for Concern', 90, 8), # B49=90, C49=8
    ]
    for row, label, att_val, lates_val in att_rows:
        ws[f'A{row}'] = label
        ws[f'A{row}'].font = label_font
        if att_val is not None:
            ws[f'B{row}'] = att_val
            ws[f'B{row}'].font = label_font
        if lates_val is not None:
            ws[f'C{row}'] = lates_val
            ws[f'C{row}'].font = label_font

    ws.sheet_state = 'hidden'


def _build_data_sheet(wb, pupils):
    ws = wb.create_sheet('Data')

    # Row 1 — instruction notes
    for col, note in [
        (2,  'Copy Paste from DOOYA\t\t'),
        (5,  'Copy Paste from DOOYA'),
        (8,  'copy-paste from Welcome Zone Report'),
        (10, 'copy-paste from Welcome Zone Report'),
    ]:
        c = ws.cell(1, col, value=note)
        c.font = Font(name='Calibri', size=9, italic=True, color='888888')

    # Row 2 — headers
    for ci, h in enumerate(HEADERS, 1):
        c = ws.cell(2, ci, value=h)
        c.font      = HDR_FONT
        c.fill      = HDR_FILL
        c.border    = THIN
        c.alignment = HDR_ALIGN
    ws.row_dimensions[2].height = 28

    # Data rows
    for ri, pupil in enumerate(pupils, start=3):
        fn     = (pupil.get('first_name') or '').strip()
        ln     = (pupil.get('last_name')  or '').strip()
        grades = pupil.get('grades', {})
        coms   = pupil.get('comments', {})
        att    = str(pupil.get('attendance')  or '').strip()
        lates  = str(pupil.get('punctuality') or '').strip()

        try:    lates_v = int(lates)
        except: lates_v = None if not lates else lates

        row = {
            1:  f'ch{ri-2:02d}',
            2:  fn,
            3:  ln,
            4:  f'{fn} {ln}'.strip(),
            5:  _grade(grades.get('R', '')),
            6:  _grade(grades.get('W', '')),
            7:  _grade(grades.get('M', '')),
            8:  float(att) if att else None,
            9:  _att_formula(ri),
            10: lates_v,
            11: _punc_formula(ri),
            12: coms.get('reader', '')        or '',
            13: coms.get('writer', '')        or '',
            14: coms.get('mathematician', '') or '',
            15: coms.get('learner_21c', '')   or '',
            16: coms.get('rights', '')        or '',
            17: (pupil.get('pupil_voice') or '').strip(),
        }

        for col, val in row.items():
            c = ws.cell(row=ri, column=col, value=val)
            c.font      = BODY
            c.border    = THIN
            c.alignment = WRAP if col >= 12 else TOP

        ws.row_dimensions[ri].height = 80

    for ci, w in enumerate(WIDTHS, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    ws.freeze_panes = 'A3'


def export_excel(class_data: dict, settings: dict = None) -> io.BytesIO:
    pupils = sorted(
        class_data.get('pupils', []),
        key=lambda p: (p.get('last_name', ''), p.get('first_name', ''))
    )

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove default blank sheet

    _build_setup_sheet(wb)
    _build_data_sheet(wb, pupils)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
