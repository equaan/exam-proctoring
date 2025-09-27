from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse, HTMLResponse
import asyncio
import json
import csv
import random
import shutil
from typing import Optional
import os
import time
import sqlite3
import logging
from io import StringIO
try:
    import redis.asyncio as redis  # redis>=5 provides asyncio API
except Exception:
    redis = None

app = FastAPI()

# Allow cross-origin requests for local file or other origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # Go up one level from app/
DATA_DIR = os.path.join(BASE_DIR, "data")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
LOG_PATH = os.path.join(DATA_DIR, "flags.jsonl")
SUBMISSIONS_PATH = os.path.join(DATA_DIR, "submissions.json")
DB_PATH = os.path.join(DATA_DIR, "proctoring.db")
STUDENTS_JSON = os.path.join(DATA_DIR, "students.json")

# HTML Route Handlers
def read_html_file(filename):
    """Helper function to read HTML files"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"<h1>Error: {filename} not found</h1>"

@app.get("/", response_class=HTMLResponse)
async def landing_hub():
    """Landing page with role selection"""
    return read_html_file(os.path.join(TEMPLATES_DIR, "landing_hub.html"))

@app.get("/teacher", response_class=HTMLResponse)
async def teacher_ui():
    """Teacher dashboard UI"""
    return read_html_file(os.path.join(TEMPLATES_DIR, "teacher_ui.html"))

@app.get("/student", response_class=HTMLResponse)
async def student_ui():
    """Student exam UI"""
    return read_html_file(os.path.join(TEMPLATES_DIR, "student_ui.html"))

@app.get("/processor", response_class=HTMLResponse)
async def processor_ui():
    """Processor control UI"""
    return read_html_file(os.path.join(TEMPLATES_DIR, "processor_ui.html"))

@app.post("/reset")
async def reset_system():
    """Reset system state - for quick actions"""
    try:
        # Reset exam state
        exam_state["started"] = False
        exam_state["start_time"] = None
        exam_state["end_time"] = None
        exam_state["duration"] = None
        
        # Reset student states
        async with students_lock:
            for sid, info in students.items():
                info["flags"] = 0
                info["last_seen"] = None
                info["in_exam"] = False
        
        # Clear submissions
        async with submissions_lock:
            submissions.clear()
            await save_submissions()
        
        # Broadcast reset to all connected clients
        await broadcast_to_teachers({"type": "system_reset", "timestamp": time.time()})
        await broadcast_to_processors({"type": "system_reset", "timestamp": time.time()})
        
        return JSONResponse(content={"status": "success", "message": "System reset successfully"})
    except Exception as e:
        logger.error(f"System reset error: {e}")
        return JSONResponse(status_code=500, content={"error": "Reset failed"})

# Legacy routes for backward compatibility
@app.get("/teacher_ui", response_class=HTMLResponse)
async def teacher_ui_legacy():
    return await teacher_ui()

@app.get("/student_ui", response_class=HTMLResponse)
async def student_ui_legacy():
    return await student_ui()

@app.get("/processor_ui", response_class=HTMLResponse)
async def processor_ui_legacy():
    return await processor_ui()

# In-memory state
students = {}  # student_id -> {"ws": WebSocket, "name": str, "last_seen": float, "flags": int}
teachers = set()  # teacher dashboards
processors = set()  # processor dashboards
students_lock = asyncio.Lock()
teachers_lock = asyncio.Lock()
processors_lock = asyncio.Lock()
# Exam state
exam_state = {
    "started": False,
    "start_time": None,
    "end_time": None,
    "duration": None,
}
# submissions: student_id -> {submitted: bool, time: ts, marks: int}
submissions = {}
submissions_lock = asyncio.Lock()

# Autosave state: student_id -> { answers: dict, version: int, updated_at: ts }
autosave_state = {}
autosave_lock = asyncio.Lock()

# Simple auth token
TEACHER_TOKEN = os.environ.get("TEACHER_TOKEN", "teacher_token")

# Feature flags / configuration
REDIS_URL = os.environ.get("REDIS_URL")
USE_REDIS_LOCKS = bool(REDIS_URL)

# Coordinator lock implementation (Redis or in-memory fallback)
class CoordinatorLock:
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._mem_locks: dict[str, asyncio.Lock] = {}
        self._mem_locks_lock = asyncio.Lock()

    async def initialize(self):
        if USE_REDIS_LOCKS and redis is not None:
            try:
                self._redis = redis.from_url(REDIS_URL, decode_responses=True)
                await self._redis.ping()
            except Exception:
                self._redis = None

    async def acquire(self, key: str, ttl_ms: int = 5000) -> bool:
        if self._redis is not None:
            try:
                ok = await self._redis.set(name=f"lock:{key}", value="1", nx=True, px=ttl_ms)
                return bool(ok)
            except Exception:
                pass
        # Fallback in-memory lock
        async with self._mem_locks_lock:
            if key not in self._mem_locks:
                self._mem_locks[key] = asyncio.Lock()
            lock = self._mem_locks[key]
        locked = lock.locked()
        if locked:
            return False
        await lock.acquire()
        return True

    async def release(self, key: str):
        if self._redis is not None:
            try:
                await self._redis.delete(f"lock:{key}")
                return
            except Exception:
                pass
        async with self._mem_locks_lock:
            lock = self._mem_locks.get(key)
        if lock and lock.locked():
            lock.release()

lock_manager = CoordinatorLock()

# Load submissions from file
def load_submissions():
    global submissions
    try:
        if os.path.exists(SUBMISSIONS_PATH):
            with open(SUBMISSIONS_PATH, "r", encoding="utf-8") as f:
                submissions.update(json.load(f))
    except Exception as e:
        logger.error(f"Failed to load submissions: {e}")

# Save submissions to file
async def save_submissions():
    try:
        with open(SUBMISSIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(submissions, f)
    except Exception as e:
        logger.error(f"Failed to save submissions: {e}")

# --- Database helpers (SQLite) ---
def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = db_connect()
        with conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS students (student_id TEXT PRIMARY KEY, name TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS autosave (student_id TEXT PRIMARY KEY, version INTEGER NOT NULL, updated_at REAL NOT NULL, answers TEXT NOT NULL)"
            )
    finally:
        try:
            conn.close()
        except Exception:
            pass

def load_students_from_json():
    try:
        if os.path.exists(STUDENTS_JSON):
            with open(STUDENTS_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                conn = db_connect()
                with conn:
                    for s in data:
                        sid = s.get("student_id") or s.get("id")
                        name = s.get("name") or sid
                        if sid:
                            conn.execute(
                                "INSERT OR REPLACE INTO students(student_id, name) VALUES(?, ?)", (sid, name)
                            )
                conn.close()
    except Exception as e:
        logger.error(f"Failed to load students.json: {e}")

async def persist_flag(event: dict):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        logger.error(f"Failed to persist flag: {e}")

# MCQ Exam Configuration
CORRECT_ANSWERS = {
    "q1": "b",  # Which property is ensured by consensus? -> Agreement
    "q2": "a",  # What is the CAP theorem? -> Consistency, Availability, Partition tolerance
    "q3": "d",  # Which algorithm is used for leader election? -> Raft
    "q4": "c",  # What is eventual consistency? -> Data will become consistent over time
    "q5": "b",  # What is a distributed hash table? -> A data structure distributed across nodes
}

MARKS_PER_QUESTION = 20  # 5 questions × 20 marks = 100 total

def compute_marks(flags: int, answers: dict | None = None) -> dict:
    """
    Compute marks based on MCQ answers and apply cheating penalties
    Returns dict with detailed scoring information
    """
    result = {
        "total_questions": len(CORRECT_ANSWERS),
        "correct_answers": 0,
        "base_score": 0,
        "final_score": 0,
        "penalty_applied": 0,
        "answer_details": {}
    }
    
    if answers:
        # Check each answer
        for question, correct_answer in CORRECT_ANSWERS.items():
            student_answer = (answers.get(question) or "").lower().strip()
            is_correct = student_answer == correct_answer.lower()
            
            result["answer_details"][question] = {
                "student_answer": student_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "marks": MARKS_PER_QUESTION if is_correct else 0
            }
            
            if is_correct:
                result["correct_answers"] += 1
        
        result["base_score"] = result["correct_answers"] * MARKS_PER_QUESTION
    else:
        # No answers provided - assume full marks for legacy compatibility
        result["base_score"] = 100
        result["correct_answers"] = 5
    
    # Apply cheating penalties
    if flags <= 0:
        result["final_score"] = result["base_score"]
        result["penalty_applied"] = 0
    elif flags == 1:
        result["final_score"] = int(result["base_score"] * 0.5)  # 50% penalty
        result["penalty_applied"] = 50
    else:
        result["final_score"] = 0  # 0% for multiple cheating incidents
        result["penalty_applied"] = 100
    
    return result

async def broadcast_to_teachers(msg: dict):
    async with teachers_lock:
        to_remove = []
        for ws in list(teachers):
            try:
                await ws.send_json(msg)
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            teachers.discard(ws)
    # Also publish to Redis for cross-instance fanout if available
    if 'redis' in globals() and redis is not None and getattr(lock_manager, '_redis', None) is not None:
        try:
            await lock_manager._redis.publish("teacher_events", json.dumps(msg))
        except Exception:
            pass

async def broadcast_to_processors(msg: dict):
    async with processors_lock:
        to_remove = []
        for ws in list(processors):
            try:
                await ws.send_json(msg)
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            processors.discard(ws)
    if 'redis' in globals() and redis is not None and getattr(lock_manager, '_redis', None) is not None:
        try:
            await lock_manager._redis.publish("processor_events", json.dumps(msg))
        except Exception:
            pass

async def notify_student(student_id: str, msg: dict):
    async with students_lock:
        if student_id in students:
            try:
                await students[student_id]["ws"].send_json(msg)
            except Exception:
                pass

async def send_student_list():
    async with students_lock:
        lst = [
            {
                "student_id": sid, 
                "name": info["name"], 
                "last_seen": info["last_seen"], 
                "flags": info["flags"],
                "in_exam": info.get("in_exam", False)
            }
            for sid, info in students.items()
        ]
    # Teachers and processors both get student list
    await broadcast_to_teachers({"type": "student_list", "students": lst})
    await broadcast_to_processors({"type": "student_list", "students": lst})
    # Mirror to Redis hash for visibility across instances
    if 'redis' in globals() and redis is not None and getattr(lock_manager, '_redis', None) is not None:
        try:
            pipe = lock_manager._redis.pipeline()
            for sid, info in students.items():
                key = f"student:{sid}"
                pipe.hset(key, mapping={
                    "name": info["name"],
                    "last_seen": info["last_seen"] or 0,
                    "flags": info["flags"],
                })
                pipe.expire(key, 3600)
            await pipe.execute()
        except Exception:
            pass

async def flag_random_student():
    while True:
        await asyncio.sleep(6 + random.random() * 4)  # Random interval 6-10s
        if not exam_state.get("started"):
            continue
        async with students_lock:
            if not students:
                continue
            # Filter students with fewer than 2 flags
            eligible_students = [sid for sid, info in students.items() if info["flags"] < 2]
            if not eligible_students:
                continue  # No eligible students, skip this cycle
            sid = random.choice(eligible_students)
            students[sid]["flags"] += 1
            now = time.time()
            students[sid]["last_seen"] = now
            ev = {
                "type": "flag",
                "student_id": sid,
                "name": students[sid]["name"],
                "flags": students[sid]["flags"],
                "timestamp": now,
                "reason": "simulated_random_detection"
            }
        await persist_flag(ev)
        # Send to teachers for penalty application
        await broadcast_to_teachers(ev)
        await notify_student(sid, {"type": "flag_warning", "message": "You were flagged for suspicious activity"})
        await send_student_list()
    # Mirror flag count to Redis for visibility
    if 'redis' in globals() and redis is not None and getattr(lock_manager, '_redis', None) is not None:
        try:
            await lock_manager._redis.hset(f"student:{sid}", mapping={"flags": students[sid]["flags"], "last_seen": now})
        except Exception:
            pass

async def exam_watcher():
    while True:
        await asyncio.sleep(1)
        if exam_state["started"] and exam_state["end_time"] is not None:
            now = time.time()
            if now >= exam_state["end_time"]:
                async with students_lock:
                    sids = list(students.keys())
                async with submissions_lock:
                    for sid in sids:
                        if submissions.get(sid, {}).get("submitted"):
                            continue
                        flags = students.get(sid, {}).get("flags", 0)
                        marks = compute_marks(flags)
                        submissions[sid] = {"submitted": True, "time": now, "marks": marks, "flags": flags}
                        ev = {"type": "submit", "student_id": sid, "timestamp": now}
                        await persist_flag(ev)
                await broadcast_to_processors({"type": "auto_submitted", "student_id": sid, "marks": marks})
                await save_submissions()
                exam_state["started"] = False
                exam_state["start_time"] = None
                exam_state["end_time"] = None
                exam_state["duration"] = None
                await broadcast_to_teachers({"type": "exam_finished", "timestamp": now})
                await broadcast_to_processors({"type": "exam_finished", "timestamp": now})
                async with students_lock:
                    for stid, info in students.items():
                        try:
                            await info["ws"].send_json({"type": "exam_finished", "timestamp": now})
                        except Exception:
                            pass

@app.on_event("startup")
async def startup_event():
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(TEMPLATES_DIR, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create base directory: {e}")
    # Migrate legacy files if present
    try:
        legacy_flags = os.path.join(BASE_DIR, "flags.jsonl")
        legacy_subs = os.path.join(BASE_DIR, "submissions.json")
        legacy_db = os.path.join(BASE_DIR, "proctoring.db")
        legacy_students = os.path.join(BASE_DIR, "students.json")
        for src, dst in [
            (legacy_flags, LOG_PATH),
            (legacy_subs, SUBMISSIONS_PATH),
            (legacy_db, DB_PATH),
            (legacy_students, STUDENTS_JSON),
        ]:
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    import shutil
                    shutil.move(src, dst)
                except Exception:
                    pass
    except Exception:
        pass
    # Reset submissions on each server start to avoid conflicts with previous runs
    async with submissions_lock:
        submissions.clear()
        await save_submissions()
    init_db()
    load_students_from_json()
    await lock_manager.initialize()
    asyncio.create_task(flag_random_student())
    asyncio.create_task(exam_watcher())
    asyncio.create_task(autosave_flush_loop())

@app.get("/flags")
async def get_flags():
    out = []
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"Failed to read flags: {e}")
            return JSONResponse(status_code=500, content={"error": "failed to read log"})
    return JSONResponse(content=out)

@app.get("/healthz")
async def healthz():
    # Basic liveness
    return JSONResponse(content={"status": "ok"})

@app.get("/readyz")
async def readyz():
    # Check DB and Redis if configured
    try:
        conn = db_connect()
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception as e:
        return JSONResponse(status_code=503, content={"db": "down", "error": str(e)})
    if REDIS_URL:
        try:
            if getattr(lock_manager, '_redis', None) is None:
                return JSONResponse(status_code=503, content={"redis": "down"})
            pong = await lock_manager._redis.ping()
            if not pong:
                return JSONResponse(status_code=503, content={"redis": "down"})
        except Exception as e:
            return JSONResponse(status_code=503, content={"redis": "down", "error": str(e)})
    return JSONResponse(content={"status": "ready"})

async def autosave_flush_loop():
    while True:
        await asyncio.sleep(5)
        try:
            async with autosave_lock:
                items = list(autosave_state.items())
            if not items:
                continue
            conn = db_connect()
            with conn:
                for sid, st in items:
                    conn.execute(
                        "INSERT OR REPLACE INTO autosave(student_id, version, updated_at, answers) VALUES(?, ?, ?, ?)",
                        (sid, st.get("version", 0), st.get("updated_at", 0), json.dumps(st.get("answers", {})))
                    )
            try:
                conn.close()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"autosave flush error: {e}")

@app.get("/students")
async def get_students_api():
    try:
        conn = db_connect()
        rows = conn.execute("SELECT student_id, name FROM students ORDER BY student_id").fetchall()
        data = [{"student_id": r["student_id"], "name": r["name"]} for r in rows]
        return JSONResponse(content=data)
    except Exception as e:
        logger.error(f"students list error: {e}")
        return JSONResponse(status_code=500, content={"error": "server error"})
    finally:
        try:
            conn.close()
        except Exception:
            pass

@app.post("/students")
async def post_students_api(req: Request):
    try:
        body = await req.json()
        # Accept either single {student_id,name} or list of them
        payload = body if isinstance(body, list) else [body]
        conn = db_connect()
        with conn:
            for s in payload:
                sid = s.get("student_id") or s.get("id")
                name = s.get("name") or sid
                if not sid:
                    continue
                conn.execute("INSERT OR REPLACE INTO students(student_id, name) VALUES(?, ?)", (sid, name))
        return JSONResponse(content={"status": "ok", "count": len(payload)})
    except Exception as e:
        logger.error(f"students upsert error: {e}")
        return JSONResponse(status_code=500, content={"error": "server error"})

@app.get("/debug/memory")
async def debug_memory():
    """Debug endpoint to see students in memory"""
    async with students_lock:
        return {
            "students_count": len(students),
            "students": list(students.keys())
        }

@app.get("/debug/students")
async def debug_students():
    """Debug endpoint to see what's in the students dictionary"""
    try:
        async with students_lock:
            debug_info = {
                "total_students": len(students),
                "students": []
            }
            for sid, info in students.items():
                debug_info["students"].append({
                    "student_id": sid,
                    "name": info.get("name", "N/A"),
                    "has_ws": info.get("ws") is not None,
                    "last_seen": info.get("last_seen"),
                    "flags": info.get("flags", 0),
                    "in_exam": info.get("in_exam", False)
                })
        return JSONResponse(content=debug_info)
    except Exception as e:
        return JSONResponse(content={"error": str(e)})

@app.get("/marks/detailed")
async def get_detailed_marks():
    """Get detailed marks with answer breakdown"""
    try:
        async with submissions_lock:
            out = []
            # Include all students in submissions, even if disconnected
            for sid, sub in submissions.items():
                flags = students.get(sid, {}).get('flags', sub.get('flags', 0))
                # attach name from DB if present
                try:
                    conn = db_connect()
                    row = conn.execute("SELECT name FROM students WHERE student_id=?", (sid,)).fetchone()
                    name = row["name"] if row else sid
                except Exception:
                    name = sid
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
                
                marks_details = sub.get('marks_details', {})
                out.append({
                    "student_id": sid,
                    "name": name,
                    "submitted": sub.get('submitted', False),
                    "marks": sub.get('marks'),
                    "time": sub.get('time'),
                    "flags": flags,
                    "marks_details": marks_details
                })
            
            # Add active students not yet in submissions (including virtual students)
            async with students_lock:
                for sid, student_info in students.items():
                    if sid not in submissions:
                        try:
                            conn = db_connect()
                            row = conn.execute("SELECT name FROM students WHERE student_id=?", (sid,)).fetchone()
                            name = row["name"] if row else student_info.get("name", sid)
                        except Exception:
                            name = student_info.get("name", sid)
                        finally:
                            try:
                                conn.close()
                            except Exception:
                                pass
                        out.append({
                            "student_id": sid,
                            "name": name,
                            "submitted": False,
                            "marks": None,
                            "time": None,
                            "flags": student_info.get('flags', 0),
                            "marks_details": {}
                        })
        return JSONResponse(content=out)
    except Exception as e:
        logger.error(f"Detailed marks endpoint error: {e}")
        return JSONResponse(status_code=500, content={"error": "server error"})

@app.get("/marks")
async def get_marks():
    try:
        async with submissions_lock:
            out = []
            # Include all students in submissions, even if disconnected
            for sid, sub in submissions.items():
                flags = students.get(sid, {}).get('flags', sub.get('flags', 0))
                # attach name from DB if present
                try:
                    conn = db_connect()
                    row = conn.execute("SELECT name FROM students WHERE student_id=?", (sid,)).fetchone()
                    name = row["name"] if row else sid
                except Exception:
                    name = sid
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass
                out.append({
                    "student_id": sid,
                    "name": name,
                    "submitted": sub.get('submitted', False),
                    "marks": sub.get('marks'),
                    "time": sub.get('time'),
                    "flags": flags
                })
            # Add active students not yet in submissions (including virtual students)
            async with students_lock:
                for sid, student_info in students.items():
                    if sid not in submissions:
                        try:
                            conn = db_connect()
                            row = conn.execute("SELECT name FROM students WHERE student_id=?", (sid,)).fetchone()
                            name = row["name"] if row else student_info.get("name", sid)
                        except Exception:
                            name = student_info.get("name", sid)
                        finally:
                            try:
                                conn.close()
                            except Exception:
                                pass
                        out.append({
                            "student_id": sid,
                            "name": name,
                            "submitted": False,
                            "marks": None,
                            "time": None,
                            "flags": student_info.get('flags', 0)
                        })
        return JSONResponse(content=out)
    except Exception as e:
        logger.error(f"Marks endpoint error: {e}")
        return JSONResponse(status_code=500, content={"error": "server error"})

@app.post("/marks/override")
async def override_marks(req: Request):
    try:
        body = await req.json()
        sid = body.get("student_id")
        marks = body.get("marks")
        if not sid or not isinstance(marks, (int, float)):
            return JSONResponse(status_code=400, content={"error": "invalid payload"})
        now = time.time()
        async with submissions_lock:
            rec = submissions.get(sid) or {"submitted": True, "time": now, "flags": students.get(sid, {}).get('flags', 0)}
            rec["marks"] = int(marks)
            rec["time"] = rec.get("time", now)
            rec["submitted"] = True
            submissions[sid] = rec
            await save_submissions()
        await persist_flag({"type": "override", "student_id": sid, "timestamp": now, "marks": int(marks)})
        await broadcast_to_teachers({"type": "submitted", "student_id": sid, "marks": int(marks)})
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        logger.error(f"override error: {e}")
        return JSONResponse(status_code=500, content={"error": "server error"})

@app.get("/marks.csv")
async def get_marks_csv():
    try:
        # Reuse JSON data
        resp = await get_marks()
        if isinstance(resp, JSONResponse):
            data = resp.body
            # body is bytes; decode
            import json as _json
            rows = _json.loads(data)
        else:
            rows = []
        # Write CSV
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(["student_id", "name", "submitted", "marks", "flags", "time"])
        for r in rows:
            writer.writerow([
                r.get("student_id"), r.get("name"), r.get("submitted"), r.get("marks"), r.get("flags"), r.get("time")
            ])
        output = buf.getvalue()
        headers = {"Content-Disposition": "attachment; filename=marks.csv"}
        return JSONResponse(content=output, headers=headers, media_type="text/csv")
    except Exception as e:
        logger.error(f"Marks CSV error: {e}")
        return JSONResponse(status_code=500, content={"error": "server error"})

# --- Autosave APIs (eventual consistency with versioning) ---
@app.post("/autosave")
async def post_autosave(req: Request):
    try:
        body = await req.json()
        sid = body.get("student_id")
        version = int(body.get("version") or 0)
        answers = body.get("answers") or {}
        if not sid:
            return JSONResponse(status_code=400, content={"error": "missing student_id"})
        now = time.time()
        async with autosave_lock:
            cur = autosave_state.get(sid, {"version": -1})
            if version >= cur.get("version", -1):
                autosave_state[sid] = {"answers": answers, "version": version, "updated_at": now}
        # Mirror to Redis (best-effort)
        if 'redis' in globals() and redis is not None and getattr(lock_manager, '_redis', None) is not None:
            try:
                await lock_manager._redis.hset(f"autosave:{sid}", mapping={
                    "version": version,
                    "updated_at": now,
                    "answers": json.dumps(answers)
                })
                await lock_manager._redis.expire(f"autosave:{sid}", 3600)
            except Exception:
                pass
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        logger.error(f"autosave error: {e}")
        return JSONResponse(status_code=500, content={"error": "server error"})

@app.get("/autosave/{student_id}")
async def get_autosave(student_id: str):
    try:
        async with autosave_lock:
            state = autosave_state.get(student_id)
        if state is None and 'redis' in globals() and redis is not None and getattr(lock_manager, '_redis', None) is not None:
            try:
                data = await lock_manager._redis.hgetall(f"autosave:{student_id}")
                if data:
                    state = {
                        "version": int(data.get("version", 0)),
                        "updated_at": float(data.get("updated_at", 0)),
                        "answers": json.loads(data.get("answers", "{}"))
                    }
            except Exception:
                state = None
        return JSONResponse(content=state or {})
    except Exception as e:
        logger.error(f"autosave get error: {e}")
        return JSONResponse(status_code=500, content={"error": "server error"})

@app.post("/start")
async def start_via_http(req: Request):
    try:
        body = await req.json()
        duration = body.get('duration')
        now = time.time()
        if not isinstance(duration, (int, float)) or duration <= 0:
            return JSONResponse(status_code=400, content={"error": "invalid duration"})
        exam_state["started"] = True
        exam_state["start_time"] = now
        exam_state["duration"] = duration
        exam_state["end_time"] = now + duration
        async with submissions_lock:
            submissions.clear()
            await save_submissions()
            
        # Create virtual students for all database students (same as WebSocket processor)
        async with students_lock:
            # Get all students from database
            conn = db_connect()
            try:
                rows = conn.execute("SELECT student_id, name FROM students ORDER BY student_id").fetchall()
                all_db_students = [{"student_id": r["student_id"], "name": r["name"]} for r in rows]
                logger.info(f"Found {len(all_db_students)} students in database")
            finally:
                conn.close()
            
            # Make all database students appear online and in exam
            for db_student in all_db_students:
                sid = db_student["student_id"]
                if sid not in students:
                    # Create virtual student entry (no WebSocket but appears in exam)
                    students[sid] = {
                        "ws": None,  # Virtual student
                        "name": db_student["name"],
                        "last_seen": now,
                        "flags": 0,
                        "in_exam": True  # Mark as in exam
                    }
                    logger.info(f"Created virtual student: {sid}")
                else:
                    # Update existing student
                    students[sid]["last_seen"] = now
                    students[sid]["in_exam"] = True
                    logger.info(f"Updated existing student: {sid}")
            
            logger.info(f"Total students in memory: {len(students)}")
                    
        await broadcast_to_teachers({"type": "exam_started", "timestamp": now, "end_time": exam_state["end_time"]})
        
        # Send updated student list to all connected clients
        await send_student_list()
        
        async with students_lock:
            for stid, info in students.items():
                try:
                    if info["ws"]:  # Only send to real WebSocket connections
                        await info["ws"].send_json({"type": "exam_started", "timestamp": now, "end_time": exam_state["end_time"]})
                except Exception:
                    pass
        return JSONResponse(content={"status": "started", "end_time": exam_state["end_time"]})
    except Exception as e:
        logger.error(f"Start exam error: {e}")
        return JSONResponse(status_code=500, content={"error": "server error"})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    role = None
    sid = None
    try:
        init = await websocket.receive_json()
        role = init.get("role")
        if role == "student":
            sid = init.get("student_id")
            name = init.get("name") or sid
            if not sid:
                await websocket.send_json({"error": "missing student_id"})
                return
            async with students_lock:
                # Check if student_id is already in use by a REAL student (has WebSocket)
                if sid in students and students[sid].get("ws") is not None:
                    await websocket.send_json({"error": "student_id already in use"})
                    return
                # Allow real students to override virtual students (ws is None)
                # Preserve in_exam status if it was set for virtual student
                in_exam_status = students.get(sid, {}).get("in_exam", False)
                students[sid] = {
                    "ws": websocket, 
                    "name": name, 
                    "last_seen": time.time(), 
                    "flags": students.get(sid, {}).get("flags", 0),
                    "in_exam": in_exam_status
                }
            await send_student_list()
            await websocket.send_json({"type": "joined", "role": "student", "student_id": sid})
            
            # If exam is currently running, send exam_started event to the new student
            if exam_state.get("started") and exam_state.get("end_time"):
                await websocket.send_json({
                    "type": "exam_started", 
                    "timestamp": exam_state.get("start_time"), 
                    "end_time": exam_state.get("end_time")
                })
        elif role == "teacher":
            if init.get("token") != TEACHER_TOKEN:
                await websocket.send_json({"error": "invalid teacher token"})
                return
            async with teachers_lock:
                teachers.add(websocket)
            await send_student_list()
            await websocket.send_json({"type": "joined", "role": "teacher"})
        elif role == "processor":
            if init.get("token") != TEACHER_TOKEN:
                await websocket.send_json({"error": "invalid processor token"})
                return
            async with processors_lock:
                processors.add(websocket)
            await send_student_list()
            await websocket.send_json({"type": "joined", "role": "processor"})
        else:
            await websocket.send_json({"error": "unknown role"})
            return

        while True:
            try:
                msg = await websocket.receive_json()
                mtype = msg.get("type")
                if role == "student":
                    if mtype == "heartbeat":
                        async with students_lock:
                            if sid in students:
                                students[sid]["last_seen"] = time.time()
                        await websocket.send_json({"type": "heartbeat_ack", "ts": time.time()})
                    elif mtype == "submit":
                        now = time.time()
                        # Coordinator lock to prevent race with autosave or duplicate submits
                        lock_key = f"submit:{sid}"
                        acquired = await lock_manager.acquire(lock_key, ttl_ms=5000)
                        if not acquired:
                            await websocket.send_json({"type": "submit_ack", "status": "busy"})
                        else:
                            try:
                                async with submissions_lock:
                                    if submissions.get(sid, {}).get("submitted"):
                                        await websocket.send_json({"type": "submit_ack", "status": "already"})
                                    else:
                                        flags = students.get(sid, {}).get("flags", 0)
                                        # Merge MCQ answers from autosave if present
                                        async with autosave_lock:
                                            mcq = (autosave_state.get(sid, {}) or {}).get("answers") or {}
                                        marks_result = compute_marks(flags, mcq)
                                        final_marks = marks_result["final_score"]
                                        submissions[sid] = {
                                            "submitted": True, 
                                            "time": now, 
                                            "marks": final_marks, 
                                            "flags": flags,
                                            "marks_details": marks_result
                                        }
                                        ev = {"type": "submit", "student_id": sid, "timestamp": now}
                                        await persist_flag(ev)
                                        await broadcast_to_teachers({"type": "submitted", "student_id": sid, "marks": final_marks})
                                        await websocket.send_json({"type": "submit_ack", "status": "ok", "marks": final_marks})
                                        await save_submissions()
                            finally:
                                await lock_manager.release(lock_key)
                    else:
                        await websocket.send_json({"type": "error", "message": "unknown message type"})
                elif role == "processor":
                    if mtype == "start_exam":
                        duration = msg.get("duration", 60)
                        now = time.time()
                        if not isinstance(duration, (int, float)) or duration <= 0:
                            await websocket.send_json({"type": "error", "message": "invalid duration"})
                            continue
                        exam_state["started"] = True
                        exam_state["start_time"] = now
                        exam_state["duration"] = duration
                        exam_state["end_time"] = now + duration
                        async with submissions_lock:
                            submissions.clear()
                            await save_submissions()
                        # Make all students online and in exam by default - create virtual students if needed
                        async with students_lock:
                            # Get all students from database
                            conn = db_connect()
                            try:
                                rows = conn.execute("SELECT student_id, name FROM students ORDER BY student_id").fetchall()
                                all_db_students = [{"student_id": r["student_id"], "name": r["name"]} for r in rows]
                                print(f"DEBUG: Found {len(all_db_students)} students in database")
                            finally:
                                conn.close()
                            
                            # Make all database students appear online and in exam
                            for db_student in all_db_students:
                                sid = db_student["student_id"]
                                if sid not in students:
                                    # Create virtual student entry (no WebSocket but appears in exam)
                                    students[sid] = {
                                        "ws": None,  # Virtual student
                                        "name": db_student["name"],
                                        "last_seen": now,
                                        "flags": 0,
                                        "in_exam": True  # Mark as in exam
                                    }
                                    print(f"DEBUG: Created virtual student {sid}")
                                else:
                                    # Update existing student
                                    students[sid]["last_seen"] = now
                                    students[sid]["in_exam"] = True
                                    print(f"DEBUG: Updated existing student {sid}")
                            
                            print(f"DEBUG: Total students in memory after creation: {len(students)}")
                        async with students_lock:
                            targets = list(students.items())
                        for stid, info in targets:
                            try:
                                if info["ws"]:  # Only send to real WebSocket connections
                                    await info["ws"].send_json({"type": "exam_started", "timestamp": now, "end_time": exam_state["end_time"]})
                            except Exception:
                                pass
                        # Notify dashboards
                        await broadcast_to_teachers({"type": "exam_started", "timestamp": now, "end_time": exam_state["end_time"]})
                        await broadcast_to_processors({"type": "exam_started", "timestamp": now, "end_time": exam_state["end_time"]})
                        await websocket.send_json({"type": "started_ack", "end_time": exam_state["end_time"]})
                    elif mtype == "stop_exam":
                        if exam_state["started"]:
                            now = time.time()
                            async with students_lock:
                                sids = list(students.keys())
                            # Use per-student submit lock to avoid races
                            for sid in sids:
                                lock_key = f"submit:{sid}"
                                acquired = await lock_manager.acquire(lock_key, ttl_ms=5000)
                                if not acquired:
                                    continue
                                try:
                                    async with submissions_lock:
                                        if submissions.get(sid, {}).get("submitted"):
                                            continue
                                        flags = students.get(sid, {}).get("flags", 0)
                                        marks_result = compute_marks(flags)
                                        final_marks = marks_result["final_score"]
                                        submissions[sid] = {
                                            "submitted": True, 
                                            "time": now, 
                                            "marks": final_marks, 
                                            "flags": flags,
                                            "marks_details": marks_result
                                        }
                                        ev = {"type": "submit", "student_id": sid, "timestamp": now}
                                        await persist_flag(ev)
                                        await broadcast_to_teachers({"type": "auto_submitted", "student_id": sid, "marks": final_marks})
                                finally:
                                    await lock_manager.release(lock_key)
                            async with submissions_lock:
                                await save_submissions()
                            exam_state["started"] = False
                            exam_state["start_time"] = None
                            exam_state["end_time"] = None
                            exam_state["duration"] = None
                            
                            # Reset all students' in_exam status
                            async with students_lock:
                                for sid, info in students.items():
                                    info["in_exam"] = False
                            
                            await broadcast_to_teachers({"type": "exam_finished", "timestamp": now})
                            await broadcast_to_processors({"type": "exam_finished", "timestamp": now})
                            
                            # Send updated student list to reflect status change
                            await send_student_list()
                            
                            async with students_lock:
                                for stid, info in students.items():
                                    try:
                                        if info["ws"]:  # Only send to real WebSocket connections
                                            await info["ws"].send_json({"type": "exam_finished", "timestamp": now})
                                    except Exception:
                                        pass
                    elif mtype == "reset_state":
                        async with students_lock:
                            for sid, info in students.items():
                                info["flags"] = 0
                                info["last_seen"] = None
                                info["in_exam"] = False  # Reset exam status
                        async with submissions_lock:
                            submissions.clear()
                            await save_submissions()
                        exam_state["started"] = False
                        exam_state["start_time"] = None
                        exam_state["end_time"] = None
                        exam_state["duration"] = None
                        await send_student_list()
                        await broadcast_to_teachers({"type": "state_reset", "timestamp": time.time()})
                        await broadcast_to_processors({"type": "state_reset", "timestamp": time.time()})
                        await websocket.send_json({"type": "reset_ack"})
                    elif mtype == "get_students":
                        await send_student_list()
                    else:
                        await websocket.send_json({"type": "error", "message": "unknown message type"})
                elif role == "teacher":
                    # Teachers can't control exam anymore
                    if mtype == "get_students":
                        await send_student_list()
                    else:
                        await websocket.send_json({"type": "error", "message": "not permitted"})
            except ValueError as e:
                logger.error(f"Invalid JSON: {e}")
                await websocket.send_json({"type": "error", "message": "invalid JSON"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if role == "student" and sid:
            async with students_lock:
                students.pop(sid, None)
            await send_student_list()
        if role == "teacher":
            async with teachers_lock:
                teachers.discard(websocket)
        if role == "processor":
            async with processors_lock:
                processors.discard(websocket)