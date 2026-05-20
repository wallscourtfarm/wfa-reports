"""
Export class data to report-data.xlsx format.
Uses ZIP-level surgery: copies the template verbatim, then replaces only
the Data sheet XML. This preserves drawings, images and the Set up Report
sheet exactly as they were — openpyxl cannot safely round-trip embedded
images, so we never let it touch those parts.
"""
import io
import os
import re
import zipfile
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


# ── Build the Data sheet bytes using a standalone workbook ────────────────────
WRAP_ALIGN = Alignment(wrap_text=True, vertical='top')
TOP_ALIGN  = Alignment(vertical='top')
THIN       = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'),  bottom=Side(style='thin'),
)
STD_FONT   = Font(name='Calibri', size=10)
COL_WIDTHS = [16,14,18,24,8,8,8,14,18,20,18,60,60,60,60,60,60]


def _build_data_sheet_xml(pupils: list) -> bytes:
    """
    Build a minimal workbook containing only the Data sheet,
    then extract and return its sheet XML bytes.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Data'

    # Row 1 — notes (matching template)
    ws.cell(1, 2).value = 'Copy Paste from DOOYA\t\t'
    ws.cell(1, 5).value = 'Copy Paste from DOOYA'
    ws.cell(1, 8).value = 'copy-paste from Welcome Zone Report'
    ws.cell(1, 10).value = 'copy-paste from Welcome Zone Report'

    # Row 2 — headers
    headers = [
        'ID', 'First Name', 'Last Name', 'Full Name',
        'R', 'W', 'M',
        'Attendance', 'Att Code', 'Punctuality (Lates) #', 'Punc Code',
        'Reader Teacher comments', 'Writer Teacher comments',
        'Mathematician Teacher comments', '21st C learner Teacher comments',
        'Rights and Responsibilities Teacher comments', 'Pupil Voice',
    ]
    for ci, h in enumerate(headers, 1):
        cell = ws.cell(2, ci, value=h)
        cell.font = Font(name='Calibri', size=10, bold=True)

    # Data rows
    for ri, pupil in enumerate(pupils, start=3):
        fn        = (pupil.get('first_name') or '').strip()
        ln        = (pupil.get('last_name')  or '').strip()
        grades    = pupil.get('grades', {})
        coms      = pupil.get('comments', {})
        att_raw   = str(pupil.get('attendance')  or '').strip()
        lates_raw = str(pupil.get('punctuality') or '').strip()

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
            9:  _att_formula(ri),
            10: lates_val,
            11: _punc_formula(ri),
            12: coms.get('reader','')        or '',
            13: coms.get('writer','')        or '',
            14: coms.get('mathematician','') or '',
            15: coms.get('learner_21c','')   or '',
            16: coms.get('rights','')        or '',
            17: (pupil.get('pupil_voice') or '').strip(),
        }

        for col, value in row_data.items():
            cell = ws.cell(row=ri, column=col, value=value)
            cell.font      = STD_FONT
            cell.border    = THIN
            cell.alignment = WRAP_ALIGN if col >= 12 else TOP_ALIGN

        ws.row_dimensions[ri].height = 80

    for ci, w in enumerate(COL_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    ws.freeze_panes = 'A3'

    # Save to memory and extract the sheet XML
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        return zf.read('xl/worksheets/sheet1.xml')


# ── Main export: ZIP-level surgery ─────────────────────────────────────────────
def export_excel(class_data: dict, settings: dict = None) -> io.BytesIO:
    """
    Produce report-data.xlsx by:
    1. Reading the template ZIP verbatim
    2. Replacing only the Data sheet XML with freshly generated content
    3. Leaving every other file (Set up Report, drawings, images, rels) untouched
    """
    settings = settings or {}
    pupils = sorted(
        class_data.get('pupils', []),
        key=lambda p: (p.get('last_name',''), p.get('first_name',''))
    )

    tpl = _template_path()

    # If no template, fall back to pure openpyxl (no images to preserve)
    if not tpl:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Data'
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    # Build the replacement Data sheet XML
    data_sheet_xml = _build_data_sheet_xml(pupils)

    # Find which zip entry is the Data sheet in the template
    with open(tpl, 'rb') as f:
        tpl_bytes = f.read()

    with zipfile.ZipFile(io.BytesIO(tpl_bytes)) as tpl_zip:
        # Identify the Data sheet path from workbook.xml
        wb_xml = tpl_zip.read('xl/workbook.xml').decode('utf-8')
        # Find sheet named 'Data' and its r:id
        # e.g. <sheet name="Data" sheetId="2" r:id="rId2"/>
        match = re.search(r'<sheet[^>]+name=["\']Data["\'][^>]+r:id=["\'](\w+)["\']', wb_xml)
        if not match:
            match = re.search(r'<sheet[^>]+r:id=["\'](\w+)["\'][^>]+name=["\']Data["\']', wb_xml)

        # Find the sheet file from workbook rels
        wb_rels = tpl_zip.read('xl/_rels/workbook.xml.rels').decode('utf-8')
        if match:
            rid = match.group(1)
            rel_match = re.search(
                rf'<Relationship[^>]+Id=["\']' + re.escape(rid) + r'["\'][^>]+Target=["\']([^"\']+)["\']',
                wb_rels
            )
            data_sheet_path = 'xl/' + rel_match.group(1).lstrip('/').replace('xl/', '') if rel_match else 'xl/worksheets/sheet2.xml'
        else:
            # Fallback: assume sheet2
            data_sheet_path = 'xl/worksheets/sheet2.xml'

        # Build output ZIP: copy everything, replace only the Data sheet
        out_buf = io.BytesIO()
        with zipfile.ZipFile(out_buf, 'w', compression=zipfile.ZIP_DEFLATED) as out_zip:
            for item in tpl_zip.infolist():
                if item.filename == data_sheet_path:
                    out_zip.writestr(item.filename, data_sheet_xml)
                else:
                    out_zip.writestr(item, tpl_zip.read(item.filename))

    out_buf.seek(0)
    return out_buf
