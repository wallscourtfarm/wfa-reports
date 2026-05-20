import streamlit as st
import requests
import time
from importer import import_from_files
from generator import generate_comments, word_count
from exporter import export_excel
from report_builder import generate_reports_pdf
from pupil_voice_importer import process_forms_export, build_output_excel
from data_manager import (
    list_classes, load_class, save_class,
    save_photo, photo_raw_url,
    load_settings, save_settings,
)

# ── Palette ────────────────────────────────────────────────────────────────────
BLUE  = "#1798d3"
NAVY  = "#0E2841"
GOLD  = "#FFC000"
GREEN = "#C6EFCE"
AMBER = "#FFEB9C"
RED   = "#FFCCCC"
LTBLUE= "#9DC3E6"

# ── Feature flags ─────────────────────────────────────────────────────────────
SHOW_ADVANCED = False  # Set True to restore PDF generation, photos and attendance

# ── Score sections + field definitions ─────────────────────────────────────────
SCORE_SECTIONS = [
    ("21st Century Learner", "🎓", [
        ("char",   "Character"),
        ("randr",  "Rights & Responsibilities"),
        ("effort", "Effort"),
        ("oracy",  "Oracy"),
        ("curio",  "Curiosity"),
        ("resil",  "Resilience"),
        ("indep",  "Independence"),
        ("collab", "Collaboration"),
    ]),
    ("Subject Engagement", "📚", [
        ("hist",  "History"),
        ("geog",  "Geography"),
        ("sci",   "Science"),
        ("art",   "Art"),
        ("ath",   "Sport / PE"),
        ("cit",   "Citizenship"),
        ("cs",    "Computing"),
        ("des",   "Design"),
        ("ling",  "Spanish"),
        ("mus",   "Music"),
    ]),
    ("Reading", "📖", [
        ("read_e",      "Love of reading"),
        ("r_fluency",   "Fluency"),
        ("r_retrieval", "Retrieval"),
        ("r_inference", "Inference"),
        ("r_vocab",     "Vocabulary"),
    ]),
    ("Writing", "✏️", [
        ("write_s",  "Writing — overall"),
        ("w_comp",   "Composition"),
        ("w_spell",  "Spelling"),
        ("w_punct",  "Punctuation & grammar"),
        ("w_vocab",  "Vocabulary"),
        ("w_hand",   "Handwriting"),
        ("w_fic",    "Fiction"),
        ("w_nonfic", "Non-fiction"),
    ]),
    ("Maths", "🔢", [
        ("math_s",   "Maths — overall"),
        ("tt",       "Times tables"),
        ("m_calc",   "Written calculation"),
        ("m_reason", "Reasoning"),
        ("m_prob",   "Problem solving"),
        ("m_frac",   "Fractions & decimals"),
    ]),
]

ALL_SCORE_KEYS = [k for _, _, fields in SCORE_SECTIONS for k, _ in fields]

GRADE_OPTIONS = ["D", "O1", "O2", "Y", "A - Y2", "A - Y3"]
GRADE_LABELS  = {
    "D":      "GD — Greater Depth",
    "O1":     "O  — Securely on track",
    "O2":     "O  — Approaching on track",
    "Y":      "Y  — Yet to meet",
    "A - Y2": "A  — Working at Y2 level",
    "A - Y3": "A  — Working at Y3 level",
}
GRADE_DISPLAY = {"D":"GD","O1":"O","O2":"O","Y":"Y","A - Y2":"A-2","A - Y3":"A-3"}
GRADE_COLOUR  = {
    "D": LTBLUE, "O1": GREEN, "O2": GREEN,
    "Y": AMBER,  "A - Y2": RED, "A - Y3": RED,
}

POS_FLAGS = [
    ("effort",            "Strong effort / work ethic"),
    ("active_engagement", "Active engagement"),
    ("stamina_high",      "Strong stamina"),
    ("focus_high",        "Strong focus"),
    ("drive",             "Drive / determination"),
]
NEG_FLAGS = [
    ("able_not_engaged",  "Able but not always engaged"),
    ("anxiety",           "Anxiety"),
    ("low_engagement",    "Low engagement"),
    ("SEN_selective",     "SEN — selective engagement"),
    ("quiet",             "Quiet / low oracy"),
    ("low_effort",        "Low effort"),
    ("passive",           "Passive learner"),
    ("stamina_low",       "Low stamina"),
    ("presentation",      "Presentation issues"),
]
POS_KEYS  = [k for k, _ in POS_FLAGS]
NEG_KEYS  = [k for k, _ in NEG_FLAGS]
ALL_FLAG_LABELS = {k: lbl for k, lbl in POS_FLAGS + NEG_FLAGS}

def _to_list(v):
    """Migrate legacy string special field to list."""
    if isinstance(v, list): return v
    return [v] if v else []
SCORE_FMT = {None: "—  not scored", 1: "1 · Emerging", 2: "2 · Developing", 3: "3 · Strong"}

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="WFA Reports", page_icon="📋", layout="wide")

st.markdown(f"""
<style>
  .block-container {{ padding-top: 1rem; max-width: 1200px; }}
  h1,h2,h3 {{ color: {NAVY}; }}
  .stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 2px solid {BLUE}; }}
  .stTabs [data-baseweb="tab"] {{
    background: #f0f6fc; border-radius: 6px 6px 0 0;
    padding: 8px 22px; font-weight: 600; color: {NAVY};
  }}
  .stTabs [aria-selected="true"] {{ background: {BLUE}; color: white; }}
  div[data-testid="stExpander"] > div:first-child {{
    background: #f8fafc; border-radius: 6px;
  }}
  .badge {{
    display: inline-block; border-radius: 4px;
    padding: 1px 8px; font-size: 12px; font-weight: 700;
    font-family: monospace;
  }}
  .row-link button {{ text-align: left !important; font-weight: 500; }}
  small {{ color: #64748b; }}
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(
    f'''<div style="display:flex;align-items:center;gap:14px;padding-bottom:12px;border-bottom:3px solid {BLUE};margin-bottom:8px;">
      <span style="background:{BLUE};color:white;font-weight:900;font-size:17px;padding:6px 13px;border-radius:6px;">WFA</span>
      <span style="color:{NAVY};font-weight:700;font-size:24px;">Report Manager</span>
    </div>''',
    unsafe_allow_html=True,
)

# ── Class selector ─────────────────────────────────────────────────────────────
classes = list_classes()
if not classes:
    classes = ["Y4_IM"]

class_id = st.selectbox(
    "Class", options=classes,
    format_func=lambda x: x.replace("_", " — "),
)

# ── Load class data ────────────────────────────────────────────────────────────
if ("cd" not in st.session_state or st.session_state.get("_cls") != class_id):
    raw = load_class(class_id)
    st.session_state.cd = raw or {"class_id": class_id, "pupils": []}
    st.session_state._cls = class_id

cd     = st.session_state.cd
pupils = cd.get("pupils", [])
p_map  = {p["id"]: p for p in pupils}


# ── Helpers ────────────────────────────────────────────────────────────────────
def scored(p):
    return sum(1 for k in ALL_SCORE_KEYS if p.get("scores", {}).get(k) is not None)

def badge_html(grade):
    g = GRADE_DISPLAY.get(grade, grade)
    c = GRADE_COLOUR.get(grade, "#e2e8f0")
    return f'<span class="badge" style="background:{c};">{g}</span>'

def save_and_confirm():
    ok = save_class(class_id, cd)
    st.toast("Saved ✓" if ok else "Save failed — check GitHub token",
             icon="✅" if ok else "❌")

def get_sel():
    return st.session_state.get("sel_id")

def set_sel(pid):
    st.session_state.sel_id = pid


# ── Tabs ───────────────────────────────────────────────────────────────────────
NAV_PAGES = ["👥 Pupils", "📋 Score", "💬 Comments", "✍️ Generate", "📥 Pupil Voice", "⚙️ Settings"] if not SHOW_ADVANCED else ["👥 Pupils", "📋 Score", "💬 Comments", "✍️ Generate", "📸 Photos", "📥 Pupil Voice", "⚙️ Settings"]
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "👥 Pupils"

# Resolve any pending programmatic navigation before the widget renders
if st.session_state.get("_nav_goto"):
    st.session_state.nav_page = st.session_state.pop("_nav_goto")

nav = st.radio(
    "nav", NAV_PAGES, horizontal=True,
    key="nav_page", label_visibility="collapsed"
)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  PUPILS TAB                                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
if nav == "👥 Pupils":

    # ── Import panel ──────────────────────────────────────────────────────────
    with st.expander("📥 Import from Excel", expanded=not pupils):
        st.markdown(
            "Upload your **output Excel** (the file from a previous run — sheet: *Data*) "
            "to pre-populate names, grades and existing comments. "
            "Optionally also upload the **input template** (sheet: *Pupil Data*) "
            "to import the 1–3 scores."
        )
        st.caption(
            "Note: the output Excel stores O1 and O2 both as 'O', so all "
            "'on track' grades will import as O1. You can correct them in the Score tab."
        )
        out_f = st.file_uploader("Previous reports Excel — IM_Y4_Reports_2025-26.xlsx", type=["xlsx"], key="imp_out")
        in_f  = st.file_uploader("Scores template — Y4_Reports_Input_Template.xlsx (optional)", type=["xlsx"], key="imp_in")

        if st.button("Import", type="primary", key="do_import"):
            if out_f is None:
                st.warning("Upload the output Excel first.")
            else:
                with st.spinner("Importing…"):
                    merged = import_from_files(
                        output_bytes=out_f.read() if out_f else None,
                        input_bytes=in_f.read()  if in_f  else None,
                        existing=pupils,
                    )
                cd["pupils"] = merged
                st.session_state.cd = cd
                save_and_confirm()
                st.rerun()

    # ── Pupil list ────────────────────────────────────────────────────────────
    total_score_fields = len(ALL_SCORE_KEYS)
    sorted_pupils = sorted(pupils, key=lambda p: p["last_name"])

    if sorted_pupils:
        st.markdown(f"**{len(sorted_pupils)} pupils**")
        st.markdown("---")

        hcols = st.columns([5, 1, 1, 1, 3, 1] if SHOW_ADVANCED else [5, 1, 1, 1, 3])
        labels = ["Name", "R", "W", "M", "Scored", "Photo"] if SHOW_ADVANCED else ["Name", "R", "W", "M", "Scored"]
        for c, lbl in zip(hcols, labels):
            c.markdown(f"<small><b>{lbl}</b></small>", unsafe_allow_html=True)

        for p in sorted_pupils:
            cols = st.columns([5, 1, 1, 1, 3, 1] if SHOW_ADVANCED else [5, 1, 1, 1, 3])

            with cols[0]:
                btn_col, name_col = st.columns([1, 8])
                with btn_col:
                    if st.button("📋", key=f"sel_{p['id']}", help="Open in Score tab"):
                        set_sel(p["id"])
                        st.session_state._nav_goto = "📋 Score"
                        st.rerun()
                with name_col:
                    st.markdown(f"<div style='padding-top:6px;'>{p['first_name']} {p['last_name']}</div>",
                                unsafe_allow_html=True)

            for ci, g in enumerate(["R", "W", "M"], 1):
                with cols[ci]:
                    st.markdown(badge_html(p["grades"].get(g, "O1")),
                                unsafe_allow_html=True)

            sc  = scored(p)
            pct = int(sc / total_score_fields * 100) if total_score_fields else 0
            bar_col = "#22c55e" if pct == 100 else "#f59e0b" if pct > 0 else "#e5e7eb"
            with cols[4]:
                st.markdown(
                    f'<div style="background:#f1f5f9;border-radius:4px;height:8px;margin-top:16px;">'
                    f'<div style="background:{bar_col};width:{pct}%;height:8px;border-radius:4px;"></div>'
                    f'</div><small>{sc}/{total_score_fields} fields scored</small>',
                    unsafe_allow_html=True,
                )

            if SHOW_ADVANCED:
                with cols[5]:
                    url = photo_raw_url(class_id, p.get("photo", ""))
                    try:
                        r = requests.head(url, timeout=2)
                        has = r.status_code == 200
                    except Exception:
                        has = False
                    st.markdown("✅" if has else "❌")
    else:
        st.info("No pupils yet. Use the Import panel above to get started.")


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SCORE TAB                                                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
if nav == "📋 Score":
    if not pupils:
        st.info("Import pupils first from the Pupils tab.")
        st.stop()

    sorted_pupils = sorted(pupils, key=lambda p: p["last_name"])
    sorted_ids    = [p["id"] for p in sorted_pupils]

    pid = get_sel()
    if pid not in sorted_ids:
        pid = sorted_ids[0]
        set_sel(pid)

    idx = sorted_ids.index(pid)

    # ── Navigation ────────────────────────────────────────────────────────────
    nc1, nc2, nc3 = st.columns([1, 5, 1])
    with nc1:
        if st.button("← Prev", disabled=(idx == 0)):
            set_sel(sorted_ids[idx - 1])
            st.rerun()
    with nc2:
        new_pid = st.selectbox(
            "Pupil",
            options=sorted_ids,
            format_func=lambda x: p_map[x]["full_name"],
            index=idx,
            label_visibility="collapsed",
        )
        if new_pid != pid:
            set_sel(new_pid)
            st.rerun()
    with nc3:
        if st.button("Next →", disabled=(idx == len(sorted_ids) - 1)):
            set_sel(sorted_ids[idx + 1])
            st.rerun()

    p = p_map[pid]
    scores = p.setdefault("scores", {})

    sc = scored(p)
    pct = int(sc / len(ALL_SCORE_KEYS) * 100)
    bar_col = "#22c55e" if pct == 100 else "#f59e0b" if pct > 0 else "#e5e7eb"

    st.markdown(
        f'<h3 style="margin-bottom:4px;">{p["first_name"]} {p["last_name"]}</h3>'
        f'<div style="background:#f1f5f9;border-radius:6px;height:10px;margin-bottom:8px;">'
        f'<div style="background:{bar_col};width:{pct}%;height:10px;border-radius:6px;"></div>'
        f'</div><small style="color:#64748b;">{sc}/{len(ALL_SCORE_KEYS)} fields scored</small>',
        unsafe_allow_html=True,
    )

    # ── Basics ────────────────────────────────────────────────────────────────
    with st.expander("📊 Grades & basics", expanded=True):
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            p["gender"] = st.radio(
                "Gender", ["M", "F"],
                index=0 if p.get("gender", "M") == "M" else 1,
                horizontal=True, key=f"gender_{pid}",
            )
        for col, subj, key in zip([b2, b3, b4], ["Reading", "Writing", "Maths"], ["R", "W", "M"]):
            with col:
                cur = p["grades"].get(key, "O1")
                if cur not in GRADE_OPTIONS:
                    cur = "O1"
                p["grades"][key] = st.selectbox(
                    subj, options=GRADE_OPTIONS,
                    index=GRADE_OPTIONS.index(cur),
                    format_func=lambda x: GRADE_LABELS[x],
                    key=f"gr_{key}_{pid}",
                )

        t1, t2 = st.columns(2)
        with t1:
            p["other"] = st.text_input(
                "Positive quality", value=p.get("other", ""),
                placeholder="e.g. helpful / humour / kind / driven / calm / vocabulary",
                key=f"other_{pid}",
            )
        with t2:
            cur_flags = _to_list(p.get("special", []))
            fc1, fc2 = st.columns(2)
            with fc1:
                st.caption("✅ Positive")
                pos_sel = st.multiselect(
                    "Positive flags", options=POS_KEYS,
                    default=[f for f in cur_flags if f in POS_KEYS],
                    format_func=lambda x: ALL_FLAG_LABELS.get(x, x),
                    key=f"pos_flags_{pid}", label_visibility="collapsed",
                )
            with fc2:
                st.caption("⚠️ Challenges")
                neg_sel = st.multiselect(
                    "Challenge flags", options=NEG_KEYS,
                    default=[f for f in cur_flags if f in NEG_KEYS],
                    format_func=lambda x: ALL_FLAG_LABELS.get(x, x),
                    key=f"neg_flags_{pid}", label_visibility="collapsed",
                )
            p["special"] = pos_sel + neg_sel

    # ── Score sections ────────────────────────────────────────────────────────
    def score_widget(label, key, pupil_id):
        val  = scores.get(key)
        opts = [None, 1, 2, 3]
        idx_ = opts.index(val) if val in opts else 0
        new  = st.selectbox(
            label, options=opts,
            format_func=lambda x: SCORE_FMT[x],
            index=idx_, key=f"sc_{key}_{pupil_id}",
            label_visibility="visible",
        )
        scores[key] = new

    for section_name, icon, fields in SCORE_SECTIONS:
        n_scored   = sum(1 for k, _ in fields if scores.get(k) is not None)
        all_scored = n_scored == len(fields)
        header     = f"{icon} {section_name} — {n_scored}/{len(fields)}"

        with st.expander(header, expanded=not all_scored):
            ncols = 4 if len(fields) >= 8 else 3
            cols  = st.columns(ncols)
            for i, (key, label) in enumerate(fields):
                with cols[i % ncols]:
                    score_widget(label, key, pid)

    # ── Attendance & pupil voice ───────────────────────────────────────────────
    def _att_cat(v):
        try:
            pct = float(str(v).replace("%","").strip())
            if pct >= 99: return "Exceptional"
            if pct >= 96: return "Expected"
            if pct >= 90: return "Below Expected"
            return "Cause for Concern"
        except: return ""

    def _punc_cat(v):
        try:
            n = int(str(v).strip())
            if n == 0:  return "Exceptional"
            if n <= 5:  return "Expected"
            if n <= 15: return "Below Expected"
            return "Cause for Concern"
        except: return ""

    with st.expander("📝 Attendance & pupil voice") if SHOW_ADVANCED else st.expander("📝 Pupil voice", expanded=True):
        if SHOW_ADVANCED:
            a1, a2, a3, a4 = st.columns(4)
            with a1:
                att_val = st.text_input("Attendance %",
                    value=p.get("attendance",""), key=f"att_{pid}", placeholder="e.g. 97.4")
                p["attendance"] = att_val
            with a2:
                auto_att = _att_cat(att_val)
                if auto_att:
                    p["att_code"] = auto_att
                    st.markdown(f"<small>→ **{auto_att}**</small>", unsafe_allow_html=True)
                else:
                    cats = ["","Exceptional","Expected","Below Expected","Cause for Concern"]
                    ac = p.get("att_code","")
                    p["att_code"] = st.selectbox("Att category", cats,
                        index=cats.index(ac) if ac in cats else 0, key=f"attc_{pid}")
            with a3:
                punc_val = st.text_input("Lates (count)",
                    value=p.get("punctuality",""), key=f"punc_{pid}", placeholder="e.g. 3")
                p["punctuality"] = punc_val
            with a4:
                auto_punc = _punc_cat(punc_val)
                if auto_punc:
                    p["punc_code"] = auto_punc
                    st.markdown(f"<small>→ **{auto_punc}**</small>", unsafe_allow_html=True)
                else:
                    cats2 = ["","Exceptional","Expected","Below Expected","Cause for Concern"]
                    pc = p.get("punc_code","")
                    p["punc_code"] = st.selectbox("Punc category", cats2,
                        index=cats2.index(pc) if pc in cats2 else 0, key=f"puncc_{pid}")
        p["pupil_voice"] = st.text_area("Pupil voice",
            value=p.get("pupil_voice",""), key=f"pv_{pid}", height=80,
            placeholder="To be completed by the pupil")

    # ── Save ──────────────────────────────────────────────────────────────────
    st.markdown("---")
    if st.button("💾  Save", type="primary", use_container_width=True, key="save_score"):
        for i, existing in enumerate(cd["pupils"]):
            if existing["id"] == pid:
                cd["pupils"][i] = p
                break
        st.session_state.cd = cd
        save_and_confirm()




# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  COMMENTS TAB                                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
if nav == "💬 Comments":
    if not pupils:
        st.info("Import pupils first from the Pupils tab.")
    else:
        sorted_pupils = sorted(pupils, key=lambda p: p["last_name"])
        sorted_ids    = [p["id"] for p in sorted_pupils]

        pid = get_sel()
        if pid not in sorted_ids:
            pid = sorted_ids[0]
            set_sel(pid)
        idx = sorted_ids.index(pid)

        nc1, nc2, nc3 = st.columns([1, 5, 1])
        with nc1:
            if st.button("← Prev ", disabled=(idx == 0), key="cprev"):
                set_sel(sorted_ids[idx - 1]); st.rerun()
        with nc2:
            new_pid = st.selectbox("Pupil ", options=sorted_ids,
                format_func=lambda x: p_map[x]["full_name"],
                index=idx, label_visibility="collapsed", key="cpupil_sel")
            if new_pid != pid:
                set_sel(new_pid); st.rerun()
        with nc3:
            if st.button("Next  →", disabled=(idx == len(sorted_ids) - 1), key="cnext"):
                set_sel(sorted_ids[idx + 1]); st.rerun()

        p = p_map[pid]
        comments = p.setdefault("comments", {})

        st.markdown(f"### {p['first_name']} {p['last_name']}")

        SECTION_META = [
            ("reader",       "📖 Being a reader",       (90, 130)),
            ("writer",       "✏️ Being a writer",       (90, 130)),
            ("mathematician","🔢 Being a mathematician",(90, 130)),
            ("learner_21c",  "🎓 21st Century Learner",  (80, 120)),
            ("rights",       "⚖️ Rights & Responsibilities", (60, 100)),
        ]

        changed = False
        for key, label, (lo, hi) in SECTION_META:
            text = comments.get(key, "")
            wc   = word_count(text)
            col_label = (f"{label} — {wc} words" +
                         (" ✅" if lo <= wc <= hi else f" ⚠️ target {lo}–{hi}"))
            new_text = st.text_area(col_label, value=text, height=160, key=f"c_{key}_{pid}")
            if new_text != text:
                comments[key] = new_text
                changed = True

        if changed:
            for i, existing in enumerate(cd["pupils"]):
                if existing["id"] == pid:
                    cd["pupils"][i] = p; break
            st.session_state.cd = cd

        if st.button("💾  Save comments", type="primary", key="save_comments"):
            for i, existing in enumerate(cd["pupils"]):
                if existing["id"] == pid:
                    cd["pupils"][i] = p; break
            st.session_state.cd = cd
            save_and_confirm()


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  GENERATE TAB                                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
if nav == "✍️ Generate":
    if not pupils:
        st.info("Import pupils first from the Pupils tab.")
    else:
        st.markdown("### Generate comments with Claude AI")
        st.markdown(
            "Comments are generated in Innes's writing style, using Y4 curriculum content, "
            "from each pupil's scores. Review and edit in the **💬 Comments** tab before finalising."
        )

        sorted_pupils = sorted(pupils, key=lambda p: p["last_name"])

        # Status summary
        has_comments = sum(1 for p in sorted_pupils
                          if any(p.get("comments",{}).get(k) for k in
                                 ["reader","writer","mathematician","learner_21c","rights"]))
        st.markdown(f"{has_comments}/{len(sorted_pupils)} pupils have comments")

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("#### Generate for all pupils")
            st.caption("Generates all 5 sections for every pupil. Takes ~1–2 min for a class of 30.")
            overwrite = st.checkbox("Overwrite existing comments", value=False, key="gen_overwrite")
            if st.button("Generate all", type="primary", key="gen_all"):
                to_generate = sorted_pupils if overwrite else [
                    p for p in sorted_pupils
                    if not any(p.get("comments",{}).get(k)
                               for k in ["reader","writer","mathematician","learner_21c","rights"])
                ]
                if not to_generate:
                    st.info("All pupils already have comments. Tick 'Overwrite' to regenerate.")
                else:
                    prog = st.progress(0.0)
                    status = st.empty()
                    ok_count = fail_count = 0
                    for i, p in enumerate(to_generate):
                        status.markdown(f"Generating: **{p['full_name']}** ({i+1}/{len(to_generate)})")
                        try:
                            result = generate_comments(p)
                            p["comments"] = result
                            for j, existing in enumerate(cd["pupils"]):
                                if existing["id"] == p["id"]:
                                    cd["pupils"][j] = p; break
                            st.session_state.cd = cd
                            ok_count += 1
                        except Exception as e:
                            st.warning(f"⚠️ {p['full_name']}: {e}")
                            fail_count += 1
                        prog.progress((i + 1) / len(to_generate))
                        time.sleep(0.3)
                    status.empty()
                    save_and_confirm()
                    st.success(f"Done — {ok_count} generated, {fail_count} failed.")

        with c2:
            st.markdown("#### Generate for one pupil")
            sel_name = st.selectbox(
                "Select pupil",
                options=[p["id"] for p in sorted_pupils],
                format_func=lambda x: p_map[x]["full_name"],
                key="gen_single_sel",
            )
            if st.button("Generate", key="gen_single"):
                p = p_map[sel_name]
                with st.spinner(f"Generating for {p['full_name']}…"):
                    try:
                        result = generate_comments(p)
                        p["comments"] = result
                        for j, existing in enumerate(cd["pupils"]):
                            if existing["id"] == p["id"]:
                                cd["pupils"][j] = p; break
                        st.session_state.cd = cd
                        save_and_confirm()
                        st.success("Generated ✓ — review in the 💬 Comments tab.")
                        # Preview
                        for key, label in [
                            ("reader","Reader"),("writer","Writer"),("mathematician","Mathematician"),
                            ("learner_21c","21C Learner"),("rights","R&R"),
                        ]:
                            with st.expander(label):
                                st.write(result.get(key, ""))
                    except Exception as e:
                        st.error(f"Generation failed: {e}")

        # ── Export Excel ─────────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### Export to Excel")
        st.markdown(
            "Exports all learner data — grades, attendance, all five generated comment "
            "sections and pupil voice — in the exact column format of **report-data.xlsx** "
            "ready for your print workflow."
        )
        comments_done = sum(1 for p in sorted_pupils
                           if any(p.get("comments",{}).get(k)
                                  for k in ["reader","writer","mathematician",
                                            "learner_21c","rights"]))
        st.caption(f"{comments_done}/{len(sorted_pupils)} learners have at least one comment section.")
        if st.button("📥 Export report-data.xlsx", type="primary", key="export_xlsx"):
            with st.spinner("Building Excel…"):
                buf = export_excel(cd, settings=load_settings())
                st.download_button(
                    "⬇️ Download report-data.xlsx",
                    data=buf,
                    file_name="report-data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_xlsx",
                )

        # ── Report PDF ────────────────────────────────────────────────────────
        if SHOW_ADVANCED:
         st.markdown("---")
         st.markdown("#### Generate report PDFs")
         if SHOW_ADVANCED:
          st.markdown("Produces the A3 duplex PDF ready to print. "
                      "Only includes learners who have comments.")

          has_all = [p for p in sorted_pupils
                     if all(p.get("comments",{}).get(k)
                            for k in ["reader","writer","mathematician","learner_21c","rights"])]
          st.caption(f"{len(has_all)}/{len(sorted_pupils)} learners have all five sections complete.")

          lz_colour = "#1798d3"

          pr1, pr2 = st.columns(2)

          with pr1:
              pdf_pupil = st.selectbox(
                  "Single learner PDF",
                  options=[p["id"] for p in sorted_pupils],
                  format_func=lambda x: p_map[x]["full_name"],
                  key="pdf_single_sel",
              )
              if st.button("Generate PDF", key="pdf_single_btn"):
                  p = p_map[pdf_pupil]
                  if not any(p.get("comments",{}).get(k)
                             for k in ["reader","writer","mathematician","learner_21c","rights"]):
                      st.warning("No comments yet for this learner — generate comments first.")
                  else:
                      with st.spinner("Building PDF…"):
                          settings = load_settings()
                          buf = generate_reports_pdf(
                              cd, settings, class_id,
                              pat=st.secrets.get("GITHUB_TOKEN"),
                              pupil_ids=[pdf_pupil],
                              lz_colour_hex=lz_colour,
                          )
                          st.download_button(
                              "⬇️ Download PDF",
                              data=buf,
                              file_name=f"{p['last_name']}_{p['first_name']}_Report_2025-26.pdf",
                              mime="application/pdf",
                              key="dl_single",
                          )

          with pr2:
              if st.button("Generate ALL reports PDF", key="pdf_all_btn", type="primary"):
                  if not has_all:
                      st.warning("No learners have complete comments yet.")
                  else:
                      with st.spinner(f"Building PDF for {len(has_all)} learners…"):
                          settings = load_settings()
                          buf = generate_reports_pdf(
                              cd, settings, class_id,
                              pat=st.secrets.get("GITHUB_TOKEN"),
                              pupil_ids=[p["id"] for p in has_all],
                              lz_colour_hex=lz_colour,
                          )
                          st.download_button(
                              f"⬇️ Download all reports ({len(has_all)} learners)",
                              data=buf,
                              file_name=f"Y4_Maple_Reports_2025-26.pdf",
                              mime="application/pdf",
                              key="dl_all",
                          )

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  PHOTOS TAB                                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
if nav == "📸 Photos":
    st.markdown(f"""
**Naming convention:** `firstname_lastname.jpg`  
Lowercase, underscores between words. Hyphens preserved in hyphenated names.

| Pupil | Expected filename |
|---|---|
| Haris Ahmed | `haris_ahmed.jpg` |
| Daisy Chase-Williams | `daisy_chase-williams.jpg` |
| Max Fong | `max_fong.jpg` |

Select all photos at once — the app matches them by filename.
""")

    uploaded = st.file_uploader(
        "Upload photos",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="photo_upload",
    )

    if uploaded and st.button("Upload to app", type="primary"):
        ok_list, fail_list = [], []
        for f in uploaded:
            # Normalise extension to .jpg
            fname = f.name.lower()
            if fname.endswith(".jpeg"):
                fname = fname[:-5] + ".jpg"
            result = save_photo(class_id, fname, f.read())
            (ok_list if result else fail_list).append(fname)
        if ok_list:
            st.success(f"Uploaded {len(ok_list)} photo(s)")
        if fail_list:
            st.error(f"Failed: {', '.join(fail_list)}")

    st.markdown("---")
    st.markdown("**Match status**")

    if pupils:
        header = st.columns([4, 3, 1])
        for c, lbl in zip(header, ["Pupil", "Expected filename", "Found"]):
            c.markdown(f"<small><b>{lbl}</b></small>", unsafe_allow_html=True)

        for p in sorted(pupils, key=lambda x: x["last_name"]):
            fn = p.get("photo", "")
            url = photo_raw_url(class_id, fn)
            try:
                r = requests.head(url, timeout=2)
                found = r.status_code == 200
            except Exception:
                found = False

            row = st.columns([4, 3, 1])
            row[0].write(p["full_name"])
            row[1].markdown(f"`{fn}`")
            row[2].write("✅" if found else "❌")



# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  PUPIL VOICE TAB                                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
if nav == "📥 Pupil Voice":
    st.markdown("### Pupil Voice Import")
    st.markdown(
        "Upload the Microsoft Forms export Excel. The app will clean each pupil's "
        "answers and generate a polished narrative paragraph ready to paste into "
        "your reports Excel."
    )

    forms_file = st.file_uploader(
        "Forms export — Year_4_Reports_Pupil_Voice.xlsx",
        type=["xlsx"],
        key="pv_upload",
    )

    if forms_file and st.button("Process and download", type="primary", key="pv_run"):
        file_bytes = forms_file.read()
        prog_bar   = st.progress(0.0)
        status_txt = st.empty()

        def on_progress(done, total, name):
            prog_bar.progress(done / total)
            status_txt.markdown(f"Processing: **{name}** ({done}/{total})")

        with st.spinner("Cleaning pupil voice responses…"):
            try:
                results, errors = process_forms_export(file_bytes, progress_cb=on_progress)
            except Exception as e:
                st.error(f"Failed to read file: {e}")
                st.stop()

        status_txt.empty()
        prog_bar.progress(1.0)

        if errors:
            st.warning("Some pupils failed — check names match exactly:")
            for err in errors:
                st.caption(f"⚠️ {err}")

        if results:
            st.success(f"Processed {len(results)} pupil(s) ✓")
            xlsx_bytes = build_output_excel(results)
            st.download_button(
                "⬇️ Download Pupil_Voice.xlsx",
                data=xlsx_bytes,
                file_name="Pupil_Voice.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="pv_dl",
            )
        else:
            st.error("No results — check the uploaded file has responses.")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SETTINGS TAB                                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
if nav == "⚙️ Settings":
    settings = load_settings()

    st.markdown("### Year & class")
    c1, c2 = st.columns(2)
    with c1:
        settings["academic_year"] = st.text_input(
            "Academic year", value=settings.get("academic_year", "2025-26"))
    with c2:
        settings["teacher_name"] = st.text_input(
            "Teacher name", value=settings.get("teacher_name", "Mr McLean"))

    if SHOW_ADVANCED:
     st.markdown("### Principal's letter")
     st.caption(
         "Use `{pupil}` for the learner's name and `{teacher}` for the teacher's name. "
        "Leave a blank line (or type `///`) to start a new paragraph. "
        "Wrap text in `**double asterisks**` to make it bold."
    )
     default_letter = (
        "Dear Families,\n\n"
        "It\'s a pleasure to share this annual report celebrating {pupil}\'s journey "
        "at WFA for 2025\u201326. This year has been rich in learning and connection\u2014"
        "from celebrating Diwali and Eid to deepening inclusive practice through Black History "
        "Month and anti-prejudice work. We\'ve also strengthened wellbeing support with a "
        "dedicated Mental Health Practitioner, and learners have thrived through science, oracy "
        "and leadership experiences. The report highlights {pupil}\'s achievements and next "
        "steps\u2014I hope it offers a meaningful opportunity to celebrate their progress.\n\n"
        "If you have any questions, please don\'t hesitate to contact us to arrange a "
        "conversation with {teacher}.\n\n"
        "Warm regards,\n"
        "**Charlotte Black (Principal)**"
    )
     settings["principals_letter"] = st.text_area(
        "Letter", value=settings.get("principals_letter", default_letter),
        height=260, label_visibility="collapsed",
    )

    if SHOW_ADVANCED:
     st.markdown("### School cover photo")
     st.caption("Building/school photo shown on the report cover. Upload once, reused every year.")
     cover_f = st.file_uploader("School cover photo", type=["jpg","jpeg","png"], key="cover_photo")
     if cover_f:
         img_bytes = cover_f.read()
         if save_photo(class_id, "school_photo.jpg", img_bytes):
             st.image(img_bytes, width=300, caption="Cover photo saved ✓")
         else:
             st.error("Upload failed")

    if SHOW_ADVANCED:
     st.markdown("### Enquiry images — Terms 1 to 6")
     st.caption(
         "Upload one image per term. You assemble these from the year's enquiries; "
        "the report generator will place them automatically."
    )
     cols = st.columns(3)
     for term in range(1, 7):
      with cols[(term - 1) % 3]:
          st.markdown(f"**Term {term}**")
          img_f = st.file_uploader(
              f"T{term} image", type=["jpg","jpeg","png"],
              key=f"enq_{term}", label_visibility="collapsed",
          )
          if img_f:
              img_bytes = img_f.read()
              fname = f"enquiry_T{term}.jpg"
              if save_photo(class_id, fname, img_bytes):
                  st.image(img_bytes, use_container_width=True)
                  st.caption(f"T{term} saved ✓")
              else:
                  st.error("Upload failed")

    st.markdown("---")
    if st.button("Save settings", type="primary"):
        if save_settings(settings):
            st.success("Settings saved ✓")
        else:
            st.error("Save failed — check GitHub token")
