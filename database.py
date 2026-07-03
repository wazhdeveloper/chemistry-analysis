"""数据库操作"""
import sqlite3
import os
import shutil
from config import DB_PATH

BACKUP_DIR = os.path.join(os.path.dirname(DB_PATH), 'excel_backups')

def get_backup_path(exam_id):
    """获取备份 Excel 文件路径"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    # 查找对应考试的备份文件
    for f in os.listdir(BACKUP_DIR):
        if f.startswith(f'{exam_id}.'):
            return os.path.join(BACKUP_DIR, f)
    return None

def save_backup(exam_id, file_bytes, ext='.xlsx'):
    """保存原始 Excel 备份"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, f'{exam_id}{ext}')
    with open(path, 'wb') as f:
        f.write(file_bytes)
    return path

def delete_backup(exam_id):
    """删除备份 Excel"""
    path = get_backup_path(exam_id)
    if path and os.path.exists(path):
        os.remove(path)

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

        CREATE TABLE IF NOT EXISTS ignored_declines (
            student_name TEXT NOT NULL,
            exam_id      INTEGER NOT NULL,
            ignored_at   TEXT DEFAULT (datetime('now','localtime')),
            PRIMARY KEY (student_name, exam_id),
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()


# ── 忽略退步预警操作 ──

def add_ignored_decline(student_name, exam_id):
    """忽略某学生某次考试的连续退步预警"""
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO ignored_declines (student_name, exam_id) VALUES (?, ?)",
        (student_name, exam_id)
    )
    conn.commit()
    conn.close()


def remove_ignored_decline(student_name, exam_id):
    """取消忽略，恢复退步预警"""
    conn = get_conn()
    conn.execute(
        "DELETE FROM ignored_declines WHERE student_name=? AND exam_id=?",
        (student_name, exam_id)
    )
    conn.commit()
    conn.close()


def get_ignored_decline_pairs():
    """获取所有被忽略的 (student_name, exam_id) 对"""
    conn = get_conn()
    rows = conn.execute("SELECT student_name, exam_id FROM ignored_declines").fetchall()
    conn.close()
    return {(r['student_name'], r['exam_id']) for r in rows}

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
    import logging; logging.warning("[DB_DEBUG] get_exams v3 called - NO ORDER BY in SQL")
    conn = get_conn()
    rows = conn.execute("SELECT * FROM exams").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        cnt = conn.execute(
            "SELECT COUNT(*) as c FROM scores WHERE exam_id=? AND is_absent=0",
            (d['id'],)
        ).fetchone()['c']
        d['student_count'] = cnt
        cls = conn.execute(
            "SELECT DISTINCT class_name FROM scores WHERE exam_id=? AND is_absent=0",
            (d['id'],)
        ).fetchall()
        d['class_names'] = ', '.join(c['class_name'] for c in cls)
        result.append(d)
    conn.close()
    result.sort(key=lambda x: x['exam_date'], reverse=True)
    return result

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
