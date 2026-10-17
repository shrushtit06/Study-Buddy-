"""Study Buddy – a calm, green study dashboard with AI tools (Streamlit + Gemini)."""
from __future__ import annotations

import base64
import calendar
import hashlib
import hmac
import shutil
import html
import json
import os
import random
import re
import textwrap
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from pypdf import PdfReader

try:
    import google.generativeai as genai
except ImportError:  # app still renders; AI features show a friendly message
    genai = None

# ------------------------------------------------------------------ setup
st.set_page_config(page_title="Study Buddy", page_icon="🌱", layout="wide",
                   initial_sidebar_state="expanded")

BASE = Path(__file__).parent
INK_DIR = BASE / "study_buddy_ink"
PDF_DIR = BASE / "study_buddy_files"
MODEL_NAME = "gemini-2.5-flash"
TODAY = date.today()

st.markdown(f"<style>{(BASE / 'style.css').read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True)


def H(markup: str) -> None:
    """Render HTML without markdown turning indentation into code blocks."""
    st.markdown(re.sub(r"\s*\n\s*", " ", markup), unsafe_allow_html=True)


esc = html.escape

# ------------------------------------------------------------------ accounts
USERS_FILE = BASE / "study_buddy_users.json"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _users() -> dict:
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()


def _uid(email: str) -> str:
    return hashlib.sha256(email.encode()).hexdigest()[:12]


def google_enabled() -> bool:
    try:
        return "auth" in st.secrets and hasattr(st, "login")
    except Exception:
        return False


def sign_up(name: str, email: str, password: str, confirm: str) -> str | None:
    """Create an account. Returns an error message, or None on success."""
    email = email.strip().lower()
    users = _users()
    if not name.strip():
        return "Enter your name."
    if not EMAIL_RE.match(email):
        return "Enter a valid email address."
    if len(password) < 8:
        return "Use a password with at least 8 characters."
    if password != confirm:
        return "The two passwords don't match."
    if email in users:
        return "An account with this email already exists. Try signing in."
    salt = os.urandom(16)
    first_account = not users
    users[email] = dict(name=name.strip(), salt=salt.hex(), hash=_hash(password, salt))
    try:
        USERS_FILE.write_text(json.dumps(users, indent=1), encoding="utf-8")
        legacy = BASE / "study_buddy_data.json"
        if first_account and legacy.exists():  # keep progress from before accounts existed
            shutil.move(str(legacy), str(BASE / f"study_buddy_data_{_uid(email)}.json"))
    except OSError:
        return "Could not save the account on this device."
    st.session_state.user = dict(email=email, name=name.strip(), uid=_uid(email))
    return None


def sign_in(email: str, password: str) -> str | None:
    email = email.strip().lower()
    rec = _users().get(email)
    # same work for unknown emails, so timing doesn't reveal which accounts exist
    salt = bytes.fromhex(rec["salt"]) if rec else b"\0" * 16
    ok = hmac.compare_digest(_hash(password, salt), rec["hash"] if rec else "0" * 64)
    if not rec or not ok:
        return "That email and password don't match."
    st.session_state.user = dict(email=email, name=rec["name"], uid=_uid(email))
    return None


def sign_out() -> None:
    google = st.session_state.get("user", {}).get("google")
    st.session_state.clear()
    if google:
        st.logout()


def set_auth_mode(mode: str) -> None:
    st.session_state.auth_mode = mode


AUTH_CSS = """
<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
.block-container { max-width: 100% !important; padding: 0 !important; }
[data-testid="stHorizontalBlock"] { gap: 0 !important; }
.auth-left { min-height: 100vh; padding: 21vh 13% 6vh; color: #fff;
  background: radial-gradient(900px 500px at 15% 10%, #3b5a47 0%, transparent 60%),
              radial-gradient(700px 500px at 90% 100%, #0e1914 0%, transparent 60%), #1d3528; }
.auth-brand { display: flex; align-items: center; gap: 14px; font-size: 1.7rem; font-weight: 700; letter-spacing: -.02em; }
.auth-logo { width: 54px; height: 54px; border-radius: 15px; background: #f6f5ee; display: grid; place-items: center; font-size: 1.7rem; }
.auth-left h1 { color: #fff; font-size: clamp(2rem, 4vw, 3.3rem); line-height: 1.08; letter-spacing: -.03em; margin: 54px 0 18px; font-weight: 700; }
.auth-left p.lead { color: #c9d8cf; font-size: 1.1rem; max-width: 26em; line-height: 1.6; margin: 0; }
.auth-feats { display: flex; margin-top: 56px; padding-top: 26px; border-top: 1px solid rgba(255,255,255,.18); max-width: 34em; }
.auth-feats > div { flex: 1; padding: 0 20px; border-left: 1px solid rgba(255,255,255,.18); }
.auth-feats > div:first-child { padding-left: 0; border-left: none; }
.auth-feats b { display: block; font-size: 1rem; margin-bottom: 8px; }
.auth-feats span { color: #b7c9bd; font-size: .86rem; line-height: 1.5; display: block; }
.st-key-auth_right { padding: 24vh 12% 6vh; min-height: 100vh; background: linear-gradient(180deg, #f4f3ea 0%, #fdfdfa 45%); }
.st-key-auth_right h2 { font-size: 2.1rem; font-weight: 700; letter-spacing: -.03em; margin: 0 0 6px; padding: 0; }
.st-key-auth_right .auth-sub { color: #66746c; font-size: 1.02rem; margin: 0 0 26px; }
.st-key-auth_right [data-testid="stForm"] { border: none; padding: 0; }
.st-key-auth_right .stTextInput input { height: 52px; border-radius: 16px !important; font-size: .98rem; padding-left: 18px; }
.st-key-auth_right .stFormSubmitButton button, .st-key-auth_right .stButton button[data-testid="stBaseButton-primary"] {
  width: 100%; height: 56px; border-radius: 16px; background: #223027; border-color: #223027; color: #fff; font-weight: 600; font-size: 1rem; margin-top: 8px; }
.st-key-auth_right .stFormSubmitButton button:hover { background: #2f4337; border-color: #2f4337; color: #fff; }
.st-key-auth_right .stButton button[data-testid="stBaseButton-tertiary"] { color: #55635b; font-size: .92rem; padding: 0; }
.auth-or { display: flex; align-items: center; gap: 14px; color: #66746c; font-size: .74rem; letter-spacing: .08em; margin: 18px 0 14px; }
.auth-or::before, .auth-or::after { content: ''; flex: 1; border-top: 1px solid #dfe3da; }
@media (max-width: 900px) { .auth-left { min-height: 0; padding: 40px 24px; } .st-key-auth_right { padding: 36px 24px; min-height: 0; } }
</style>
"""


def auth_screen() -> None:
    st.markdown(AUTH_CSS, unsafe_allow_html=True)
    mode = st.session_state.setdefault("auth_mode", "signin")
    left, right = st.columns([1.1, 1])
    with left:
        H('''<div class="auth-left"><div class="auth-brand"><span class="auth-logo">🌱</span>Study Buddy</div>
          <h1>Small steps.<br>Big results.</h1>
          <p class="lead">Study tools built from what you were actually taught.</p>
          <div class="auth-feats"><div><b>Notes</b><span>Type, handwrite or import PDFs</span></div>
          <div><b>Flashcards</b><span>Active recall until it sticks</span></div>
          <div><b>Quizzes</b><span>From your real material</span></div></div></div>''')
    with right, st.container(key="auth_right"):
        if mode == "signup":
            H('<h2>Create your account</h2><p class="auth-sub">Start building your study streak today.</p>')
            with st.form("signup", border=False):
                name = st.text_input("Name", placeholder="Name", label_visibility="collapsed")
                email = st.text_input("Email", placeholder="Email", label_visibility="collapsed")
                pw = st.text_input("Password", placeholder="Password (8+ characters)", type="password", label_visibility="collapsed")
                pw2 = st.text_input("Confirm password", placeholder="Confirm password", type="password", label_visibility="collapsed")
                go_ = st.form_submit_button("Create account", type="primary")
            if go_:
                err = sign_up(name, email, pw, pw2)
                if err:
                    st.error(err)
                else:
                    st.rerun()
            st.button("Already have an account? Sign in", type="tertiary", on_click=set_auth_mode, args=("signin",))
        elif mode == "forgot":
            H('<h2>Reset password</h2><p class="auth-sub">We can\'t email you from this app yet.</p>')
            st.info("This app runs on your own computer, so it has no email service to send a reset link. "
                    "To reset, delete your entry in `study_buddy_users.json` and create the account again with the same email. "
                    "Your notes and tasks stay in `study_buddy_data_*.json`.")
            st.button("‹  Back to sign in", type="tertiary", on_click=set_auth_mode, args=("signin",))
        else:
            H('<h2>Sign in</h2><p class="auth-sub">Welcome back. Pick up where you left off.</p>')
            if google_enabled():
                st.button("Continue with Google", on_click=st.login, use_container_width=True)
                H('<div class="auth-or">OR EMAIL</div>')
            with st.form("signin", border=False):
                email = st.text_input("Email", placeholder="Email", label_visibility="collapsed")
                pw = st.text_input("Password", placeholder="Password", type="password", label_visibility="collapsed")
                go_ = st.form_submit_button("Sign in", type="primary")
            if go_:
                err = sign_in(email, pw)
                if err:
                    st.error(err)
                else:
                    st.rerun()
            a, b = st.columns(2)
            a.button("Forgot password?", type="tertiary", on_click=set_auth_mode, args=("forgot",))
            b.button("Create an account", type="tertiary", on_click=set_auth_mode, args=("signup",))


if "user" not in st.session_state and google_enabled() and getattr(st.user, "is_logged_in", False):
    st.session_state.user = dict(email=st.user.get("email", ""), name=st.user.get("name") or "Student",
                                 uid=_uid(st.user.get("email", "google")), google=True)
if "user" not in st.session_state:
    auth_screen()
    st.stop()


def data_file() -> Path:
    return BASE / f"study_buddy_data_{st.session_state.user['uid']}.json"


# ------------------------------------------------------------------ data
PALETTE = [("#efe6fb", "#7b4fd0"), ("#e1eefc", "#3f7fd8"), ("#e6f2ea", "#2f7d5b"),
           ("#fdebd3", "#e08a1e"), ("#fde4e4", "#d9534f")]


def _seed() -> dict:
    d = lambda n: (TODAY + timedelta(days=n)).isoformat()
    t = lambda title, subj, pr, due, time, st_: dict(
        id=uuid.uuid4().hex[:8], title=title, subject=subj, priority=pr, due=due, time=time, status=st_)
    return {
        "name": st.session_state.user["name"],
        "streak": {"last": TODAY.isoformat(), "count": 1},
        "sample": True,
        "tasks": [
            t("DBMS assignment", "DBMS", "High", d(0), "10:00", "Completed"),
            t("OOPM revision", "OOPM", "Medium", d(0), "12:00", "Completed"),
            t("Networking notes", "Networking", "Medium", d(0), "15:00", "Pending"),
            t("Mock test (DSA)", "DSA", "Low", d(0), "18:00", "Pending"),
            t("DBMS assignment 2", "DBMS", "High", d(6), "", "In progress"),
            t("OOPM internal test", "OOPM", "Medium", d(8), "", "Pending"),
            t("Project presentation", "CS", "Low", d(13), "", "Pending"),
        ],
        "notes": [
            dict(id=uuid.uuid4().hex[:8], title="DBMS - ER Model", subject="DBMS", pages=10,
                 date=d(-1), blurb="Entity Relationship model with examples and diagrams.", text=""),
            dict(id=uuid.uuid4().hex[:8], title="OOPM - Concepts", subject="OOPM", pages=8,
                 date=d(-3), blurb="Classes, objects, inheritance, polymorphism and more.", text=""),
            dict(id=uuid.uuid4().hex[:8], title="Networking - OSI Model", subject="Networking", pages=12,
                 date=d(-5), blurb="7 layers of OSI model with explanation and diagrams.", text=""),
            dict(id=uuid.uuid4().hex[:8], title="DSA - Arrays", subject="DSA", pages=15,
                 date=d(-7), blurb="Important array concepts, time complexity and practice questions.", text=""),
        ],
        "activity": [],
    }


def load_data() -> dict:
    if data_file().exists():
        try:
            return json.loads(data_file().read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return _seed()


def save() -> None:
    try:
        data_file().write_text(json.dumps(st.session_state.data, indent=1), encoding="utf-8")
    except OSError:
        pass  # read-only hosting: the app still works for the session


if "data" not in st.session_state:
    st.session_state.data = load_data()
    s = st.session_state.data["streak"]
    last = date.fromisoformat(s["last"])
    if last == TODAY - timedelta(days=1):
        s["count"] += 1
    elif last != TODAY:
        s["count"] = 1
    s["last"] = TODAY.isoformat()
    save()

D = st.session_state.data
D.setdefault("cards", {})
D.setdefault("events", [])
st.session_state.setdefault("page", "Dashboard")
st.session_state.setdefault("ai_tool", "Summarize")
st.session_state.setdefault("quiz", None)
st.session_state.setdefault("editor", None)

# ------------------------------------------------------------------ helpers
def go(page: str) -> None:
    st.session_state.page = page
    st.session_state.editor = None


def fmt_day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}"


def fmt_time(hhmm: str) -> str:
    if not hhmm:
        return ""
    return datetime.strptime(hhmm, "%H:%M").strftime("%I:%M %p").lstrip("0")


def pill_priority(p: str) -> str:
    return f'<span class="pill {p.lower()}">{esc(p)}</span>'


def pill_status(s: str) -> str:
    cls = {"In progress": "s-progress", "Pending": "s-pending", "Completed": "s-completed"}[s]
    return f'<span class="pill {cls}">{esc(s)}</span>'


def subjects() -> list[str]:
    seen: list[str] = []
    for item in D["tasks"] + D["notes"]:
        if item["subject"] not in seen:
            seen.append(item["subject"])
    return seen


def toggle_task(tid: str) -> None:
    for t in D["tasks"]:
        if t["id"] == tid:
            t["status"] = "Pending" if t["status"] == "Completed" else "Completed"
    save()


def set_status(tid: str, status: str) -> None:
    for t in D["tasks"]:
        if t["id"] == tid:
            t["status"] = status
    save()


def delete_task(tid: str) -> None:
    D["tasks"] = [t for t in D["tasks"] if t["id"] != tid]
    save()


def delete_note(nid: str) -> None:
    D["notes"] = [n for n in D["notes"] if n["id"] != nid]
    try:
        (INK_DIR / f"{nid}.png").unlink(missing_ok=True)
    except OSError:
        pass
    save()


def toggle_pin(nid: str) -> None:
    for n in D["notes"]:
        if n["id"] == nid:
            n["pinned"] = not n.get("pinned", False)
    save()


def log_event(kind: str, value: float = 1) -> None:
    """Record study progress for the Study Quest (kinds: focus, ai, card, quiz)."""
    D["events"].append({"d": TODAY.isoformat(), "t": kind, "v": value})
    D["events"] = D["events"][-500:]
    save()


def log_activity(text: str) -> None:
    D["activity"].insert(0, {"text": text, "at": datetime.now().isoformat(timespec="seconds")})
    D["activity"] = D["activity"][:20]
    log_event("ai")


def ago(iso: str) -> str:
    delta = datetime.now() - datetime.fromisoformat(iso)
    mins = int(delta.total_seconds() // 60)
    if mins < 1:
        return "Just now"
    if mins < 60:
        return f"{mins} min ago"
    if mins < 60 * 24:
        return f"{mins // 60} hours ago"
    return "Yesterday" if delta.days == 1 else f"{delta.days} days ago"


def page_header(title: str, sub: str, right_html: str = "") -> None:
    left, right = st.columns([3, 1.2])
    with left:
        H(f'<p class="ph-title">{title}</p><p class="ph-sub">{sub}</p>')
    if right_html:
        with right:
            H(right_html)


def card_title(text: str, link_page: str | None = None, key: str = "") -> None:
    if link_page:
        a, b = st.columns([3, 1])
        a.markdown(f'<p class="card-title">{text}</p>', unsafe_allow_html=True)
        b.button("View all  ›", key=f"va_{key}", type="tertiary", on_click=go, args=(link_page,))
    else:
        st.markdown(f'<p class="card-title">{text}</p>', unsafe_allow_html=True)


# ------------------------------------------------------------------ Gemini
def api_key() -> str:
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "") or st.session_state.get("gemini_key", "")


def key_box(label: str = "Gemini API key (kept only for this session)") -> None:
    """Key entry that survives page changes (widget keys are dropped when a page isn't shown)."""
    val = st.text_input(label, value=st.session_state.get("gemini_key", ""), type="password",
                        help="Get a key at aistudio.google.com. For a permanent setup, put GEMINI_API_KEY "
                             "in .streamlit/secrets.toml.")
    st.session_state.gemini_key = val.strip()


def ask_ai(prompt: str, pdf: bytes | None = None) -> str | None:
    key = api_key()
    if genai is None:
        st.error("The `google-generativeai` package is not installed. Run `pip install -r requirements.txt`.")
        return None
    if not key:
        st.warning("Add your Gemini API key above (or in Settings) to use AI tools.")
        return None
    try:
        genai.configure(api_key=key)
        parts = [{"mime_type": "application/pdf", "data": pdf}, prompt] if pdf else prompt
        reply = genai.GenerativeModel(MODEL_NAME).generate_content(parts)
        return reply.text
    except Exception as exc:  # network, quota, bad key, blocked content…
        st.error(f"The AI request failed: {exc}")
        return None


def clip(text: str, limit: int = 30000) -> str:
    return text[:limit]


def read_pdf(file) -> tuple[str, int]:
    reader = PdfReader(file)
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    return text, len(reader.pages)


def pdf_file(nid: str) -> Path:
    return PDF_DIR / f"{nid}.pdf"


def add_note_from_pdf(file, title: str | None = None, subject: str = "Others") -> dict | None:
    try:
        text, pages = read_pdf(file)
    except Exception:
        st.error("That PDF could not be read. Try another file.")
        return None
    nid = uuid.uuid4().hex[:8]
    try:
        PDF_DIR.mkdir(exist_ok=True)
        pdf_file(nid).write_bytes(file.getvalue())
    except OSError:
        pass
    note = dict(id=nid, title=title or Path(file.name).stem, subject=subject,
                pages=pages, date=TODAY.isoformat(),
                blurb=(re.sub(r"\s+", " ", text).strip()[:90] + "…") if text.strip()
                else "Scanned or image-based PDF. The AI will read it directly.",
                text=text, kind="pdf")
    D["notes"].insert(0, note)
    save()
    return note


def has_material(n: dict) -> bool:
    return bool(n.get("text", "").strip()) or pdf_file(n["id"]).exists()


def source_picker(key: str) -> tuple[str, str, str] | None:
    """Choose a note, or upload a new PDF. Returns (text, title, note_id)."""
    usable = [n for n in D["notes"] if has_material(n)]
    options = [n["title"] for n in usable] + ["Upload a new PDF…"]
    choice = st.selectbox("Study material", options, key=f"src_{key}",
                          index=0 if usable else len(options) - 1)
    if choice == "Upload a new PDF…":
        up = st.file_uploader("Upload your PDF notes", type="pdf", key=f"up_{key}")
        if up is None:
            return None
        done = st.session_state.setdefault("uploaded_ids", {})
        if up.file_id not in done:
            note = add_note_from_pdf(up)
            if note is None:
                return None
            done[up.file_id] = note["id"]
        note = next((n for n in D["notes"] if n["id"] == done[up.file_id]), None)
    else:
        note = next(n for n in usable if n["title"] == choice)
    if not note:
        return None
    if not note.get("text", "").strip() and pdf_file(note["id"]).exists():
        st.info("This PDF has no selectable text (scanned pages or images), so the AI will read the file itself.")
    return note["text"], note["title"], note["id"]


def material(src: tuple[str, str, str]) -> tuple[str, bytes | None]:
    """Text for the prompt, plus raw PDF bytes when the PDF has no extractable text."""
    text, _, nid = src
    if text.strip():
        return "Notes:\n" + clip(text), None
    return "The notes are in the attached PDF.", pdf_file(nid).read_bytes()


# ------------------------------------------------------------------ dialogs
@st.dialog("Add task")
def add_task_dialog() -> None:
    title = st.text_input("Task")
    known = subjects() + ["New subject…"]
    subj = st.selectbox("Subject", known)
    if subj == "New subject…":
        subj = st.text_input("Subject name")
    c1, c2, c3 = st.columns(3)
    prio = c1.selectbox("Priority", ["High", "Medium", "Low"], index=1)
    due = c2.date_input("Due date", TODAY)
    time = c3.time_input("Time", value=None)
    if st.button("Add task", type="primary"):
        if not title.strip() or not subj.strip():
            st.error("Enter a task and a subject.")
            return
        D["tasks"].append(dict(id=uuid.uuid4().hex[:8], title=title.strip(), subject=subj.strip(),
                               priority=prio, due=due.isoformat(),
                               time=time.strftime("%H:%M") if time else "", status="Pending"))
        save()
        st.rerun()


@st.dialog("Import notes")
def new_note_dialog() -> None:
    title = st.text_input("Title")
    known = subjects() + ["New subject…"]
    subj = st.selectbox("Subject", known)
    if subj == "New subject…":
        subj = st.text_input("Subject name")
    up = st.file_uploader("Upload a PDF (optional)", type="pdf")
    body = st.text_area("…or type your note", height=120)
    if st.button("Save note", type="primary"):
        if up is not None:
            note = add_note_from_pdf(up, title.strip() or None, subj.strip() or "Others")
            if note:
                st.rerun()
        elif title.strip() and body.strip():
            D["notes"].insert(0, dict(id=uuid.uuid4().hex[:8], title=title.strip(),
                                      subject=subj.strip() or "Others", pages=1, date=TODAY.isoformat(),
                                      blurb=body.strip()[:90], text=body.strip(), kind="text"))
            save()
            st.rerun()
        else:
            st.error("Add a title and some text, or upload a PDF.")


# ------------------------------------------------------------------ sidebar
NAV = [("Dashboard", ":material/home:"), ("Tasks", ":material/checklist:"),
       ("Focus Mode", ":material/timer:"), ("Notes", ":material/description:"),
       ("AI Tools", ":material/auto_awesome:"), ("Study Quest", ":material/emoji_events:"), ("Settings", ":material/settings:")]

with st.sidebar:
    H('<div class="sb-brand"><div class="sb-logo">🌱</div>Study Buddy</div>')
    active = st.session_state.page
    for name, icon in NAV:
        st.button(f"{icon} {name}", key=f"nav_{name}", on_click=go, args=(name,),
                  type="primary" if name == active else "secondary", use_container_width=True)
    st.button(":material/logout: Sign out", key="nav_signout", on_click=sign_out, use_container_width=True)
    H('<div class="sb-tip"><span class="leaf">🌿</span><span>Small steps<br>every day lead to<br>big results! ✨</span></div>')


# ------------------------------------------------------------------ pages
def page_dashboard() -> None:
    hour = datetime.now().hour
    greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    left, right = st.columns([3, 1])
    with left:
        H(f'<p class="ph-title">{greet}, {esc(D["name"])}! 👋</p>'
          '<p class="ph-sub">Keep going! You\'re doing great.</p>')
    with right:
        H(f'<p class="ph-date">{TODAY:%a}, {TODAY.day} {TODAY:%b %Y}</p>')

    today_tasks = sorted([t for t in D["tasks"] if t["due"] == TODAY.isoformat()], key=lambda t: t["time"] or "99")
    done = sum(t["status"] == "Completed" for t in today_tasks)
    total = len(today_tasks)
    pct = round(100 * done / total) if total else 0
    circ = 2 * 3.14159 * 36
    active_subjects = len({t["subject"] for t in D["tasks"] if t["status"] != "Completed"})

    c1, c2, c3 = st.columns([1.35, 1, 1])
    with c1:
        H(f'''<div class="card stat">
          <div class="ring"><svg width="84" height="84" viewBox="0 0 84 84">
            <circle cx="42" cy="42" r="36" fill="none" stroke="#e3ebe4" stroke-width="7"/>
            <circle cx="42" cy="42" r="36" fill="none" stroke="#2f7d5b" stroke-width="7" stroke-linecap="round"
              stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ * (1 - pct / 100):.1f}"/></svg>
            <div class="pct">{pct}%</div></div>
          <div style="flex:1"><div style="font-weight:600">Today's Progress</div>
            <div class="lbl">{done} of {total} tasks completed</div>
            <div class="bar"><i style="width:{pct}%"></i></div></div></div>''')
    with c2:
        H(f'<div class="card stat"><div class="ico">🔥</div><div><div class="big">{D["streak"]["count"]}</div>'
          f'<div class="lbl" style="color:var(--ink)">Day Streak</div><div class="lbl">Keep it up!</div></div></div>')
    with c3:
        H(f'<div class="card stat"><div class="ico doc">📄</div><div><div class="big">{active_subjects}</div>'
          f'<div class="lbl" style="color:var(--ink)">Subjects</div><div class="lbl">Active this week</div></div></div>')

    st.write("")
    a, b = st.columns([1.15, 1])
    with a:
        with st.container(border=True):
            card_title("Today's Tasks", "Tasks", "today")
            if not today_tasks:
                H('<div class="empty">Nothing due today. Add a task to plan your day.</div>')
            for t in today_tasks:
                k1, k2, k3, k4 = st.columns([0.07, 0.5, 0.2, 0.23], vertical_alignment="center")
                k1.checkbox("done", value=t["status"] == "Completed", label_visibility="collapsed",
                            key=f"dchk_{t['id']}_{t['status'] == 'Completed'}", on_change=toggle_task, args=(t["id"],))
                k2.markdown(f'<span class="row-title">{esc(t["title"])}</span>', unsafe_allow_html=True)
                k3.markdown(pill_priority(t["priority"]), unsafe_allow_html=True)
                k4.markdown(f'<div class="row-time">{fmt_time(t["time"])}</div>', unsafe_allow_html=True)
    with b:
        with st.container(border=True):
            card_title("Upcoming Deadlines", "Tasks", "deadlines")
            upcoming = sorted([t for t in D["tasks"] if t["status"] != "Completed" and t["due"] > TODAY.isoformat()],
                              key=lambda t: t["due"])[:3]
            if not upcoming:
                H('<div class="empty">No upcoming deadlines. Enjoy the breathing room.</div>')
            for t in upcoming:
                H(f'''<div class="dl {t["priority"].lower()}" style="display:flex;justify-content:space-between;
                      align-items:center;margin:10px 0"><div><div class="row-title">{esc(t["title"])}</div>
                      <div class="row-sub">{fmt_day(t["due"])}, {t["due"][:4]}</div></div>{pill_priority(t["priority"])}</div>''')


def calendar_html() -> str:
    due_days = {date.fromisoformat(t["due"]).day for t in D["tasks"]
                if t["status"] != "Completed" and date.fromisoformat(t["due"]).month == TODAY.month
                and date.fromisoformat(t["due"]).year == TODAY.year}
    weeks = calendar.Calendar(0).monthdayscalendar(TODAY.year, TODAY.month)
    head = "".join(f"<th>{d}</th>" for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    body = ""
    for w in weeks:
        body += "<tr>"
        for day in w:
            if day == 0:
                body += '<td class="dim"><span>&nbsp;</span></td>'
                continue
            cls = " ".join(c for c, on in [("today", day == TODAY.day), ("due", day in due_days)] if on)
            body += f'<td class="{cls}"><span>{day}</span></td>'
        body += "</tr>"
    return f'<table class="cal"><tr>{head}</tr>{body}</table>'


def page_tasks() -> None:
    left, right = st.columns([3, 1])
    with left:
        H('<p class="ph-title">Tasks &amp; Study Planner</p>'
          '<p class="ph-sub">Organize your tasks, track progress and stay on top of your goals.</p>')
    with right:
        if st.button("＋  Add Task", type="primary", use_container_width=True):
            add_task_dialog()

    f1, f2 = st.columns([3, 1])
    flt = f1.radio("Filter", ["All", "Today", "Upcoming", "Completed"], horizontal=True,
                   label_visibility="collapsed", key="tasks_filter")
    subj = f2.selectbox("Subject", ["All Subjects"] + subjects(), label_visibility="collapsed")

    tasks = list(D["tasks"])
    iso = TODAY.isoformat()
    if flt == "Today":
        tasks = [t for t in tasks if t["due"] == iso]
    elif flt == "Upcoming":
        tasks = [t for t in tasks if t["due"] > iso and t["status"] != "Completed"]
    elif flt == "Completed":
        tasks = [t for t in tasks if t["status"] == "Completed"]
    if subj != "All Subjects":
        tasks = [t for t in tasks if t["subject"] == subj]
    tasks.sort(key=lambda t: (t["due"], t["time"]))

    cal_col, tbl_col = st.columns([1, 2.5])
    with cal_col:
        with st.container(border=True):
            H(f'<p class="card-title">{TODAY:%B %Y}</p>')
            H(calendar_html())
            H('<p class="th" style="margin-top:14px">Priority</p><div class="legend">'
              '<span><i class="dot" style="background:#e8756c"></i>High</span>'
              '<span><i class="dot" style="background:#e8b04a"></i>Medium</span>'
              '<span><i class="dot" style="background:#2f7d5b"></i>Low</span></div>')
    with tbl_col:
        with st.container(border=True):
            widths = [0.06, 0.27, 0.14, 0.12, 0.13, 0.17, 0.05]
            for col, name in zip(st.columns(widths), ["", "Task", "Subject", "Priority", "Due Date", "Status", ""]):
                col.markdown(f'<span class="th">{name}</span>', unsafe_allow_html=True)
            H('<hr class="soft">')
            if not tasks:
                H('<div class="empty">No tasks here yet. Use “Add Task” to plan your next step.</div>')
            for t in tasks:
                c = st.columns(widths, vertical_alignment="center")
                c[0].checkbox("done", value=t["status"] == "Completed", label_visibility="collapsed",
                              key=f"chk_{t['id']}_{t['status'] == 'Completed'}", on_change=toggle_task, args=(t["id"],))
                c[1].markdown(f'<span class="row-title">{esc(t["title"])}</span>', unsafe_allow_html=True)
                c[2].markdown(f'<span class="subj">{esc(t["subject"])}</span>', unsafe_allow_html=True)
                c[3].markdown(pill_priority(t["priority"]), unsafe_allow_html=True)
                c[4].markdown(f'<span class="row-sub" style="color:var(--ink)">{fmt_day(t["due"])}</span>', unsafe_allow_html=True)
                c[5].markdown(pill_status(t["status"]), unsafe_allow_html=True)
                with c[6].popover("⋮"):
                    st.button("Mark in progress", key=f"ip_{t['id']}", on_click=set_status, args=(t["id"], "In progress"))
                    st.button("Mark pending", key=f"pe_{t['id']}", on_click=set_status, args=(t["id"], "Pending"))
                    st.button("Delete", key=f"del_{t['id']}", on_click=delete_task, args=(t["id"],))


focus_component = components.declare_component("sb_focus", path=str(BASE / "focus_component"))


def page_focus() -> None:
    page_header("Focus Mode", "Stay focused. Get more done.")
    left, right = st.columns([1, 1.15])
    with right:
        with st.container(border=True):
            H('<p class="card-title">Session Settings</p>')
            work = st.selectbox("Work Duration", [15, 20, 25, 30, 45, 50], index=2, format_func=lambda m: f"{m} minutes")
            short = st.selectbox("Break Duration", [3, 5, 10], index=1, format_func=lambda m: f"{m} minutes")
            long_ = st.selectbox("Long Break Duration", [10, 15, 20, 30], index=1, format_func=lambda m: f"{m} minutes")
            n = st.selectbox("Long Break After", [2, 3, 4, 5], index=2, format_func=lambda m: f"{m} sessions")
        H('<div class="motive" style="margin-top:14px"><span style="font-size:1.4rem">💡</span>'
          '<span><b>Focus tip</b><br>Keep your phone away and find a quiet place to study. '
          'Finished sessions count towards your Study Quest.</span></div>')
    with left:
        done = focus_component(work=work, short=short, long=long_, n=n, key="focus_cmp", default=None)
        if isinstance(done, dict) and done.get("event") != D.get("last_focus_event"):
            D["last_focus_event"] = done["event"]
            log_event("focus", float(done.get("minutes", work)))
            st.toast("Session complete. Nice work! 🌱")


def note_color(subject: str) -> tuple[str, str]:
    return PALETTE[sum(map(ord, subject)) % len(PALETTE)]


ink_component = components.declare_component("sb_ink", path=str(BASE / "ink_component"))


def ink_file(nid: str) -> Path:
    return INK_DIR / f"{nid}.png"


def save_ink(nid: str, data_url: str) -> None:
    try:
        INK_DIR.mkdir(exist_ok=True)
        if data_url:
            ink_file(nid).write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
        else:
            ink_file(nid).unlink(missing_ok=True)
    except OSError:
        st.warning("Could not store the handwriting on this device.")


def open_editor(nid: str | None = None) -> None:
    st.session_state.editor = nid or uuid.uuid4().hex[:8]


def close_editor() -> None:
    st.session_state.editor = None


def page_editor() -> None:
    nid = st.session_state.editor
    existing = next((n for n in D["notes"] if n["id"] == nid), None)
    note = existing or dict(id=nid, title="", subject=(subjects() or ["Others"])[0], text="", paper="Lined", pinned=False)

    c = st.columns([0.9, 3, 1.6, 1.3, 1.1], vertical_alignment="bottom")
    c[0].button("‹  Back", on_click=close_editor)
    title = c[1].text_input("Title", note["title"], key=f"ed_t_{nid}", placeholder="Untitled note")
    subj_opts = list(dict.fromkeys(subjects() + ["Others", note["subject"]]))
    subject = c[2].selectbox("Subject", subj_opts, index=subj_opts.index(note["subject"]), key=f"ed_s_{nid}")
    papers = ["Plain", "Lined", "Grid"]
    paper = c[3].selectbox("Paper", papers, index=papers.index(note.get("paper", "Lined")), key=f"ed_p_{nid}")
    save_clicked = c[4].button("Save note", type="primary", use_container_width=True)

    t_draw, t_type = st.tabs(["✎  Handwrite", "Aa  Type"])
    with t_draw:
        initial = ""
        if ink_file(nid).exists():
            initial = "data:image/png;base64," + base64.b64encode(ink_file(nid).read_bytes()).decode()
        drawn = ink_component(initial=initial, paper=paper, key=f"ink_{nid}", default=None)
    with t_type:
        text = st.text_area("Note text", note.get("text", ""), height=420, key=f"ed_x_{nid}",
                            label_visibility="collapsed", placeholder="Type your note here…")

    if save_clicked:
        if drawn is not None:
            save_ink(nid, drawn)
        has_ink = ink_file(nid).exists()
        if not (title.strip() or text.strip() or has_ink):
            st.error("Add a title, some text or a drawing before saving.")
            return
        data = dict(id=nid, title=title.strip() or "Untitled note", subject=subject, pages=1,
                    date=TODAY.isoformat(), blurb=text.strip()[:90] or ("Handwritten note" if has_ink else ""),
                    text=text.strip(), kind="sketch" if has_ink else "text", paper=paper,
                    pinned=note.get("pinned", False))
        if existing:
            existing.update(data)
        else:
            D["notes"].insert(0, data)
        save()
        close_editor()
        st.rerun()


def page_notes() -> None:
    if st.session_state.editor:
        return page_editor()
    left, right = st.columns([2.2, 1])
    with left:
        H('<p class="ph-title">Notes &amp; Resources</p><p class="ph-sub">Save, organize and access your study material anytime.</p>')
    q = right.text_input("Search", placeholder="Search notes, subjects…", label_visibility="collapsed")

    subj = st.radio("Subject", ["All"] + subjects(), horizontal=True, label_visibility="collapsed", key="notes_filter")
    notes = [n for n in D["notes"] if (subj == "All" or n["subject"] == subj)
             and (not q or q.lower() in (n["title"] + n["subject"] + n["blurb"]).lower())]
    notes.sort(key=lambda n: not n.get("pinned", False))

    side, grid = st.columns([1, 2.4])
    with side:
        with st.container(border=True):
            st.button("＋  New Note", type="primary", use_container_width=True, on_click=open_editor)
            if st.button("⬆  Import PDF", use_container_width=True):
                new_note_dialog()
            H('<p class="card-title" style="margin-top:14px">Recent</p>')
            for n in sorted(D["notes"], key=lambda n: n["date"], reverse=True)[:4]:
                H(f'<div class="recent-item"><span class="ri">📘</span><div><div class="row-title" style="font-size:.8rem">'
                  f'{esc(n["title"])}</div><div class="row-sub">{fmt_day(n["date"])}, {n["date"][:4]}</div></div></div>')
    with grid:
        if not notes:
            H('<div class="card empty">No notes match. Create one with “New Note” or import a PDF.</div>')
        for i in range(0, len(notes), 2):
            cols = st.columns(2)
            for col, n in zip(cols, notes[i:i + 2]):
                bg, fg = note_color(n["subject"])
                pin = "📌 " if n.get("pinned") else ""
                with col, st.container(border=True):
                    a, b = st.columns([5, 1], vertical_alignment="center")
                    a.markdown(f'<div style="display:flex;gap:12px;align-items:center"><div class="note-ico" '
                               f'style="background:{bg};color:{fg}">▤</div><span class="note-title">{pin}{esc(n["title"])}</span></div>',
                               unsafe_allow_html=True)
                    with b.popover("⋮"):
                        if n.get("kind") != "pdf":
                            st.button("Edit", key=f"ed_{n['id']}", on_click=open_editor, args=(n["id"],))
                        st.button("Unpin" if n.get("pinned") else "Pin to top", key=f"pn_{n['id']}",
                                  on_click=toggle_pin, args=(n["id"],))
                        st.button("Delete note", key=f"dn_{n['id']}", on_click=delete_note, args=(n["id"],))
                    if ink_file(n["id"]).exists():
                        st.image(str(ink_file(n["id"])), use_container_width=True)
                    H(f'<div class="note-blurb">{esc(n["blurb"])}</div><div class="note-foot">'
                      f'<span class="chip">{esc(n["subject"])}</span>'
                      f'<span>{n["pages"]} page{"s" if n["pages"] != 1 else ""}</span></div>')


TOOLS = [
    ("Summarize", "📄", "#e3f4ea", "Short, clear summary of your PDF."),
    ("Explain a topic", "💡", "#fdf3cf", "Simple explanations of any topic in it."),
    ("Ask AI", "💬", "#e1eefc", "Chat with your material."),
    ("Quiz", "📝", "#ebe9fb", "Exam-pressure practice with a score."),
    ("Flashcards", "🗂️", "#e0f7ea", "Active recall until it sticks."),
    ("Mind map", "🕸️", "#efe9fb", "See how topics connect."),
    ("Podcast", "🎧", "#e8f1fd", "Listen to a short audio lesson."),
    ("Games", "🎮", "#fde9ee", "Learn by playing: memory match."),
]


def set_tool(name: str) -> None:
    st.session_state.ai_tool = name


def gen_cache() -> dict:
    return st.session_state.setdefault("gen", {})


def parse_json(raw: str):
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        return json.loads(raw)
    except ValueError:
        m = re.search(r"(\{.*\}|\[.*\])", raw, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except ValueError:
                return None
    return None


def result_box(text: str, filename: str | None = None) -> None:
    with st.container(border=True):
        st.markdown(text)
    if filename:
        st.download_button("Download as text", text, file_name=filename)


def ask_json(prompt: str, src: tuple[str, str, str]):
    body, pdf = material(src)
    with st.spinner("Working on it… large PDFs can take a minute."):
        raw = ask_ai(prompt.replace("{NOTES}", body), pdf)
    if raw is None:
        return None
    data = parse_json(raw)
    if data is None:
        st.error("The AI reply could not be read. Please try again.")
    return data


# ---- text tools -------------------------------------------------------
def panel_summary(src) -> None:
    key = (src[2], "summary")
    if st.button("Regenerate summary" if key in gen_cache() else "Summarize notes", type="primary"):
        body, pdf = material(src)
        with st.spinner("Writing your summary… large PDFs can take a minute."):
            out = ask_ai(f"Summarize these notes in simple language with short headings and bullet points.\n\n{body}", pdf)
        if out:
            gen_cache()[key] = out
            log_activity(f"Summary generated for {src[1]}")
    if key in gen_cache():
        result_box(gen_cache()[key], f"{src[1]}-summary.txt")


def panel_explain(src) -> None:
    topic = st.text_input("Topic to explain", placeholder="e.g. Normalization", key=f"topic_{src[2]}")
    key = (src[2], "explain", topic.strip().lower())
    if st.button("Explain topic", type="primary", disabled=not topic.strip()):
        body, pdf = material(src)
        with st.spinner("Thinking…"):
            out = ask_ai(f"Explain the topic '{topic}' simply, using these notes. Use a short example.\n\n{body}", pdf)
        if out:
            gen_cache()[key] = out
            log_activity(f"Explained “{topic}” from {src[1]}")
    if key in gen_cache():
        result_box(gen_cache()[key])


def panel_chat(src) -> None:
    msgs = st.session_state.setdefault("chats", {}).setdefault(src[2], [])
    if not msgs:
        H('<div class="empty">Ask anything about this PDF. Answers come only from your material.</div>')
    for m in msgs:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    q = st.chat_input("Ask a question about this PDF", key=f"chat_{src[2]}")
    if q:
        with st.chat_message("user"):
            st.markdown(q)
        history = "\n".join(f"{m['role']}: {m['content']}" for m in msgs[-6:])
        body, pdf = material(src)
        prompt = ("You are a study assistant. Use ONLY the notes below.\n\n" f"{body}\n\n"
                  f"Conversation so far:\n{history}\n\nQuestion: {q}\n\n"
                  "If the answer is not in the notes, say: 'Answer not available in uploaded notes.'")
        with st.chat_message("assistant"):
            with st.spinner("Looking through your notes…"):
                out = ask_ai(prompt, pdf)
            if out:
                st.markdown(out)
        if out:
            msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": out}]
            log_activity(f"Answered question on {src[1]}")


# ---- quiz -------------------------------------------------------------
def parse_quiz(raw) -> list[dict] | None:
    items = parse_json(raw) if isinstance(raw, str) else raw
    if isinstance(items, dict):
        items = items.get("questions")
    try:
        ok = [q for q in items if len(q["options"]) == 4 and 0 <= int(q["answer"]) < 4]
        return [dict(q=q["question"], options=q["options"], answer=int(q["answer"]),
                     why=q.get("explanation", "")) for q in ok] or None
    except (TypeError, KeyError, ValueError):
        return None


def record_answer(i: int) -> None:
    quiz = st.session_state.quiz
    val = st.session_state.get(f"qa_{i}")
    if val is not None:
        quiz["answers"][i] = quiz["questions"][i]["options"].index(val)


def quiz_step(delta: int) -> None:
    st.session_state.quiz["i"] += delta


def clear_quiz_widgets() -> None:
    for k in [k for k in st.session_state if str(k).startswith("qa_")]:
        del st.session_state[k]


def finish_quiz(quiz: dict) -> None:
    quiz["done"] = True
    score = sum(quiz["answers"].get(k) == q["answer"] for k, q in enumerate(quiz["questions"]))
    log_event("quiz", score / len(quiz["questions"]))


def panel_quiz(src) -> None:
    nid = src[2]
    a, b, c = st.columns([1, 1, 1], vertical_alignment="bottom")
    level = a.selectbox("Difficulty", ["Easy", "Medium", "Hard"], index=1)
    n_q = b.selectbox("Questions", [5, 10, 15])
    if c.button("✦  Generate Quiz", type="primary", use_container_width=True):
        prompt = (f"Create {n_q} {level.lower()}-level multiple-choice questions strictly from these notes.\n\n{{NOTES}}\n\n"
                  "Return ONLY a JSON array, no markdown. Each item: {\"question\": str, \"options\": [4 strings], "
                  "\"answer\": index 0-3 of the correct option, \"explanation\": 1-2 sentences saying why the correct "
                  "answer is right and, if useful, why a tempting wrong option is wrong}. "
                  "Spread correct answers across positions and never use 'All of the above'.")
        qs = parse_quiz(ask_json(prompt, src))
        if qs:
            st.session_state.quiz = dict(nid=nid, questions=qs, i=0, answers={}, level=level, done=False)
            clear_quiz_widgets()
            log_activity(f"Quiz created from {src[1]}")
            st.rerun()
        elif qs is None:
            st.error("The quiz could not be created. Please try again.")

    quiz = st.session_state.quiz
    st.write("")
    if not quiz or quiz["nid"] != nid:
        H('<div class="empty">Choose a difficulty and number of questions, then select “Generate Quiz”.</div>')
        return
    qs, i = quiz["questions"], quiz["i"]

    if quiz["done"]:
        score = sum(quiz["answers"].get(k) == q["answer"] for k, q in enumerate(qs))
        pct = round(100 * score / len(qs))
        circ = 2 * 3.14159 * 46
        msg = ("Outstanding! You've got this material down." if pct >= 90 else
               "Great work. A little review will lock it in." if pct >= 70 else
               "Good start. The explanations below will help you improve." if pct >= 40 else
               "Tough round. Review the explanations and try again.")
        H(f'''<div style="display:flex;gap:24px;align-items:center;margin-bottom:6px">
          <div class="qring"><svg width="120" height="120" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="46" fill="none" stroke="#e3ebe4" stroke-width="10"/>
            <circle cx="60" cy="60" r="46" fill="none" stroke="#2f7d5b" stroke-width="10" stroke-linecap="round"
             stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ * (1 - pct / 100):.1f}"/></svg>
            <div class="in"><small>SCORE</small><b>{score}/{len(qs)}</b></div></div>
          <div><p class="q-h">{pct}% correct</p><p class="ph-sub" style="margin:0">{msg}</p></div></div>''')
        wrong = [(k, q) for k, q in enumerate(qs) if quiz["answers"].get(k) != q["answer"]]
        if wrong:
            H('<p class="card-title" style="margin-top:14px">Review your mistakes</p>')
            for k, q in wrong:
                ch = quiz["answers"].get(k)
                yours = esc(q["options"][ch]) if ch is not None else "No answer"
                H(f'<div class="mistake"><b>Q{k + 1}. {esc(q["q"])}</b><br>Your answer: {yours}<br>'
                  f'Correct answer: <b>{esc(q["options"][q["answer"]])}</b>'
                  f'<div class="why">💡 {esc(q["why"])}</div></div>')
        else:
            st.success("Perfect score! No mistakes to review. 🎉")
        with st.expander("See all questions"):
            for k, q in enumerate(qs):
                ok = quiz["answers"].get(k) == q["answer"]
                st.markdown(f"**Q{k + 1}. {q['q']}**  \n{'✅' if ok else '❌'} Correct answer: {q['options'][q['answer']]}  \n{q['why']}")
        r1, r2, _ = st.columns([1, 1.6, 2])
        if r1.button("Retake quiz"):
            quiz.update(i=0, answers={}, done=False)
            clear_quiz_widgets()
            st.rerun()
        if wrong and r2.button("Make flashcards from mistakes"):
            deck = D["cards"].setdefault(nid, [])
            deck += [dict(f=q["q"], b=f"{q['options'][q['answer']]}. {q['why']}") for _, q in wrong]
            save()
            st.session_state.fc = None
            st.toast(f"Added {len(wrong)} cards to your flashcards.")
        return

    q = qs[i]
    h1, h2 = st.columns([5, 1])
    h1.markdown(f'<div class="q-text">Q{i + 1}. {esc(q["q"])}</div>', unsafe_allow_html=True)
    h2.markdown(f'<div class="q-count">{i + 1} / {len(qs)}</div>', unsafe_allow_html=True)
    st.radio("Answer", q["options"], index=quiz["answers"].get(i), key=f"qa_{i}", label_visibility="collapsed",
             on_change=record_answer, args=(i,))
    p, _, nx = st.columns([1, 3, 1])
    p.button("‹  Previous", disabled=i == 0, on_click=quiz_step, args=(-1,))
    if i < len(qs) - 1:
        nx.button("Next  ›", type="primary", on_click=quiz_step, args=(1,))
    elif nx.button("Finish", type="primary"):
        record_answer(i)
        finish_quiz(quiz)
        st.rerun()


# ---- flashcards -------------------------------------------------------
def fc_show() -> None:
    st.session_state.fc["show"] = True


def fc_rate(known: bool) -> None:
    fc = st.session_state.fc
    idx = fc["queue"].pop(0)
    if known:
        fc["known"] += 1
    else:
        fc["again"] += 1
        fc["queue"].append(idx)
    fc["show"] = False
    log_event("card", 1)


def fc_reset(nid: str, total: int) -> None:
    st.session_state.fc = dict(nid=nid, queue=list(range(total)), show=False, known=0, again=0)


def panel_flashcards(src) -> None:
    nid = src[2]
    deck = D["cards"].get(nid, [])
    a, b = st.columns([1, 1], vertical_alignment="bottom")
    count = a.selectbox("Cards to create", [10, 15, 20])
    if b.button("Regenerate deck" if deck else "✦  Generate flashcards", type="primary", use_container_width=True):
        prompt = (f"Create {count} flashcards from these notes that test the most important ideas, definitions and "
                  "facts. Keep the front to a short question or term and the back to a clear answer of at most "
                  "two sentences.\n\n{NOTES}\n\nReturn ONLY a JSON array of {\"front\": str, \"back\": str}.")
        data = ask_json(prompt, src)
        cards = [dict(f=str(c["front"]), b=str(c["back"])) for c in data if isinstance(c, dict) and "front" in c and "back" in c] \
            if isinstance(data, list) else []
        if cards:
            D["cards"][nid] = cards
            save()
            fc_reset(nid, len(cards))
            log_activity(f"Flashcards created from {src[1]}")
            st.rerun()
        elif data is not None:
            st.error("No flashcards came back. Please try again.")
    if not deck:
        H('<div class="empty">No cards yet. Generate a deck from this PDF to start active recall.</div>')
        return
    fc = st.session_state.get("fc")
    if not fc or fc["nid"] != nid or max(fc["queue"] + [-1]) >= len(deck):
        fc_reset(nid, len(deck))
        fc = st.session_state.fc
    st.progress(fc["known"] / len(deck), text=f"{fc['known']} of {len(deck)} known · {len(fc['queue'])} to go")
    if not fc["queue"]:
        st.success("Deck complete! 🎉 Every card is in your memory bank.")
        st.button("Study again", on_click=fc_reset, args=(nid, len(deck)))
    else:
        card = deck[fc["queue"][0]]
        back = f'<div class="back">{esc(card["b"])}</div>' if fc["show"] else ""
        H(f'<div class="fcard"><div class="side">{"ANSWER" if fc["show"] else "QUESTION"}</div>'
          f'<div class="front">{esc(card["f"])}</div>{back}</div>')
        if not fc["show"]:
            st.button("Show answer", type="primary", on_click=fc_show, use_container_width=True)
        else:
            x, y = st.columns(2)
            x.button("↻  Still learning", on_click=fc_rate, args=(False,), use_container_width=True)
            y.button("✓  Got it", type="primary", on_click=fc_rate, args=(True,), use_container_width=True)
    with st.expander("See all cards"):
        for c in deck:
            st.markdown(f"**{c['f']}**  \n{c['b']}")


# ---- mind map ---------------------------------------------------------
def mindmap_dot(tree: dict) -> str:
    fills = [("#2f7d5b", "white"), ("#cfe8d9", "#1e2a24"), ("#eef6f1", "#1e2a24"), ("#ffffff", "#1e2a24")]
    lines = ["digraph G {", "rankdir=LR;", 'bgcolor="transparent";', "ranksep=0.5;",
             'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=12, color="#2f7d5b", margin="0.14,0.08"];',
             'edge [color="#9bb8a8"];']
    counter = [0]

    def walk(node: dict, depth: int, parent: int | None) -> None:
        i = counter[0]
        counter[0] += 1
        label = textwrap.fill(str(node.get("title", "")), 24).replace('"', "'").replace("\n", "\\n")
        fill, font = fills[min(depth, 3)]
        lines.append(f'n{i} [label="{label}", fillcolor="{fill}", fontcolor="{font}"];')
        if parent is not None:
            lines.append(f"n{parent} -> n{i};")
        if depth < 3:
            for ch in (node.get("children") or [])[:8]:
                if isinstance(ch, dict):
                    walk(ch, depth + 1, i)

    walk(tree, 0, None)
    return "\n".join(lines + ["}"])


def panel_mindmap(src) -> None:
    key = (src[2], "mindmap")
    if st.button("Regenerate mind map" if key in gen_cache() else "✦  Create mind map", type="primary"):
        prompt = ("Create a mind map of the main ideas in these notes.\n\n{NOTES}\n\nReturn ONLY JSON shaped like "
                  "{\"title\": str, \"children\": [{\"title\": str, \"children\": [{\"title\": str}]}]}. "
                  "Use 4 to 7 main branches with up to 4 sub-points each. Keep every title under 6 words.")
        tree = ask_json(prompt, src)
        if isinstance(tree, dict) and tree.get("title"):
            gen_cache()[key] = tree
            log_activity(f"Mind map created for {src[1]}")
        elif tree is not None:
            st.error("The mind map could not be built. Please try again.")
    if key in gen_cache():
        st.graphviz_chart(mindmap_dot(gen_cache()[key]), use_container_width=True)
    else:
        H('<div class="empty">Create a mind map to see how the topics in this PDF connect.</div>')


# ---- podcast ----------------------------------------------------------
def panel_podcast(src) -> None:
    key = (src[2], "podcast")
    if st.button("Regenerate episode" if key in gen_cache() else "✦  Create audio lesson", type="primary"):
        prompt = ("Write a friendly two-host study podcast (Alex and Sam) that teaches the key ideas in these notes in "
                  "about 14 short turns. Be accurate, conversational and include one memory tip.\n\n{NOTES}\n\n"
                  "Return ONLY a JSON array of {\"speaker\": \"Alex\" or \"Sam\", \"text\": str}.")
        data = ask_json(prompt, src)
        lines = [dict(s=0 if str(t.get("speaker", "")).lower().startswith("a") else 1, n=str(t["speaker"]), t=str(t["text"]))
                 for t in data if isinstance(t, dict) and "text" in t and "speaker" in t] if isinstance(data, list) else []
        if lines:
            gen_cache()[key] = lines
            log_activity(f"Audio lesson created for {src[1]}")
        elif data is not None:
            st.error("The episode could not be created. Please try again.")
    if key in gen_cache():
        page = (BASE / "podcast.html").read_text(encoding="utf-8")
        data = json.dumps(gen_cache()[key]).replace("</", "<\\/")
        components.html(page.replace("__DATA__", data), height=520)
    else:
        H('<div class="empty">Create an audio lesson and listen to your PDF as a short two-host podcast.</div>')


# ---- games ------------------------------------------------------------
def mm_start(nid: str) -> None:
    deck = D["cards"].get(nid, [])
    pick = random.sample(deck, min(6, len(deck)))
    tiles = []
    for k, c in enumerate(pick):
        tiles.append(dict(pair=k, text=c["f"][:60]))
        tiles.append(dict(pair=k, text=c["b"][:70]))
    random.shuffle(tiles)
    st.session_state.mm = dict(nid=nid, tiles=tiles, open=[], matched=[], moves=0, rewarded=False)


def mm_click(i: int) -> None:
    s = st.session_state.mm
    if len(s["open"]) == 2:
        s["open"] = []
    s["open"].append(i)
    if len(s["open"]) == 2:
        s["moves"] += 1
        a, b = s["open"]
        if s["tiles"][a]["pair"] == s["tiles"][b]["pair"]:
            s["matched"] += [a, b]
            s["open"] = []


def panel_games(src) -> None:
    nid = src[2]
    deck = D["cards"].get(nid, [])
    if len(deck) < 3:
        H('<div class="empty">Memory Match uses your flashcards. Create a deck first, then come back to play.</div>')
        st.button("Go to Flashcards", on_click=set_tool, args=("Flashcards",))
        return
    H('<p class="row-title">Memory Match</p><p class="row-sub">Flip two tiles to pair each term with its answer.</p>')
    s = st.session_state.get("mm")
    if not s or s["nid"] != nid:
        mm_start(nid)
        s = st.session_state.mm
    pairs = len(s["tiles"]) // 2
    c1, c2 = st.columns([1, 1])
    c1.markdown(f"**Moves:** {s['moves']} · **Matched:** {len(s['matched']) // 2} / {pairs}")
    c2.button("New game", on_click=mm_start, args=(nid,))
    with st.container(key="mm_grid"):
        for row in range(0, len(s["tiles"]), 4):
            cols = st.columns(4)
            for j, col in enumerate(cols):
                i = row + j
                if i >= len(s["tiles"]):
                    break
                shown = i in s["open"] or i in s["matched"]
                col.button(s["tiles"][i]["text"] if shown else "❔", key=f"mm_{i}_{s['moves']}_{len(s['open'])}",
                           disabled=i in s["matched"] or i in s["open"], on_click=mm_click, args=(i,))
    if len(s["matched"]) == len(s["tiles"]):
        st.success(f"You matched every pair in {s['moves']} moves! 🎉")
        if not s["rewarded"]:
            s["rewarded"] = True
            log_event("card", pairs)
            st.balloons()


PANELS = {"Summarize": panel_summary, "Explain a topic": panel_explain, "Ask AI": panel_chat, "Quiz": panel_quiz,
          "Flashcards": panel_flashcards, "Mind map": panel_mindmap, "Podcast": panel_podcast, "Games": panel_games}


def page_ai() -> None:
    page_header("AI Tools", "Pick a PDF once, then study it every way you like.")
    if not api_key():
        st.warning("Add your Gemini API key to turn on the AI tools.")
        key_box()
    with st.container(border=True):
        H('<p class="card-title">Study material</p>')
        src = source_picker("ai")

    tool = st.session_state.ai_tool if st.session_state.ai_tool in PANELS else "Summarize"
    for row in (TOOLS[:4], TOOLS[4:]):
        for col, (name, ico, bg, desc) in zip(st.columns(4), row):
            with col, st.container(border=True):
                H(f'<div style="display:flex;gap:12px;align-items:center"><div class="note-ico" style="background:{bg};'
                  f'font-size:1.2rem">{ico}</div><div><div class="tool-title">{name}</div></div></div>'
                  f'<div class="tool-desc" style="min-height:2.6em;margin:10px 0">{desc}</div>')
                st.button("Open", key=f"tool_{name}", on_click=set_tool, args=(name,), use_container_width=True,
                          type="primary" if name == tool else "secondary")

    st.write("")
    with st.container(border=True):
        H(f'<p class="card-title">{tool}</p>')
        if src is None:
            H('<div class="empty">Choose a note or upload a PDF above to begin.</div>')
        else:
            PANELS[tool](src)

    st.write("")
    H('<p class="card-title">Recent Activity</p>')
    with st.container(border=True):
        if not D["activity"]:
            H('<div class="empty">Your AI activity will show up here.</div>')
        for a in D["activity"][:4]:
            H(f'<div class="act"><span>📄</span><span>{esc(a["text"])}<small>{ago(a["at"])}</small></span></div>')


# ---- study quest ------------------------------------------------------
CHECKPOINTS = [("A", "Spark", 4), ("B", "Glow", 8), ("C", "Blaze", 14), ("D", "Orbit", 22)]


def quest_stats() -> dict:
    start = (TODAY - timedelta(days=TODAY.weekday())).isoformat()
    ev = [e for e in D["events"] if e["d"] >= start]
    focus = sum(e["v"] for e in ev if e["t"] == "focus")
    ai = sum(1 for e in ev if e["t"] == "ai")
    cards = int(sum(e["v"] for e in ev if e["t"] == "card"))
    quizzes = [e["v"] for e in ev if e["t"] == "quiz"]
    score = focus / 25 + ai * 0.5 + cards / 10 + sum(1 + 2 * v for v in quizzes)
    return dict(focus=focus, ai=ai, cards=cards, quizzes=len(quizzes), score=round(score, 1))


def page_quest() -> None:
    left, right = st.columns([4, 1])
    with left:
        H('<p class="ph-title">Study quest</p><p class="ph-sub">Your points this week (Monday to Sunday).</p>')
    with right.popover("How it works"):
        st.markdown("Earn points by studying. Your score resets every Monday.\n\n"
                    "- **Focus:** 1 point for every 25 minutes of finished focus sessions\n"
                    "- **AI sessions:** 0.5 points for each summary, explanation, chat answer, mind map or audio lesson\n"
                    "- **Cards:** 1 point for every 10 flashcards you review\n"
                    "- **Quizzes:** 1 point for finishing, plus up to 2 more for your score\n\n"
                    "Reach checkpoints A to D to complete the quest.")
    s = quest_stats()
    score = s["score"]
    nxt = next((c for c in CHECKPOINTS if score < c[2]), None)
    prev = max([c[2] for c in CHECKPOINTS if c[2] <= score], default=0)
    total = CHECKPOINTS[-1][2]
    circ = 2 * 3.14159 * 54
    if nxt is None:
        pill, head, sub, frac, lo, hi = "Quest complete", "You reached Orbit! 🎉", "Fantastic week. Keep the streak going.", 1, prev, total
    else:
        pill = f"Next: Checkpoint {nxt[0]}"
        head = "Your quest starts when you study" if score == 0 else f"{nxt[2] - score:.1f} pts to {nxt[1]}"
        sub = "Open notes, cards, or a quiz to begin." if score == 0 else "Every session counts. Keep going."
        frac, lo, hi = (score - prev) / (nxt[2] - prev), prev, nxt[2]
    with st.container(border=True):
        c1, c2 = st.columns([1, 3.4], vertical_alignment="center")
        with c1:
            H(f'''<div class="qring" style="width:140px;height:140px;margin:auto"><svg width="140" height="140" viewBox="0 0 140 140">
              <circle cx="70" cy="70" r="54" fill="none" stroke="#eceee8" stroke-width="12"/>
              <circle cx="70" cy="70" r="54" fill="none" stroke="#2f7d5b" stroke-width="12" stroke-linecap="round"
               stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ * (1 - min(score / total, 1)):.1f}"/></svg>
              <div class="in"><small>SCORE</small><b>{score:.1f}</b></div></div>''')
        with c2:
            H(f'<span class="nextpill">✦ {pill}</span><p class="q-h">{head}</p><p class="ph-sub" style="margin:0 0 10px">{sub}</p>'
              f'<div class="bar"><i style="width:{frac * 100:.0f}%"></i></div>'
              f'<div style="display:flex;justify-content:space-between;font-size:.74rem;color:var(--muted);margin-top:6px">'
              f'<span>{lo}</span><span>{hi:.1f} pts</span></div>')
            st.button("⏱  Go study", type="primary", on_click=go, args=("AI Tools",))
        H(f'<div class="tiles"><div class="tile"><div class="k">Focus time</div><div class="v">{s["focus"] / 60:.1f}h</div></div>'
          f'<div class="tile"><div class="k">AI sessions</div><div class="v">{s["ai"]}</div></div>'
          f'<div class="tile"><div class="k">Cards</div><div class="v">{s["cards"]}</div></div>'
          f'<div class="tile"><div class="k">Quizzes</div><div class="v">{s["quizzes"]}</div></div></div>')
        st.caption("Hit checkpoints A to D to complete this week's quest.")
    reached = sum(score >= c[2] for c in CHECKPOINTS)
    H(f'<div style="display:flex;justify-content:space-between;margin:22px 0 10px"><p class="card-title" style="margin:0">Checkpoint path</p>'
      f'<span class="row-sub">{reached}/4</span></div>')
    cps = ""
    for letter, name, pts in CHECKPOINTS:
        cls = "done" if score >= pts else "next" if nxt and nxt[0] == letter else ""
        cps += (f'<div class="cp {cls}"><div class="c">{"✓" if score >= pts else letter}</div>'
                f'<b>{name}</b><small>{pts} pts</small></div>')
    H(f'<div class="path">{cps}</div>')


def page_settings() -> None:
    page_header("Settings", "Make Study Buddy yours.")
    with st.container(border=True):
        st.caption(f"Signed in as {st.session_state.user['email'] or st.session_state.user['name']}")
        D["name"] = st.text_input("Your name", D["name"])
        key_box()
        if api_key():
            st.success("Gemini API key found.")
        c1, c2 = st.columns(2)
        if c1.button("Save settings", type="primary"):
            save()
            st.toast("Settings saved")
        if D.get("sample") and c2.button("Clear sample tasks and notes"):
            D["tasks"], D["notes"], D["sample"] = [], [], False
            save()
            st.rerun()


PAGES = {"Dashboard": page_dashboard, "Tasks": page_tasks, "Focus Mode": page_focus, "Notes": page_notes,
         "AI Tools": page_ai, "Study Quest": page_quest, "Settings": page_settings}
PAGES[st.session_state.page]()
