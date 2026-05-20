"""
Export class data to report-data.xlsx format.
Loads report_template.xlsx as the base (preserving the 'Set up Report' sheet
and its formulas for columns I and K), then populates the Data sheet.
"""
import io, os
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# ── Grade mapping ──────────────────────────────────────────────────────────────
GRADE_MAP = {
    'D':'D', 'GD':'D', 'O':'O', 'O1':'O', 'O2':'O', 'Y':'Y',
    'A - Y2':'A Y2', 'A - Y3':'A Y3', 'A - Y4':'A Y4', 'A - Y5':'A Y5',
}

def _grade(v): return GRADE_MAP.get(str(v or '').strip(), str(v or ''))


# ── Formulas for columns I and K (row-specific) ────────────────────────────────
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


# ── Locate the template ────────────────────────────────────────────────────────
def _template_path():
    sd = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(sd, 'data', 'static', 'report_template.xlsx'),
        os.path.join('/mount/src/wfa-reports/data/static', 'report_template.xlsx'),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


# ── Styles ─────────────────────────────────────────────────────────────────────
WRAP_ALIGN = Alignment(wrap_text=True, vertical='top')
TOP_ALIGN  = Alignment(vertical='top')
THIN       = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'),  bottom=Side(style='thin'),
)
STD_FONT   = Font(name='Calibri', size=10)
COL_WIDTHS = [16,14,18,24,8,8,8,14,18,20,18,60,60,60,60,60,60]


# ── Main export function ───────────────────────────────────────────────────────
def export_excel(class_data: dict, settings: dict = None) -> io.BytesIO:
    """
    Populate the report template with class data.
    Preserves the 'Set up Report' sheet and its formulas.
    Updates LZ name, year and teacher name from settings if provided.
    Returns BytesIO of the completed workbook.
    """
    settings = settings or {}
    pupils = sorted(
        class_data.get('pupils', []),
        key=lambda p: (p.get('last_name',''), p.get('first_name',''))
    )

    # Load template or create minimal fallback
    tpl = _template_path()
    if tpl:
        wb = openpyxl.load_workbook(tpl)
    else:
        wb = openpyxl.Workbook()
        wb.active.title = 'Data'

    # ── Populate Data sheet ────────────────────────────────────────────────────
    ws = wb['Data'] if 'Data' in wb.sheetnames else wb.active

    # Clear existing data rows (keep rows 1 and 2 — notes and headers)
    for row in range(3, ws.max_row + 1):
        for col in range(1, 18):
            ws.cell(row, col).value = None

    # Write pupil rows
    for ri, pupil in enumerate(pupils, start=3):
        fn        = (pupil.get('first_name') or '').strip()
        ln        = (pupil.get('last_name')  or '').strip()
        grades    = pupil.get('grades', {})
        coms      = pupil.get('comments', {})
        att_raw   = str(pupil.get('attendance')  or '').strip()
        lates_raw = str(pupil.get('punctuality') or '').strip()

        # Convert lates to int if possible
        try:    lates_val = int(lates_raw)
        except: lates_val = None if not lates_raw else lates_raw

        row_data = {
            1:  f"ch{ri-2:02d}",
            2:  fn,
            3:  ln,
            4:  f"{fn} {ln}".strip(),
            5:  _grade(grades.get('R','')),
            6:  _grade(grades.get('W','')),
            7:  _grade(grades.get('M','')),
            8:  float(att_raw) if att_raw else None,
            9:  _att_formula(ri),          # formula — keeps link to Set up Report
            10: lates_val,
            11: _punc_formula(ri),         # formula — keeps link to Set up Report
            12: coms.get('reader','')        or '',
            13: coms.get('writer','')        or '',
            14: coms.get('mathematician','') or '',
            15: coms.get('learner_21c','')   or '',
            16: coms.get('rights','')        or '',
            17: (pupil.get('pupil_voice') or '').strip(),
        }

        for col, value in row_data.items():
            cell = ws.cell(row=ri, column=col, value=value)
            cell.font   = STD_FONT
            cell.border = THIN
            cell.alignment = WRAP_ALIGN if col >= 12 else TOP_ALIGN

        ws.row_dimensions[ri].height = 80

    # Column widths
    for ci, w in enumerate(COL_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    ws.freeze_panes = 'A3'

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
