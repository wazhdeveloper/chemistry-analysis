"""分析计算"""
import re
from config import FULL_SCORE
from collections import defaultdict
from database import get_exam_by_id, get_exam_scores, get_all_students, get_conn as _get_conn, get_exam_class_scores


def normalize_class_name(class_name):
    """班级名归一化：'高一年级205班' → '205'，'205' → '205'"""
    nums = re.findall(r'\d+', str(class_name))
    return nums[0] if nums else class_name


def detect_platform(df):
    """根据列名自动识别平台（扫描前5行的内容）"""
    # 先看 df.columns 是否直接匹配
    col_set = {str(c).strip() for c in df.columns}
    if '学号' in col_set and '总得分' in col_set:
        return '新教育'
    if '准考证号' in col_set:
        return '智学网'

    # 再扫描前几行找标题行
    for i in range(min(5, len(df))):
        row_vals = [str(v).strip() for v in df.iloc[i].values if str(v).strip() not in ('nan', '', 'NaT')]
        if '学号' in row_vals and '总得分' in row_vals:
            return '新教育'
        if '准考证号' in row_vals:
            return '智学网'

    return None


def parse_xinjiaoyu(df):
    """解析新教育智能平台导出的 DataFrame
    返回: list of dict (成绩数据)
    """
    scores = []
    # 跳过前几行（标题、统计、表头），找到数据起始行
    data_start = None
    for i in range(len(df)):
        row = df.iloc[i]
        # 找包含"学号"的行作为表头
        if str(row.iloc[0]).strip() == '学号':
            data_start = i + 1
            break

    if data_start is None:
        return scores

    # 重设列名为第 data_start-1 行的值
    df_clean = df.iloc[data_start:].copy()
    new_cols = []
    for i, val in enumerate(df.iloc[data_start - 1]):
        name = str(val).strip()
        if name and name != 'nan':
            new_cols.append(name)
        else:
            new_cols.append(df.columns[i] if i < len(df.columns) else f'col_{i}')
    df_clean.columns = new_cols

    for _, row in df_clean.iterrows():
        name = str(row.get('姓名', '')).strip()
        if not name or name == 'nan' or name == '':
            continue

        # 检查是否缺考（学号列可能是"未交名单"所在行）
        student_id = str(row.get('学号', '')).strip()
        if '未交' in student_id or '未交' in name:
            continue

        total_score = _to_float(row.get('总得分'))
        if total_score is None:
            continue  # 缺考或无效数据

        scores.append({
            'student_name': name,
            'class_name': normalize_class_name(str(row.get('班级', ''))),
            'total_score': total_score,
            'objective_score': _to_float(row.get('客观题得分')),
            'subjective_score': _to_float(row.get('主观题得分')),
            'class_rank': _to_int(row.get('班级排名')),
            'grade_rank': _to_int(row.get('年级排名')),
            'is_absent': 0,
        })

    return scores


def parse_zhixuewang(df):
    """解析智学网导出的 DataFrame
    返回: list of dict (成绩数据)
    """
    scores = []

    # 找到表头行（包含"准考证号"的行）
    header_row = None
    for i in range(len(df)):
        row = df.iloc[i]
        for val in row:
            if str(val).strip() == '准考证号':
                header_row = i
                break
        if header_row is not None:
            break

    if header_row is None:
        return scores

    df_clean = df.iloc[header_row + 1:].copy()
    # 设置列名：用 header_row 的值，空值用原列名填充
    new_cols = []
    for i, val in enumerate(df.iloc[header_row]):
        name = str(val).strip()
        if name and name != 'nan':
            new_cols.append(name)
        else:
            new_cols.append(df.columns[i] if i < len(df.columns) else f'col_{i}')
    df_clean.columns = new_cols

    for _, row in df_clean.iterrows():
        name = str(row.get('姓名', '')).strip()
        if not name or name == 'nan' or name == '':
            continue

        score_str = str(row.get('得分', '')).strip()

        # 检查缺考
        if score_str == '未扫描' or score_str == '' or score_str == 'nan':
            # 缺考学生，记录但不计入有效成绩
            scores.append({
                'student_name': name,
                'class_name': normalize_class_name(str(row.get('班级', ''))),
                'total_score': None,
                'objective_score': None,
                'subjective_score': None,
                'class_rank': _to_int(row.get('班次') or row.get('班名')),
                'grade_rank': _to_int(row.get('校次') or row.get('校名')),
                'is_absent': 1,
            })
            continue

        total_score = _to_float(score_str)
        if total_score is None:
            continue

        scores.append({
            'student_name': name,
            'class_name': normalize_class_name(str(row.get('班级', ''))),
            'total_score': total_score,
            'objective_score': None,
            'subjective_score': None,
            'class_rank': _to_int(row.get('班次') or row.get('班名')),
            'grade_rank': _to_int(row.get('校次') or row.get('校名')),
            'is_absent': 0,
        })

    return scores


def _to_float(val):
    """安全转浮点"""
    if val is None:
        return None
    try:
        v = float(str(val).strip())
        return v
    except (ValueError, TypeError):
        return None


def _to_int(val):
    """安全转整数"""
    if val is None:
        return None
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return None


def calc_trend_data(student_scores):
    """计算趋势数据
    返回: {
        'exams': [(name, date), ...],
        'total': [score, ...],
        'objective': [score, ...],
        'subjective': [score, ...],
        'absent': [bool, ...]
    }
    """
    result = {
        'exams': [],
        'dates': [],
        'total': [],
        'objective': [],
        'subjective': [],
        'total_rank': [],
        'class_rank': [],
        'absent': [],
    }
    for s in student_scores:
        result['exams'].append((s['exam_name'], s['exam_date']))
        result['dates'].append(s['exam_date'])
        result['absent'].append(bool(s['is_absent']))

        if s['is_absent']:
            result['total'].append(None)
            result['objective'].append(None)
            result['subjective'].append(None)
            result['total_rank'].append(None)
            result['class_rank'].append(None)
        else:
            result['total'].append(s['total_score'])
            result['objective'].append(s['objective_score'])
            result['subjective'].append(s['subjective_score'])
            result['total_rank'].append(s['grade_rank'])
            result['class_rank'].append(s['class_rank'])

    return result


def calc_progress(current, previous):
    """计算进退步
    current, previous: dict with keys total_score, class_rank, grade_rank
    returns: dict with score_diff, class_rank_diff, grade_rank_diff
    """
    if current is None or previous is None:
        return None

    result = {}
    if current.get('total_score') is not None and previous.get('total_score') is not None:
        result['score_diff'] = round(current['total_score'] - previous['total_score'], 1)
    else:
        result['score_diff'] = None

    if current.get('class_rank') is not None and previous.get('class_rank') is not None:
        result['class_rank_diff'] = previous['class_rank'] - current['class_rank']
    else:
        result['class_rank_diff'] = None

    if current.get('grade_rank') is not None and previous.get('grade_rank') is not None:
        result['grade_rank_diff'] = previous['grade_rank'] - current['grade_rank']
    else:
        result['grade_rank_diff'] = None

    return result


def calc_class_stats(scores_list):
    """计算全班统计
    scores_list: list of dict or sqlite3.Row
    returns: dict with avg, max, min, pass_count, excellent_count
    """
    # 统一转 dict（兼容 sqlite3.Row）
    scores_list = [dict(s) if hasattr(s, 'keys') else s for s in scores_list]
    valid = [s for s in scores_list if s.get('total_score') is not None and not s.get('is_absent')]
    if not valid:
        return {}

    scores = [s['total_score'] for s in valid]
    avg = round(sum(scores) / len(scores), 1)

    # 客观题/主观题平均得分率
    obj_scores = [s['objective_score'] for s in valid if s.get('objective_score') is not None]
    subj_scores = [s['subjective_score'] for s in valid if s.get('subjective_score') is not None]

    result = {
        'count': len(valid),
        'avg': avg,
        'max': max(scores),
        'min': min(scores),
        'pass_count': sum(1 for s in scores if s >= 60),
        'excellent_count': sum(1 for s in scores if s >= 90),
        'pass_rate': round(sum(1 for s in scores if s >= 60) / len(scores) * 100, 1),
        'excellent_rate': round(sum(1 for s in scores if s >= 90) / len(scores) * 100, 1),
        'obj_avg': round(sum(obj_scores) / len(obj_scores), 1) if obj_scores else None,
        'subj_avg': round(sum(subj_scores) / len(subj_scores), 1) if subj_scores else None,
    }
    return result


def find_consecutive_declines(conn, min_times=2):
    """查找连续退步预警学生（最近 N 次成绩连续下降）
    返回: list of dict {student_name, class_name, consec_declines, latest_score, prev_score, latest_exam_id}
    已被教师忽略的最新考试的学生会被跳过。
    """
    from database import get_ignored_decline_pairs
    students = get_all_students()
    results = []
    db = conn or _get_conn()
    ignored_pairs = get_ignored_decline_pairs()
    for s in students:
        rows = db.execute("""
            SELECT s.total_score, s.exam_id, e.exam_date, e.name as exam_name
            FROM scores s
            JOIN exams e ON e.id = s.exam_id
            WHERE s.student_name = ? AND s.is_absent = 0
            ORDER BY e.exam_date DESC
        """, (s['student_name'],)).fetchall()

        if len(rows) < min_times + 1:
            continue

        # 若最新考试已被忽略，跳过该学生
        latest_exam_id = rows[0]['exam_id']
        if (s['student_name'], latest_exam_id) in ignored_pairs:
            continue

        consec = 0
        for i in range(len(rows) - 1):
            cur = rows[i]['total_score']
            prev = rows[i + 1]['total_score']
            if cur is not None and prev is not None and cur < prev:
                consec += 1
            else:
                break

        if consec >= min_times:
            results.append({
                'student_name': s['student_name'],
                'class_name': s['class_name'],
                'consec_declines': consec,
                'latest_score': rows[0]['total_score'],
                'prev_score': rows[1]['total_score'] if len(rows) > 1 else None,
                'latest_exam_id': latest_exam_id,
            })

    if not conn:
        db.close()
    # 按连续退步次数降序
    results.sort(key=lambda x: (-x['consec_declines'], x['class_name'], x['student_name']))
    return results


def get_top_decliners(exam_id, conn, top_n=5, class_name=None):
    """获取某次考试各班退步最大的前 top_n 名学生（按名次下降）
    如果指定 class_name，只返回该班级的退步学生
    返回: dict { class_name: [{student_name, prev_rank, current_rank, rank_diff}, ...] }
    """
    exam = get_exam_by_id(exam_id)
    if not exam:
        return {}

    # 找上一次考试（如果指定班级，找该班有数据的上次考试）
    if class_name:
        prev = conn.execute("""
            SELECT e.id FROM exams e
            WHERE e.exam_date < ? AND e.id IN (
                SELECT DISTINCT s.exam_id FROM scores s WHERE s.class_name = ?
            )
            ORDER BY e.exam_date DESC LIMIT 1
        """, (exam['exam_date'], class_name)).fetchone()
    else:
        prev = conn.execute("""
            SELECT id FROM exams
            WHERE exam_date < ? AND exam_date IS NOT NULL
            ORDER BY exam_date DESC LIMIT 1
        """, (exam['exam_date'],)).fetchone()

    if not prev:
        return {}

    current_scores = get_exam_scores(exam_id)
    prev_scores = get_exam_scores(prev['id'])

    # 建立上次成绩查找表（含排名）
    prev_map = {}
    for s in prev_scores:
        if not s['is_absent'] and s['class_rank'] is not None:
            prev_map[s['student_name']] = {
                'class_rank': s['class_rank'],
                'class_name': s['class_name'],
            }

    # 计算名次退步
    declines = []
    for s in current_scores:
        if s['is_absent'] or s['class_rank'] is None:
            continue
        name = s['student_name']
        if name in prev_map:
            # 名次数字变大 = 退步，数字变小 = 进步
            rank_diff = s['class_rank'] - prev_map[name]['class_rank']
            if rank_diff > 0:  # 退步
                declines.append({
                    'student_name': name,
                    'class_name': s['class_name'],
                    'prev_rank': prev_map[name]['class_rank'],
                    'current_rank': s['class_rank'],
                    'rank_diff': rank_diff,
                })

    # 按班级分组，取名次退步最大的前 N 名
    result = {}
    for d in sorted(declines, key=lambda x: x['rank_diff'], reverse=True):
        cls = d['class_name']
        if cls not in result:
            result[cls] = []
        if len(result[cls]) < top_n:
            result[cls].append(d)

    return result


def get_class_comparison(exam_id, class_name, conn):
    """获取某班某次考试 vs 上次考试的完整对比数据
    返回: {
        'current_exam': {...}, 'prev_exam': {...} or None,
        'big_decliners': [...],      # 降 ≥ 10 分
        'big_improvers': [...],      # 升 ≥ 10 分
        'consec_declines': [...],    # 连续退步
        'class_stats': {...},        # 本次全班统计
        'prev_class_stats': {...},   # 上次全班统计
        'detail_rows': [...],        # 全班明细表
    }
    """
    exam = get_exam_by_id(exam_id)
    if not exam:
        return {}

    # 找上一次有该班数据的考试
    prev_exam = conn.execute("""
        SELECT e.id, e.name, e.exam_date FROM exams e
        WHERE e.exam_date < ? AND e.id IN (
            SELECT DISTINCT s.exam_id FROM scores s WHERE s.class_name = ? AND s.is_absent = 0
        )
        ORDER BY e.exam_date DESC LIMIT 1
    """, (exam['exam_date'], class_name)).fetchone()

    current_scores = [dict(r) for r in get_exam_class_scores(exam_id, class_name)]
    prev_scores = [dict(r) for r in get_exam_class_scores(prev_exam['id'], class_name)] if prev_exam else []

    # 建立上次成绩查找表
    prev_map = {}
    for s in prev_scores:
        if not s.get('is_absent'):
            prev_map[s.get('student_name')] = s

    big_decliners = []   # 降 ≥ 10 分
    big_improvers = []   # 升 ≥ 10 分
    consec_declines = []  # 连续退步
    detail_rows = []

    for s in current_scores:
        if s['is_absent']:
            continue
        name = s['student_name']
        prev = prev_map.get(name)
        prev_score = prev['total_score'] if prev else None
        prev_rank = prev['class_rank'] if prev else None

        score_diff = round(s['total_score'] - prev_score, 1) if prev_score is not None else None
        rank_diff = prev_rank - s['class_rank'] if (prev_rank is not None and s['class_rank'] is not None) else None

        detail_rows.append({
            'student_name': name,
            'class_name': s['class_name'],
            'prev_score': prev_score,
            'current_score': s['total_score'],
            'score_diff': score_diff,
            'prev_rank': prev_rank,
            'current_rank': s['class_rank'],
            'rank_diff': rank_diff,
        })

        if score_diff is not None and score_diff <= -10:
            big_decliners.append(detail_rows[-1])
        if score_diff is not None and score_diff >= 10:
            big_improvers.append(detail_rows[-1])

    # 按分数差排序
    big_decliners.sort(key=lambda x: x['score_diff'])
    big_improvers.sort(key=lambda x: x['score_diff'], reverse=True)
    detail_rows.sort(key=lambda x: x['current_rank'] if x['current_rank'] else 999)

    # 连续退步检测（取这个班有 ≥3 次考试的学生）
    for s_name in set(d['student_name'] for d in detail_rows):
        rows = conn.execute("""
            SELECT s.total_score, e.exam_date
            FROM scores s JOIN exams e ON e.id = s.exam_id
            WHERE s.student_name = ? AND s.class_name = ? AND s.is_absent = 0
            ORDER BY e.exam_date DESC
        """, (s_name, class_name)).fetchall()
        if len(rows) < 3:
            continue
        c = 0
        for i in range(len(rows) - 1):
            if rows[i]['total_score'] is not None and rows[i+1]['total_score'] is not None \
               and rows[i]['total_score'] < rows[i+1]['total_score']:
                c += 1
            else:
                break
        if c >= 2:
            consec_declines.append({
                'student_name': s_name,
                'consec_declines': c,
                'latest_score': rows[0]['total_score'],
            })
    consec_declines.sort(key=lambda x: -x['consec_declines'])

    return {
        'current_exam': dict(exam),
        'prev_exam': dict(prev_exam) if prev_exam else None,
        'big_decliners': big_decliners,
        'big_improvers': big_improvers,
        'consec_declines': consec_declines,
        'class_stats': calc_class_stats(current_scores),
        'prev_class_stats': calc_class_stats(prev_scores) if prev_scores else None,
        'detail_rows': detail_rows,
        'student_count': len(current_scores),
    }


def get_class_avg_trends(conn):
    """获取各班每次考试的平均分，用于趋势图
    返回: {
        'exams': [{'id': 1, 'name': '月考1', 'date': '...'}, ...],
        'classes': {
            '205': [avg1, avg2, ...],
            '206': [avg1, avg2, ...],
        }
    }
    """
    exams = conn.execute("""
        SELECT id, name, exam_date FROM exams ORDER BY exam_date ASC
    """).fetchall()
    if not exams:
        return {'exams': [], 'classes': {}}

    classes = conn.execute("""
        SELECT DISTINCT class_name FROM scores ORDER BY class_name
    """).fetchall()
    class_names = [c['class_name'] for c in classes]

    result = {
        'exams': [{'id': e['id'], 'name': e['name'], 'date': e['exam_date']} for e in exams],
        'classes': {},
    }

    for cls in class_names:
        avgs = []
        for e in exams:
            row = conn.execute("""
                SELECT AVG(total_score) as avg_score FROM scores
                WHERE exam_id = ? AND class_name = ? AND is_absent = 0 AND total_score IS NOT NULL
            """, (e['id'], cls)).fetchone()
            avgs.append(round(row['avg_score'], 1) if row['avg_score'] else None)
        result['classes'][cls] = avgs

    return result


def analyze_student_trend(scores):
    """综合分析学生历次成绩趋势，生成评语
    scores: list of dict (from get_student_scores, 按日期升序)
    returns: dict with 评语, 标签, 各维度分析
    """
    valid = [s for s in scores if not s['is_absent'] and s['total_score'] is not None]
    if len(valid) < 2:
        return {'tag': '📊', 'comment': '数据不足，至少需要 2 次有效成绩才能分析趋势。', 'details': {}}

    n = len(valid)
    scores_list = [s['total_score'] for s in valid]
    avg_score = round(sum(scores_list) / n, 1)
    max_score = max(scores_list)
    min_score = min(scores_list)

    # ── 1. 总体趋势（线性回归斜率） ──
    xs = list(range(n))
    mean_x = (n - 1) / 2
    mean_y = avg_score
    num = sum((x - mean_x) * (scores_list[x] - mean_y) for x in xs)
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = round(num / den, 2) if den != 0 else 0

    # ── 2. 波动性 ──
    variance = sum((s - avg_score) ** 2 for s in scores_list) / n
    std_dev = round(variance ** 0.5, 1)

    # ── 3. 最近趋势（后3次 vs 前3次或全部之前） ──
    if n >= 3:
        recent_3 = scores_list[-3:]
        before = scores_list[:3] if n >= 6 else scores_list[:n-3]
        recent_avg = round(sum(recent_3) / 3, 1)
        before_avg = round(sum(before) / len(before), 1) if before else recent_avg
        recent_diff = round(recent_avg - before_avg, 1)
    else:
        recent_avg = avg_score
        before_avg = avg_score
        recent_diff = round(scores_list[-1] - scores_list[0], 1)

    # ── 4. 等级评估 ──
    def level(s):
        if s >= 90: return '优秀'
        if s >= 80: return '良好'
        if s >= 70: return '中等'
        if s >= 60: return '及格'
        return '待提升'

    current_level = level(scores_list[-1])
    levels = [level(s) for s in scores_list]
    main_level = max(set(levels), key=levels.count)

    # ── 5. 排名趋势 ──
    rank_trend = None
    rank_scores = [s for s in valid if s.get('class_rank') is not None]
    if len(rank_scores) >= 2:
        first_rank = rank_scores[0]['class_rank']
        last_rank = rank_scores[-1]['class_rank']
        rank_diff = first_rank - last_rank
        if rank_diff > 0:
            rank_trend = f'进步了 {rank_diff} 名'
        elif rank_diff < 0:
            rank_trend = f'退步了 {abs(rank_diff)} 名'
        else:
            rank_trend = '排名稳定'

    # ── 6. 客观题/主观题 ──
    obj_scores = [s['objective_score'] for s in valid if s.get('objective_score') is not None]
    subj_scores = [s['subjective_score'] for s in valid if s.get('subjective_score') is not None]
    obj_subj_comment = None
    if obj_scores and subj_scores and len(obj_scores) >= 2:
        obj_avg = round(sum(obj_scores) / len(obj_scores), 1)
        subj_avg = round(sum(subj_scores) / len(subj_scores), 1)
        obj_rate = round(obj_avg / 50 * 100) if obj_avg else None
        subj_rate = round(subj_avg / 50 * 100) if subj_avg else None
        if obj_rate and subj_rate:
            if obj_rate - subj_rate > 15:
                obj_subj_comment = f'选择题比填空题强（{obj_rate}% vs {subj_rate}%），建议加强主观题训练'
            elif subj_rate - obj_rate > 15:
                obj_subj_comment = f'填空题比选择题强（{subj_rate}% vs {obj_rate}%），选择题还有提升空间'
            else:
                obj_subj_comment = f'选择题和填空题发展均衡（{obj_rate}% / {subj_rate}%）'

    # ── 7. 连续升降检测 ──
    consec_up = 0
    consec_down = 0
    for i in range(n - 1, 0, -1):
        diff = scores_list[i] - scores_list[i - 1]
        if diff > 0:
            consec_up += 1
            consec_down = 0
        elif diff < 0:
            consec_down += 1
            consec_up = 0
        else:
            break

    # ── 8. 生成评语 ──
    parts = []

    # 总评开头
    if slope > 1.5:
        parts.append(f'📈 总体呈明显上升趋势')
    elif slope > 0.5:
        parts.append(f'📈 总体呈上升趋势')
    elif slope > -0.5:
        parts.append(f'➡️ 总体保持平稳')
    elif slope > -1.5:
        parts.append(f'📉 总体呈下降趋势')
    else:
        parts.append(f'📉 总体呈明显下降趋势')

    # 当前水平
    if current_level == '优秀':
        parts.append(f'🏆 当前处于优秀水平（{scores_list[-1]}分）')
    elif current_level == '良好':
        parts.append(f'👍 当前处于良好水平（{scores_list[-1]}分），冲击优秀还有 {round(90 - scores_list[-1])} 分')
    elif current_level == '中等':
        parts.append(f'💪 当前处于中等水平（{scores_list[-1]}分），冲上良好还需 {round(80 - scores_list[-1])} 分')
    elif current_level == '及格':
        parts.append(f'⚠️ 当前处于及格边缘（{scores_list[-1]}分），需要抓紧了')
    else:
        parts.append(f'🔴 当前分数偏低（{scores_list[-1]}分），要加油啦')

    # 波动性
    if std_dev > 10:
        parts.append(f'📊 成绩波动较大（标准差{std_dev}），发挥不太稳定')
    elif std_dev > 5:
        parts.append(f'📊 成绩有一定波动（标准差{std_dev}），有提升空间')
    else:
        parts.append(f'📊 成绩稳定（标准差{std_dev}）')

    # 最近趋势
    if n >= 3:
        if recent_diff > 5:
            parts.append(f'🔥 近期进步明显（后3次平均 {recent_avg}，较之前提高 {recent_diff} 分）')
        elif recent_diff > 0:
            parts.append(f'📈 近期略有进步（后3次平均 {recent_avg}，较之前提高 {recent_diff} 分）')
        elif recent_diff > -5:
            parts.append(f'📉 近期略有下滑（后3次平均 {recent_avg}，较之前下降 {abs(recent_diff)} 分）')
        else:
            parts.append(f'⚠️ 近期下滑明显（后3次平均 {recent_avg}，较之前下降 {abs(recent_diff)} 分）')

    # 连续升降
    if consec_down >= 2:
        parts.append(f'⚠️ 连续 {consec_down} 次成绩下降，需要关注')
    if consec_up >= 2:
        parts.append(f'🔥 连续 {consec_up} 次成绩上升，保持势头！')

    # 排名
    if rank_trend:
        parts.append(f'🏅 班级排名 {rank_trend}')

    # 客观/主观
    if obj_subj_comment:
        parts.append(f'🎯 {obj_subj_comment}')

    # 高低分差
    if max_score - min_score > 20:
        parts.append(f'📉 高低分差 {max_score - min_score} 分（最高 {max_score} / 最低 {min_score}），发挥空间较大')
    elif max_score - min_score > 10:
        parts.append(f'📊 高低分差 {max_score - min_score} 分（最高 {max_score} / 最低 {min_score}）')

    # 标签
    if current_level == '优秀' and slope > 0:
        tag = '🌟 优等生'
    elif consec_down >= 2:
        tag = '⚠️ 需关注'
    elif slope > 1:
        tag = '🚀 进步之星'
    elif slope < -1:
        tag = '📉 需要加油'
    elif current_level in ('优秀', '良好') and std_dev < 5:
        tag = '✅ 稳定优秀'
    elif current_level in ('良好', '中等') and slope > 0:
        tag = '📈 稳步提升'
    else:
        tag = f'📊 {current_level}'

    return {
        'tag': tag,
        'comment': '\n'.join(parts),
        'details': {
            'avg': avg_score,
            'max': max_score,
            'min': min_score,
            'std_dev': std_dev,
            'slope': slope,
            'current_level': current_level,
            'recent_diff': recent_diff,
            'consec_up': consec_up,
            'consec_down': consec_down,
            'rank_trend': rank_trend,
            'n_exams': n,
        }
    }
