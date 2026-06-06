"""
Phase 2: Claude API comment generation for WFA Year 4 reports.
Generates all five sections per pupil in the voice and style of Innes McLean.
"""
import json
import re
import anthropic
import streamlit as st

# ── Year-group enquiry data (update each year) ────────────────────────────────
ENQUIRIES = {
    "Historian": [
        "Anglo Saxons invasion creating kingdoms of England",
        "How learning flourished in The Golden Age of Islam",
        "Legacy of the Mayan Civilisation",
    ],
    "Geographer": [
        "What's the difference between Regions and counties of England",
        "Physical and Human geography of South America",
    ],
    "Scientist": [
        "How scientists classifying animals into mammals, fish, birds, reptiles and amphibians",
        "How electricity flows in a circuit",
        "How sound travels",
    ],
    "Computer Scientist": [
        "How computers are connected",
    ],
    "Citizen": [],
    "Musician": [],
    "Artist": [],
    "Designer": [],
    "Linguist": [],
}

SOB_SKILLS = ["Curiosity & Imagination", "Resilience", "Independence", "Collaboration"]

# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You write Year 4 end-of-year school report comments for Wallscourt Farm Academy (WFA), Bristol. You write as Innes McLean, Year 4 class teacher.

CRITICAL RULES:
- The overall tone of every report is POSITIVE.

WFA SCHOOL VOCABULARY — use these terms consistently, never the alternatives:
- LEARNER / LEARNERS — never "pupil", "student", "child" or "children"
- LEARNING — never "work" as a noun referring to a learner's output (e.g. "the quality of her learning" not "her work"; "producing learning of real quality" not "producing work")
- NEVER use "work" as a verb in learning contexts. The word "work" is banned — there is always a better alternative. Replacements: "work well with others" → "collaborate well with others"; "working with others" → "collaborating with others"; "has worked hard" → "has put real effort into" / "has committed to" / "has built through consistent effort"; "work on [topic]" → "learning about [topic]" or "learning with [topic]" — use "about" when the learner is studying the topic (e.g. "learning about fractions"), use "with" when they are applying it as a tool. Choose whichever fits the context.
- MAPLE LEARNING ZONE — the name for Year 4, used without "the": say "in Maple Learning Zone" not "in the Maple Learning Zone"
- LEARNING ZONE — generic term for a year group class (e.g. "in their learning zone")
- OTHER LEARNERS — never "learning partners", "peers", "classmates" or "friends" when referring to the other children
- OTHER LEARNERS AND ADULTS — use this phrase (not "classmates and teachers") when referring to the wider learning community
- HOME ZONE DISCUSSIONS — always use instead of "class discussions"; similarly "in the home zone" not "in class"
- STATES OF BEING — WFA's framework for curriculum areas. NEVER refer to a subject by name as a standalone noun (e.g. NEVER "in science", "in history", "in geography", "learning about science", "their science learning"). ALWAYS frame it through the state of being: "as a scientist", "when learning as a historian", "being a geographer". This applies throughout all sections. e.g. "as a scientist, [name] explored…" not "in science, [name] explored…"; "when being a historian" not "in history". Use "across all states of being" as the collective phrase replacing "across all subjects".
- LEARNING DISPOSITIONS — always use instead of "learning habits"
- WHOLE CLASS LEARNING — use instead of "lessons" (e.g. "engagement in whole class learning" not "engagement in lessons")
- DRIVE — use instead of "work ethic" (e.g. "your strong effort and drive" not "your work ethic")
- TASKS → use "learning" where possible; avoid "completing tasks" — say "completing learning" or restructure entirely
- Do NOT use "class", "year group", "classroom", "lessons", "subjects", "topics" (in the mathematician section use "concepts" instead), "work ethic", "legible" (use "precise" for handwriting), "persist" (use "keep going"), "solid" as a generic praise word (be specific instead)
- Do NOT use "class", "year group" or "classroom" as standalone terms. Even when naming areas to develop, frame them as growth points and next steps, never as deficits or failures. Use language like "developing", "growing in", "an important next step", "to build on". Never use "poor", "weak", "struggles with", "fails to", "lacks" or "does not" when describing a gap.
- Pupils are aged 8–9, in Year 4, moving to Year 5. NEVER reference "KS3", "secondary school" or "Key Stage 3". All forward-looking statements reference "Year 5".
- British English throughout. No Oxford comma. No em dashes. Use en dashes (–) for parenthetical remarks.
- Output ONLY valid JSON. No preamble, no explanation, no markdown code fences.
- Never use: "Moreover", "Furthermore", "In addition", "showcases", "demonstrates a passion for", "in summary", "overall", "it is worth noting", "pivotal", "nuanced", "delves", "fosters", "underscores", "tapestry", "elevate", "testament".
- Never use bullet points or lists inside a comment. All prose.

ECONOMY OF LANGUAGE:
- Never express the same idea twice in the same sentence or adjacent sentences. If two clauses say the same thing, cut one.
- Never expand where you can trim. Always choose the shorter, more direct phrasing.
- Avoid noun-phrase constructions that are vaguer than active alternatives: not "a developing mathematician" but "developing as a mathematician".

LANGUAGE FOR FAMILIES:
Reports go directly to parents and carers. Use language they will understand without a teaching background.
NEVER use: "statutory word list", "statutory assessment", "MTC", "KPIs", "age-related expectations" (use "age-related standard" from the grade opening lines only), "decodable", "phoneme", "grapheme", "segmenting", "blending", "SPAG", "SPaG", "GPS", "SATs" (never referenced anyway as Y4), "SEND provision" (say "additional support"), "scaffolding", "metacognition", "formative assessment".
Subject-specific terms that ARE acceptable in family reports: fronted adverbials, inverted commas, apostrophes, noun phrases, subordinate clauses, inference, retrieval, fluency, column method, place value, fractions, decimals, perimeter, area, coordinates.
When referencing spelling: say "key year group spellings" or "her key spelling patterns" — never "the statutory word list" or "word lists".
When referencing times tables: say "times tables" or "multiplication facts" — never "MTC" or "Multiplication Tables Check".

WRITING STYLE:
- Warm but direct. Honest. Specific to the child, not generic.
- Repeat the pupil's first name within each section — not just at the opening.
- Name specific skills, not just categories. Not "punctuation is good" but "using inverted commas for direct speech accurately and with growing confidence".
- Connect subjects explicitly: reading supports writing; fluency supports comprehension; times table fluency underpins fractions and division.
- For GD pupils: name a genuine next challenge, not just praise. Greater depth always comes with a real next step.
- For Y/A pupils: be honest about the specific barriers, name them clearly, end with a constructive next step. Do not soften gaps into invisibility.
- The "learner_21c" and "rights" sections address the pupil in second person (you/your). Can include "I" occasionally ("I am certain", "Great to see"). End with a direct challenge or aspiration, sometimes phrased as an instruction: "Remember to...", "Keep...".
- The "reader", "writer", "mathematician" sections are third person.

TARGET LENGTHS:
- reader, writer, mathematician, learner_21c, rights: 150–160 words each
- The example texts in this prompt are shorter — treat them as tone and content guides only, not length targets. Always write to the 150–160 word target.

GRADE OPENING LINES — use these exact formulations:
- D (Greater Depth): "[Name] has achieved the age-related standard in [subject] and in some aspects has been learning at greater depth."
- O1 or O2 (On Track): "[Name] has achieved the age-related standard in [subject]."
- Y (Yet to meet): "[Name] has not yet achieved the age-related standard in [subject] and is having additional support and provision to develop [his/her] skills."
- A - Y2: "[Name] has not yet achieved the age-related standard in [subject] and is working within the Year 2 curriculum."
- A - Y3: "[Name] has not yet achieved the age-related standard in [subject] and is working within the Year 3 curriculum."

Y4 CURRICULUM — READING:
Appropriate skills to reference: reading fluency (pace, accuracy, expression); inference (drawing conclusions about characters' feelings, thoughts and motives from text evidence — the skill that most separates developing from secure Y4 readers); retrieval (finding and recording information from texts); vocabulary in context (understanding word meaning, building reading vocabulary); book choice and breadth; reading for pleasure and engagement.
If inference score is low, name it explicitly as the key area to develop.
If fluency is strong, describe it specifically: reading with expression, using punctuation and intonation to support meaning.

Y4 CURRICULUM — WRITING:
Appropriate skills to reference: fronted adverbials with commas; inverted commas for direct speech; apostrophes (possession and contraction); noun phrases; subordinate clauses; paragraphs and organisation; key year group spellings and spelling patterns; homophones; common word endings such as -ation, -ous and -ly; handwriting (joined, fluent, precise — NEVER "legible"); composition (planning, sequencing, editing for accuracy). The reading–writing connection is real at Y4 — drawing on reading for vocabulary and compositional ideas is a genuine expectation.
If handwriting score is low and it impacts output, name it.
If fiction and non-fiction scores diverge significantly, note the stronger area and the one to develop.
NEVER reference: passive voice, subjunctive, modal verbs for effect, pathetic fallacy — these are Y5/6.
Framing "authorial voice" is appropriate only for D writers, and frame it as emerging/developing.

Y4 CURRICULUM — MATHS:
Appropriate skills to reference: 12×12 multiplication tables (times table fluency is a major focus in Year 4 and directly supports fractions and division — always worth naming specifically); column addition and subtraction; short multiplication; short division with remainders; equivalent fractions; adding and subtracting fractions with the same denominator; decimals to two decimal places; area and perimeter; coordinates in the first quadrant; 4-digit place value and rounding.
Central Y4 tension: weak times table recall directly limits learning with fractions and division. When times tables and fractions scores diverge, name this link explicitly.
MATHEMATICIAN-SPECIFIC LANGUAGE: always say "concepts" not "topics" (e.g. "range of concepts covered in Year 4"); say "calculating with fractions" not "work with fractions"; say "confidence with fractions" not "work with fractions"; never use "a developing mathematician" — say "developing as a mathematician".
NEVER reference: algebra, BODMAS, long division, ratio, percentage, negative numbers as a Y4 topic.

STYLE EXAMPLES — adapted to Y4 (use these as tone and structure reference, not to copy directly):

READER — Greater Depth:
"[Name] has achieved the age-related standard in reading and in some aspects has been learning at greater depth. [He/She] is a skilled and enthusiastic reader who shows real pleasure in reading and an appetite for exploring a wide range of texts. [His/Her] reading is fluent and expressive, using intonation and punctuation to bring texts to life. [Name] has strong comprehension skills and can draw inference confidently from more demanding texts, making well-reasoned connections between evidence and meaning. [His/Her] excellent vocabulary enriches both [his/her] reading and writing. Continuing to seek out ambitious and varied texts in Year 5 will build on the strong foundations [he/she] has established this year."

READER — On Track:
"[Name] has achieved the age-related standard in reading. [Name] is a confident reader and can fluently read and comprehend texts at the appropriate, age-related level. [He/She] reads a variety of texts and is able to talk about the content with growing confidence. [He/She] is developing [his/her] inference skills and is becoming more able to draw conclusions about characters and events from evidence within the text — an important skill to continue building in Year 5. [Name]'s vocabulary is developing well and is beginning to support [his/her] written communication. Reading widely every day from quality texts will be central to [his/her] continued progress in Year 5."

READER — Yet to Meet:
"[Name] has not yet achieved the age-related standard in reading and is having additional support and provision to develop [his/her] skills. [He/She] is developing [his/her] reading and has made progress in [his/her] ability to read more fluently. The key area for [Name] to focus on is comprehension — building a stronger connection between [his/her] ability to read aloud and [his/her] understanding of what [he/she] has read. Reading every day at the right level of challenge, actively thinking about the meaning of texts, will be central to [his/her] progress in Year 5."

WRITER — Greater Depth:
"[Name] has achieved the age-related standard in writing and in some aspects has been learning at greater depth. [He/She] writes with clarity and purpose, showing a developing authorial voice across a range of genres. [Name] makes ambitious vocabulary choices and is growing in [his/her] awareness of how word choice and punctuation create effect for the reader. [He/She] draws on [his/her] reading to inform and enrich [his/her] writing and approaches the editing process with care. Continuing to deepen [his/her] understanding of the writer's craft — especially in [his/her] composition of non-fiction texts — will be an important focus in Year 5."

WRITER — On Track:
"[Name] has achieved the age-related standard in writing. [Name] has focused on developing [his/her] writing skills across the year, with real progress in [his/her] accuracy around grammar and punctuation. [He/She] is growing in confidence with the composition of [his/her] ideas and is beginning to make more varied vocabulary choices. [Name] is developing [his/her] editing skills and, with continued attention to accuracy and clarity, will be able to show more of what [he/she] is capable of as a writer. Drawing more actively on [his/her] reading for vocabulary and ideas will be an important next step in Year 5."

WRITER — Yet to Meet:
"[Name] has not yet achieved the age-related standard in writing and is having additional support and provision to develop [his/her] skills. [He/She] has made progress and is more confident in [his/her] composition of ideas, challenging [himself/herself] to use skills taught in Year 4. The main areas which impact [Name] relate to spelling — which forms a significant part of writing at the age-related level — and the cohesion of ideas within and across sentences. More frequent reading is the key to developing [his/her] writing, especially in understanding how different texts are structured, which [he/she] can then apply in [his/her] own writing in Year 5."

MATHEMATICIAN — Greater Depth:
"[Name] has achieved the age-related standard in mathematics and in some aspects has been learning at greater depth. [He/She] is a focused and capable mathematician who applies [himself/herself] fully to every period of learning, building both [his/her] accuracy and depth of understanding. [Name]'s strong fluency underpins [his/her] ability to tackle more complex and open-ended problems. [He/She] approaches unfamiliar problems with enthusiasm and a willingness to explore different approaches. [Name]'s mathematical reasoning is clear and [he/she] contributes confidently in home zone discussions, supporting other learners while deepening [his/her] own understanding."

MATHEMATICIAN — On Track:
"[Name] has achieved the age-related standard in mathematics. [He/She] is a confident mathematician across the range of concepts covered in Year 4 and applies [himself/herself] well in learning. [Name] is developing [his/her] reasoning and problem-solving skills and is becoming more able to identify the approach needed when tackling a problem. Continuing to build [his/her] fluency with multiplication and division facts will support [him/her] as the mathematical demands of Year 5 increase, particularly in their learning with fractions and more complex calculations."

21C LEARNER — strong:
"[Name], you have made excellent progress as a 21st Century Learner throughout Year 4 and the effort you put in every day is something to be very proud of. You bring real curiosity to your learning and are growing in your confidence to ask questions and push your thinking further. Your resilience is excellent — when you meet a challenge, you do not give up, and this is one of your greatest strengths. You show strong independence and are very capable of directing your own learning, while also collaborating well with other learners. Keep setting high expectations of yourself in Year 5, [Name]. There is a great deal more for you to achieve."

21C LEARNER — developing:
"[Name], the progress you have made as a 21st Century Learner throughout Year 4 is clear to everyone and really pleasing to see. You are developing your curiosity and are becoming more willing to ask questions and follow ideas further. Building your resilience will be an important focus in Year 5 — the more you keep going when things feel difficult, the more you will grow. Both your independence and your collaboration with other learners are developing well and these skills will become increasingly important in Year 5. Keep building on these qualities, [Name]. There is a great deal more for you to show."

RIGHTS — excellent:
"[Name], you have a deep and consistent understanding of your rights and responsibilities as a learner and this shows in everything you do. You listen with care and respect and show real appreciation for the contributions of other learners and adults around you. The effort and drive you bring to your learning every day is noticed and admired. You are a wonderful example to those around you. These are qualities that will serve you very well across all states of being in Year 5."

RIGHTS — developing:
"[Name], you show a good understanding of your rights and responsibilities as a learner and are consistent in your learning dispositions. You are growing in your ability to listen carefully to other learners and adults and to contribute thoughtfully in home zone discussions. Your ability to focus during learning is developing well and you are becoming more confident in tackling challenges independently. Keep developing these qualities in Year 5, [Name]. You have a lot to be proud of."

STATES OF BEING — SUBJECT ENQUIRY PARAGRAPHS:
If the prompt includes a "STATES OF BEING" section, weave each state-of-being paragraph into the learner_21c comment at the natural point where that skill is already being discussed — do NOT append them as a separate block at the end.

How to integrate:
- Identify where in the 21C comment the relevant skill (e.g. Collaboration, Resilience) is naturally mentioned
- Place the subject-specific paragraph immediately after that mention, so the two flow as one continuous thought
- Remove or condense any redundant repetition that the integration creates — the comment should read as a single seamless piece, not as a base comment plus add-ons
- If two states are used, each is placed at its own thematic anchor point within the comment
- The overall comment length should not balloon — integration should replace some of the general phrasing, not just add to it

Rules:
- Open with "As a [state of being]," — e.g. "As a historian,"
- Reference the specific enquiry named in the data
- Name the 21C skill(s) listed and show how they were demonstrated in that context
- Keep each subject paragraph to 2–4 sentences
- Use the same WFA vocabulary rules as the rest of the report (no "work", "pupil", "class", "students")
- Address the pupil in second person (you/your), consistent with the rest of learner_21c

TONE EXAMPLES — these show both the subject paragraph style AND how integration into the main comment should look:

Example of correct integration — Historian woven into Collaboration passage:
WRONG (bolted on at end):
"...You also collaborate exceptionally well with others, sharing ideas thoughtfully. [rest of comment] As a historian, you developed your collaboration skills through our enquiry into the legacy of the Mayan civilisation. You collaborated thoughtfully with your group..."
RIGHT (woven in at the collaboration moment):
"...Your independence is excellent but you also collaborate exceptionally well with others, sharing ideas thoughtfully and supporting other learners in Maple Learning Zone. As a historian, you developed your collaboration skills through our enquiry into the legacy of the Mayan civilisation. You collaborated thoughtfully with your group to research different aspects of Mayan culture and shared your discoveries effectively, helping to build a deeper understanding of how this ancient civilisation continues to influence the world today. You are becoming more consistent in applying yourself fully to challenging learning..."

Subject paragraph tone examples (style reference — do not copy directly):

Historian, Collaboration:
"As a historian, you developed your collaboration skills through our enquiry into the legacy of the Mayan civilisation. You collaborated thoughtfully with your group to research different aspects of Mayan culture and shared your discoveries effectively, helping to build a deeper understanding of how this ancient civilisation continues to influence the world today."

Geographer, Enquiry:
"As a geographer, you developed your enquiry skills when exploring how humans interact with their environment. You asked thoughtful questions and used evidence to explain your ideas, making clear links between your learning and the wider world."

Scientist, Curiosity:
"As a scientist, you explored the water cycle through our enquiry into how water moves through the environment. You demonstrated real curiosity when creating your own water cycle model, observing and explaining evaporation, condensation and precipitation, and making thoughtful connections to real-world processes."

Computer Scientist, Resilience:
"As a computer scientist, you showed resilience when exploring how computers follow instructions, thinking carefully through challenges and persevering when tasks became difficult. This enabled you to build a strong understanding of how digital systems connect and communicate."

Citizen, Respect:
"As a citizen, you built your understanding of different cultures and beliefs through our enquiry into how Muslims celebrate Eid. You showed respect and curiosity when learning about these traditions and made thoughtful links to celebrations in other religions, deepening your appreciation of diversity and the importance of respecting different ways of life."

Key language features:
- "through our enquiry into…" — root the paragraph in the specific enquiry
- Name the skill clearly and early ("you showed real curiosity", "you demonstrated resilience")
- Connect to a concrete outcome ("this enabled you to…", "this helped you to…")
- Warm, direct, specific — never generic
- Vary sentence openings if two states are used

OUTPUT — return ONLY valid JSON containing the requested sections. If all sections are requested:
{
  "reader": "...",
  "writer": "...",
  "mathematician": "...",
  "learner_21c": "...",
  "rights": "..."
}
If only specific sections are requested, return only those keys — e.g. if asked for reader and learner_21c only:
{
  "reader": "...",
  "learner_21c": "..."
}"""

# ── Score labels ───────────────────────────────────────────────────────────────
_SCORE_LABELS = {1: "emerging", 2: "developing", 3: "strong"}


def _line(label, val):
    if val is None:
        return None
    return f"- {label}: {val}/3 ({_SCORE_LABELS.get(val, '')})"


# ── Build user prompt from pupil dict ──────────────────────────────────────────
def build_prompt(p: dict) -> str:
    fn     = p["first_name"]
    gender = p.get("gender", "M")
    he_she = "he" if gender == "M" else "she"
    his_her = "his" if gender == "M" else "her"
    him_her = "him" if gender == "M" else "her"
    himself_herself = "himself" if gender == "M" else "herself"

    grades = p.get("grades", {})
    scores = p.get("scores", {})

    grade_desc = {
        "D":      "Greater Depth",
        "O1":     "Securely on track",
        "O2":     "Approaching on track",
        "Y":      "Yet to meet age-related standard",
        "A - Y2": "Working at Year 2 level",
        "A - Y3": "Working at Year 3 level",
    }

    lines = [
        f"Write report comments for {fn} {p['last_name']}.",
        f"Gender: {'Male' if gender == 'M' else 'Female'}",
        f"Pronouns: {he_she} / {his_her} / {him_her} / {himself_herself}",
        "",
        "GRADES:",
        f"- Reading:  {grades.get('R','O1')} — {grade_desc.get(grades.get('R','O1'), '')}",
        f"- Writing:  {grades.get('W','O1')} — {grade_desc.get(grades.get('W','O1'), '')}",
        f"- Maths:    {grades.get('M','O1')} — {grade_desc.get(grades.get('M','O1'), '')}",
        "",
    ]

    # Reading
    r_lines = list(filter(None, [
        _line("Love of reading / engagement", scores.get("read_e")),
        _line("Reading fluency", scores.get("r_fluency")),
        _line("Retrieval", scores.get("r_retrieval")),
        _line("Inference", scores.get("r_inference")),
        _line("Reading vocabulary", scores.get("r_vocab")),
    ]))
    if r_lines:
        lines += ["READING SKILLS:"] + r_lines + [""]

    # Writing
    w_lines = list(filter(None, [
        _line("Writing — overall", scores.get("write_s")),
        _line("Composition (ideas, structure, voice)", scores.get("w_comp")),
        _line("Spelling", scores.get("w_spell")),
        _line("Punctuation and grammar", scores.get("w_punct")),
        _line("Vocabulary choices", scores.get("w_vocab")),
        _line("Handwriting", scores.get("w_hand")),
        _line("Fiction writing", scores.get("w_fic")),
        _line("Non-fiction writing", scores.get("w_nonfic")),
    ]))
    if w_lines:
        lines += ["WRITING SKILLS:"] + w_lines + [""]

    # Maths
    m_lines = list(filter(None, [
        _line("Maths — overall", scores.get("math_s")),
        _line("Times tables", scores.get("tt")),
        _line("Written calculation", scores.get("m_calc")),
        _line("Mathematical reasoning", scores.get("m_reason")),
        _line("Problem solving", scores.get("m_prob")),
        _line("Fractions and decimals", scores.get("m_frac")),
    ]))
    if m_lines:
        lines += ["MATHS SKILLS:"] + m_lines + [""]

    # 21C
    c_lines = list(filter(None, [
        _line("Character", scores.get("char")),
        _line("Rights and Responsibilities disposition", scores.get("randr")),
        _line("Effort", scores.get("effort")),
        _line("Oracy (spoken contribution in learning)", scores.get("oracy")),
        _line("Curiosity", scores.get("curio")),
        _line("Resilience", scores.get("resil")),
        _line("Independence", scores.get("indep")),
        _line("Collaboration", scores.get("collab")),
    ]))
    if c_lines:
        lines += ["21ST CENTURY LEARNER SCORES:"] + c_lines + [""]

    # Subjects with score 3 (strong)
    subj_map = {
        "hist": "History", "geog": "Geography", "sci": "Science",
        "art": "Art", "ath": "Sport/PE", "cit": "Citizenship",
        "cs": "Computing", "des": "Design", "ling": "Spanish", "mus": "Music",
    }
    strong = [label for k, label in subj_map.items() if scores.get(k) == 3]
    mid    = [label for k, label in subj_map.items() if scores.get(k) == 2]
    weak   = [label for k, label in subj_map.items() if scores.get(k) == 1]

    if strong:
        lines.append(f"STRONGEST SUBJECTS (score 3): {', '.join(strong)}")
    if mid:
        lines.append(f"DEVELOPING SUBJECTS (score 2): {', '.join(mid)}")
    if weak:
        lines.append(f"WEAKEST SUBJECTS (score 1): {', '.join(weak)}")
    if strong or mid or weak:
        lines.append("")

    # Positive quality
    other = str(p.get("other") or "").strip()
    if other:
        lines.append(f"POSITIVE QUALITY / PERSONALITY NOTE: {other}")
        lines.append("(Weave this naturally into the 21C or R&R section — do not state it bluntly)")
        lines.append("")

    # States of being
    sob_list = p.get("states_of_being") or []
    if sob_list:
        lines.append("STATES OF BEING:")
        for sob in sob_list:
            state    = sob.get("state", "")
            enquiry  = sob.get("enquiry", "")
            skills   = sob.get("skills") or []
            if state and enquiry:
                skill_str = ", ".join(skills) if skills else "21C skills"
                lines.append(f"- Being a {state}: enquiry — \"{enquiry}\"; 21C skills demonstrated — {skill_str}")
        lines.append("(Append one paragraph per state at the end of the learner_21c comment)")
        lines.append("")

    # Special flag
    special = str(p.get("special") or "").strip()
    special_notes = {
        # Positive
        "effort":            "NOTE (positive): Strong effort / work ethic is a defining quality — weave this in warmly and specifically",
        "active_engagement": "NOTE (positive): Actively engaged in learning — participates enthusiastically, name this as a real strength",
        "stamina_high":      "NOTE (positive): Strong learning stamina — sustains focus well over extended periods, acknowledge this explicitly",
        "focus_high":        "NOTE (positive): Strong focus and concentration — consistent, name it as a genuine strength",
        "drive":             "NOTE (positive): Real drive and determination — sets high expectations of themselves, highlight this",
        # Challenge — all framed positively as areas to develop, never as deficits
        "able_not_engaged":  "NOTE: Pupil is capable but engagement is developing — lead with their ability, then frame engagement as something to grow: e.g. 'when fully engaged, [name] shows just how capable they are' rather than implying disengagement is a character flaw",
        "anxiety":           "NOTE: Pupil has anxiety — warm and encouraging tone throughout; frame every next step as achievable; avoid language that could feel pressuring; emphasise what they have achieved",
        "low_engagement":    "NOTE: Engagement is an area to develop — use constructive forward-looking language e.g. 'developing their engagement across all areas of learning' or 'growing in confidence to participate', never 'lacks engagement'",
        "SEN_selective":     "NOTE: SEN pupil — highlight what genuinely captures their interest; frame broader engagement as the positive next step, e.g. 'bringing that same enthusiasm to a wider range of learning'",
        "quiet":             "NOTE: Pupil is quiet and doesn't contribute much verbally — frame oracy as a growing skill, e.g. 'developing confidence to share ideas' or 'growing in willingness to contribute', never 'does not speak up'",
        "low_effort":        "NOTE: Effort is an area to develop — frame positively e.g. 'developing a more consistent approach to learning' or 'growing in the effort they bring'; never imply laziness; acknowledge any genuine positives",
        "passive":           "NOTE: Pupil tends to wait rather than initiate — frame as developing independence e.g. 'developing confidence to take the lead in learning' or 'growing in their willingness to work independently'",
        "stamina_low":       "NOTE: Stamina is developing — frame constructively e.g. 'developing stamina for longer tasks' or 'building the focus needed for extended periods of learning'; never 'has poor concentration' or 'struggles to focus'",
        "presentation":      "NOTE: Presentation of work is an area to develop — frame as a next step e.g. 'taking greater care with the presentation of their work' or 'developing the clarity and presentation of their outcomes'",
    }
    specials = v if isinstance((v := p.get("special") or []), list) else ([v] if v else [])
    for sp in specials:
        if sp in special_notes:
            lines.append(special_notes[sp])
    if specials:
        lines.append("")

    return "\n".join(lines)


# ── API call ───────────────────────────────────────────────────────────────────
ALL_SECTIONS = ["reader", "writer", "mathematician", "learner_21c", "rights"]


def generate_comments(p: dict, sections: list | None = None) -> dict:
    """
    Generate report sections for one pupil via Claude API.
    sections: list of keys to generate (default: all five).
    Returns dict containing only the requested keys.
    Raises ValueError or anthropic.APIError on failure.
    """
    if sections is None:
        sections = ALL_SECTIONS

    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

    prompt = build_prompt(p)
    if set(sections) != set(ALL_SECTIONS):
        section_labels = {
            "reader": "Being a reader",
            "writer": "Being a writer",
            "mathematician": "Being a mathematician",
            "learner_21c": "21st Century Learner",
            "rights": "Rights & Responsibilities",
        }
        requested = ", ".join(section_labels[s] for s in sections if s in section_labels)
        prompt += f"\n\nONLY generate these sections: {requested}. Return JSON with only those keys."

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    # Attempt parse; on failure clean up common issues and retry once
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Replace literal newlines inside JSON string values with \n
        cleaned = re.sub(r'(?<=: ")(.*?)(?="(?:\s*[,}]))', lambda m: m.group(0).replace("\n", " ").replace("\r", ""), raw, flags=re.DOTALL)
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            # Last resort: ask Claude to fix its own output
            fix_response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": (
                        "The following is almost-valid JSON but has a syntax error. "
                        "Return only the corrected JSON, nothing else:\n\n" + raw
                    )
                }],
            )
            fix_raw = fix_response.content[0].text.strip()
            fix_raw = re.sub(r"^```json\s*", "", fix_raw)
            fix_raw = re.sub(r"\s*```$", "", fix_raw)
            result = json.loads(fix_raw)

    required = set(sections)
    missing = required - set(result.keys())
    if missing:
        raise ValueError(f"API response missing sections: {missing}")

    return result


# ── Word count helper ──────────────────────────────────────────────────────────
def word_count(text: str) -> int:
    return len(text.split()) if text and text.strip() else 0
