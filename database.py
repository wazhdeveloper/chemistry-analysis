"""数据库操作"""
import sqlite3
import os
from config import DB_PATH

def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """初始化数据库表结构"""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS exams (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            source      TEXT NOT NULL DEFAULT '新教育',
            exam_date   TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS scores (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id         INTEGER NOT NULL,
            student_name    TEXT NOT NULL,
            class_name      TEXT NOT NULL,
            total_score     REAL,
            objective_score REAL,
            subjective_score REAL,
            class_rank      INTEGER,
            grade_rank      INTEGER,
            is_absent       INTEGER DEFAULT 0,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_scores_name ON scores(student_name);
        CREATE INDEX IF NOT EXISTS idx_scores_exam ON scores(exam_id);
    """)
    conn.commit()
    conn.close()

# ── 考试操作 ──

def add_exam(name, source, exam_date):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO exams (name, source, exam_date) VALUES (?, ?, ?)",
              (name, source, exam_date))
    exam_id = c.lastrowid
    conn.commit()
    conn.close()
    return exam_id

def delete_exam(exam_id):
    conn = get_conn()
    conn.execute("DELETE FROM scores WHERE exam_id = ?", (exam_id,))
    conn.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
    conn.commit()
    conn.close()

def get_exams():
    conn = get_conn()
    rows = conn.execute("""
        SELECT e.*, COUNT(s.id) as student_count
        FROM exams e
        LEFT JOIN scores s ON s.exam_id = e.id AND s.is_absent = 0
        GROUP BY e.id
        ORDER BY e.exam_date DESC
    """).fetchall()
    conn.close()
    return rows

def get_exam_by_id(exam_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
    conn.close()
    return row

# ── 成绩操作 ──

def add_scores(exam_id, scores_list):
    """批量插入成绩
    scores_list: list of dict
        {student_name, class_name, total_score, objective_score,
         subjective_score, class_rank, grade_rank, is_absent}
    """
    conn = get_conn()
    conn.executemany("""
        INSERT INTO scores
            (exam_id, student_name, class_name, total_score,
             objective_score, subjective_score, class_rank, grade_rank, is_absent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [(
        exam_id,
        s['student_name'],
        s['class_name'],
        s.get('total_score'),
        s.get('objective_score'),
        s.get('subjective_score'),
        s.get('class_rank'),
        s.get('grade_rank'),
        s.get('is_absent', 0)
    ) for s in scores_list])
    conn.commit()
    conn.close()

def get_exam_scores(exam_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM scores
        WHERE exam_id = ?
        ORDER BY total_score DESC
    """, (exam_id,)).fetchall()
    conn.close()
    return rows

def get_student_scores(student_name):
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.*, e.name as exam_name, e.exam_date, e.source
        FROM scores s
        JOIN exams e ON e.id = s.exam_id
        WHERE s.student_name = ?
        ORDER BY e.exam_date ASC
    """, (student_name,)).fetchall()
    conn.close()
    return rows

def search_students(query):
    """搜索学生（去重）"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT DISTINCT student_name, class_name
        FROM scores
        WHERE student_name LIKE ?
        ORDER BY student_name
    """, (f'%{query}%',)).fetchall()
    conn.close()
    return rows

def get_all_students():
    conn = get_conn()
    rows = conn.execute("""
        SELECT DISTINCT student_name, class_name
        FROM scores
        ORDER BY student_name
    """).fetchall()
    conn.close()
    return rows

def get_duplicate_names(exam_id):
    """检查本次考试中是否有跟历史数据重名的学生"""
    conn = get_conn()
    existing = conn.execute("""
        SELECT DISTINCT student_name FROM scores
        WHERE exam_id != ?
    """, (exam_id,)).fetchall()
    current = conn.execute("""
        SELECT DISTINCT student_name FROM scores
        WHERE exam_id = ?
    """, (exam_id,)).fetchall()
    conn.close()
    existing_names = {r['student_name'] for r in existing}
    current_names = {r['student_name'] for r in current}
    # 返回同时存在于历史数据和本次数据中的名字
    # 注意：同名可能是同一个人，也可能是不同人，需要用户确认
    return list(existing_names & current_names)

def get_latest_exam_scores(student_name, exclude_exam_id=None):
    """获取某学生最近一次考试的成绩（用于进退步对比）"""
    conn = get_conn()
    if exclude_exam_id:
        row = conn.execute("""
            SELECT s.*, e.name as exam_name, e.exam_date
            FROM scores s
            JOIN exams e ON e.id = s.exam_id
            WHERE s.student_name = ? AND s.exam_id != ? AND s.is_absent = 0
            ORDER BY e.exam_date DESC
            LIMIT 1
        """, (student_name, exclude_exam_id)).fetchone()
    else:
        row = conn.execute("""
            SELECT s.*, e.name as exam_name, e.exam_date
            FROM scores s
            JOIN exams e ON e.id = s.exam_id
            WHERE s.student_name = ? AND s.is_absent = 0
            ORDER BY e.exam_date DESC
            LIMIT 1
        """, (student_name,)).fetchone()
    conn.close()
    return row

def get_class_students(class_name):
    """获取某班级的所有学生（去重）"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT DISTINCT student_name, class_name
        FROM scores
        WHERE class_name = ?
        ORDER BY student_name
    """, (class_name,)).fetchall()
    conn.close()
    return rows

def get_exam_class_scores(exam_id, class_name):
    """获取某次考试某班级的成绩"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM scores
        WHERE exam_id = ? AND class_name = ? AND is_absent = 0
        ORDER BY total_score DESC
    """, (exam_id, class_name)).fetchall()
    conn.close()
    return rows
