import streamlit as st
import requests
import time
from importer import import_from_files
from generator import generate_comments, word_count
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

SPECIAL_OPTIONS = [
    "", "effort", "able_not_engaged", "anxiety",
    "low_engagement", "SEN_selective", "quiet", "low_effort",
]
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
c1, c2 = st.columns([1, 10])
with c1:
    st.markdown(
        f'<div style="background:{BLUE};color:white;font-weight:800;font-size:20px;'
        f'padding:10px 14px;border-radius:8px;text-align:center;margin-top:4px;">WFA</div>',
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f'<h2 style="margin:0;padding-top:8px;color:{NAVY};">Report Manager</h2>',
        unsafe_allow_html=True,
    )
st.markdown("---")

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
NAV_PAGES = ["👥 Pupils", "📋 Score", "💬 Comments", "✍️ Generate", "📸 Photos", "⚙️ Settings"]
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "👥 Pupils"

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

        hcols = st.columns([5, 1, 1, 1, 3, 1])
        for c, lbl in zip(hcols, ["Name", "R", "W", "M", "Scored", "Photo"]):
            c.markdown(f"<small><b>{lbl}</b></small>", unsafe_allow_html=True)

        for p in sorted_pupils:
            cols = st.columns([5, 1, 1, 1, 3, 1])

            with cols[0]:
                btn_col, name_col = st.columns([1, 8])
                with btn_col:
                    if st.button("📋", key=f"sel_{p['id']}", help="Open in Score tab"):
                        set_sel(p["id"])
                        st.session_state.nav_page = "📋 Score"
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
            sp_cur = p.get("special", "")
            sp_idx = SPECIAL_OPTIONS.index(sp_cur) if sp_cur in SPECIAL_OPTIONS else 0
            p["special"] = st.selectbox(
                "Special flag", options=SPECIAL_OPTIONS,
                index=sp_idx, key=f"special_{pid}",
                format_func=lambda x: x if x else "— none",
            )

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
    with st.expander("📝 Attendance & pupil voice"):
        a1, a2, a3, a4 = st.columns(4)
        att_codes  = ["", "Exceptional", "Expected", "Below Expected", "Cause for Concern"]
        punc_codes = ["", "Always on time", "Very rarely late", "Frequently late", "Persistently late"]
        with a1:
            p["attendance"] = st.text_input("Attendance %",
                value=p.get("attendance",""), key=f"att_{pid}")
        with a2:
            ac = p.get("att_code","")
            p["att_code"] = st.selectbox("Code", att_codes,
                index=att_codes.index(ac) if ac in att_codes else 0,
                key=f"attc_{pid}")
        with a3:
            p["punctuality"] = st.text_input("Lates #",
                value=p.get("punctuality",""), key=f"punc_{pid}")
        with a4:
            pc = p.get("punc_code","")
            p["punc_code"] = st.selectbox("Code ", punc_codes,
                index=punc_codes.index(pc) if pc in punc_codes else 0,
                key=f"puncc_{pid}")
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
# ║  SETTINGS TAB                                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
if nav == "⚙️ Settings":
    settings = load_settings()

    st.markdown("### Year & class")
    c1, c2 = st.columns(2)
    with c1:
        settings["academic_year"]  = st.text_input(
            "Academic year", value=settings.get("academic_year", "2025-26"))
    with c2:
        settings["class_display"] = st.text_input(
            "Class display name", value=settings.get("class_display", "Y4 Maple"),
            help="Shown on the report cover — e.g. 'Y4 Maple'")

    st.markdown("### Principal's letter")
    st.caption("This text appears on every report. Update it each year.")
    settings["principals_letter"] = st.text_area(
        "Letter", value=settings.get("principals_letter", "Dear Families,\n\n"),
        height=220, label_visibility="collapsed",
    )

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
