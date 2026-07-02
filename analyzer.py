"""分析计算"""
import re
from config import FULL_SCORE


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
    scores_list: list of dict
    returns: dict with avg, max, min, pass_count, excellent_count
    """
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


def get_top_decliners(exam_id, conn, top_n=5):
    """获取某次考试各班退步最大的前 top_n 名学生（按名次下降）
    返回: dict { class_name: [{student_name, prev_rank, current_rank, rank_diff}, ...] }
    """
    from database import get_exam_by_id, get_exam_scores
    exam = get_exam_by_id(exam_id)
    if not exam:
        return {}

    # 找上一次考试
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
