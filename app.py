"""化学成绩分析系统 - Streamlit 主程序"""
import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date

from database import init_db, add_exam, delete_exam, get_exams
from database import add_scores, get_exam_scores, get_student_scores
from database import search_students, get_all_students, get_latest_exam_scores
from database import get_exam_by_id, get_exam_class_scores
from analyzer import (
    detect_platform, parse_xinjiaoyu, parse_zhixuewang,
    calc_trend_data, calc_progress, calc_class_stats,
    normalize_class_name, get_top_decliners, find_consecutive_declines,
    get_class_comparison, get_class_avg_trends
)
from database import get_conn

# ── Excel 备份 ──
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'excel_backups')

def _get_backup_path(exam_id):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    for f in os.listdir(BACKUP_DIR):
        if f.startswith(f'{exam_id}.'):
            return os.path.join(BACKUP_DIR, f)
    return None

def _save_backup(exam_id, file_bytes, ext='.xlsx'):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, f'{exam_id}{ext}')
    with open(path, 'wb') as f:
        f.write(file_bytes)
    return path

def _delete_backup(exam_id):
    path = _get_backup_path(exam_id)
    if path and os.path.exists(path):
        os.remove(path)

# ── 页面配置 ──
st.set_page_config(page_title="化学成绩分析", page_icon="📊", layout="wide")

# ── 自定义样式 ──
st.markdown("""
<style>
    /* 整体色调 */
    .stApp { background: #f5f7fb; }

    .main > div { padding: 0 0.5rem; }


    /* 标题区 */
    .app-header {
        background: linear-gradient(135deg, #1a73e8, #0d47a1);
        color: white;
        padding: 1.2rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 0.8rem;
        box-shadow: 0 2px 12px rgba(26,115,232,0.15);
    }
    .app-header h1 { margin: 0; font-size: 1.6rem; color: white; }
    .app-header span { font-size: 1.8rem; opacity: 0.9; }

    /* 卡片 */
    .card {
        background: white;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 1px 6px rgba(0,0,0,0.06);
        border: 1px solid #eef0f4;
    }
    .card-warn {
        background: #fff8f0;
        border-left: 4px solid #f59e0b;
    }
    .card-good {
        background: #f0fdf4;
        border-left: 4px solid #22c55e;
    }

    /* 考试条目 */
    .exam-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.6rem 0;
        border-bottom: 1px solid #f0f0f0;
    }
    .exam-item:last-child { border-bottom: none; }

    /* Metric 数字 */
    .metric-box {
        text-align: center;
        padding: 0.8rem;
        background: #f8faff;
        border-radius: 8px;
        border: 1px solid #e8edf5;
    }
    .metric-box .num { font-size: 1.8rem; font-weight: 700; }
    .metric-box .label { font-size: 0.75rem; color: #6b7280; margin-top: 0.2rem; }
    .metric-box.green .num { color: #16a34a; }
    .metric-box.red .num { color: #dc2626; }
    .metric-box.orange .num { color: #f59e0b; }
    .metric-box.blue .num { color: #2563eb; }

    /* 退步学生条目 */
    .decline-row {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        padding: 0.4rem 0;
    }
    .decline-row .name { font-weight: 600; min-width: 5rem; }
    .decline-row .arrow { color: #dc2626; font-weight: 700; min-width: 3rem; }
    .decline-row .rank { color: #6b7280; font-size: 0.85rem; }

    /* 侧边栏 */
    .css-1d391kg, .css-163ttbj { background: #ffffff; }
    .sidebar-info {
        background: #f0f7ff;
        border-radius: 8px;
        padding: 0.8rem;
        margin-top: 0.5rem;
        text-align: center;
    }

    /* 分割线美化 */
    hr { margin: 1.2rem 0; border-color: #eef0f4; }

    /* 学生详情头部 */
    .student-header {
        background: linear-gradient(135deg, #1e40af, #3b82f6);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 12px rgba(59,130,246,0.2);
    }
    .student-header h2 { margin: 0; color: white; font-size: 1.5rem; }
    .student-header .sub { opacity: 0.8; font-size: 0.9rem; margin-top: 0.3rem; }


    /* 数据表格 */
    .dataframe { font-size: 0.85rem; }

</style>
""", unsafe_allow_html=True)

# ── 初始化 ──
init_db()
if 'page' not in st.session_state:
    st.session_state.page = 'home'
if 'selected_student' not in st.session_state:
    st.session_state.selected_student = None
if 'selected_exam_id' not in st.session_state:
    st.session_state.selected_exam_id = None
if 'import_success' not in st.session_state:
    st.session_state.import_success = None
if 'overview_exam_id' not in st.session_state:
    st.session_state.overview_exam_id = None
if 'overview_class' not in st.session_state:
    st.session_state.overview_class = None
if 'editing_exam' not in st.session_state:
    st.session_state.editing_exam = None

# ── 侧边栏导航 ──
st.sidebar.markdown("## 📊 化学成绩分析")
st.sidebar.markdown("---")

if st.sidebar.button("🏠 首页", use_container_width=True):
    st.session_state.page = 'home'
    st.session_state.selected_student = None
    st.session_state.selected_exam_id = None
    st.rerun()

if st.sidebar.button("📥 导入新成绩", use_container_width=True):
    st.session_state.page = 'import'
    st.rerun()

if st.sidebar.button("📉 班级分析", use_container_width=True):
    st.session_state.page = 'class_overview'
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("💡 点击学生姓名查看趋势")
st.sidebar.markdown("---")
st.sidebar.markdown("**👥 全部学生**")
all_students = get_all_students()
classes = {}
for s in all_students:
    cls = s['class_name']
    if cls not in classes:
        classes[cls] = []
    classes[cls].append(s['student_name'])
for cls_name in sorted(classes.keys(), key=lambda x: int(x) if x.isdigit() else x):
    with st.sidebar.expander(f"🏫 {cls_name}班（{len(classes[cls_name])} 人）", expanded=False):
        for name in sorted(classes[cls_name]):
            if st.button(f"👤 {name}", key=f"sb_{name}", use_container_width=True):
                st.session_state.selected_student = name
                st.session_state.page = 'student'
                st.rerun()

# 如果正在查看学生页面，侧边栏显示学生信息
if st.session_state.page == 'student' and st.session_state.selected_student:
    st.sidebar.markdown(f"**当前查看：**")
    st.sidebar.markdown(f"👤 {st.session_state.selected_student}")
    if st.sidebar.button("← 返回首页", use_container_width=True):
        st.session_state.page = 'home'
        st.session_state.selected_student = None
        st.rerun()

# ════════════════════════════════════════════════
# 页面：首页
# ════════════════════════════════════════════════
def render_home():
    st.markdown('<div class="app-header"><span>📊</span><h1>化学成绩分析</h1></div>', unsafe_allow_html=True)

    # 导入成功提示
    if st.session_state.import_success:
        st.success(st.session_state.import_success)
        st.session_state.import_success = None

    # 处理链接参数
    edit_id = st.query_params.get("edit")
    if edit_id:
        try:
            eid = int(edit_id)
            bp = _get_backup_path(eid)
            if bp:
                os.startfile(bp)
                st.session_state.editing_exam = eid
        except:
            pass
        st.query_params.clear()
        st.rerun()

    delete_id = st.query_params.get("delete")
    if delete_id:
        try:
            did = int(delete_id)
            _delete_backup(did)
            delete_exam(did)
        except:
            pass
        st.query_params.clear()
        st.rerun()

    col1, col2 = st.columns([7, 3])
    with col1:
        exams = get_exams()
        if exams:
            with st.expander(f"📋 考试记录（共 {len(exams)} 次）", expanded=False):
                for e in exams:
                    c1, c2, c3, c4 = st.columns([4, 3, 1, 1])
                    with c1:
                        cls_names = e.get('class_names', '') or ''
                        st.markdown(f'<b>{e["name"]}</b>　<span style="color:#6b7280;font-size:0.85rem">🏫 {cls_names}</span>', unsafe_allow_html=True)
                    with c2:
                        st.markdown(f'📅 {e["exam_date"]}　👥 {e["student_count"]} 人', unsafe_allow_html=True)
                    with c3:
                        bp = _get_backup_path(e['id'])
                        if bp:
                            st.markdown(f'<a href="?edit={e["id"]}" style="color:#2563eb;text-decoration:none;cursor:pointer">编辑</a>', unsafe_allow_html=True)
                        else:
                            st.markdown('<span style="color:#999">--</span>', unsafe_allow_html=True)
                    with c4:
                        st.markdown(f'<a href="?delete={e["id"]}" style="color:#dc2626;text-decoration:none" onclick="return confirm(\'确定删除「{e["name"]}」吗？\')">删除</a>', unsafe_allow_html=True)
                # 重新读取更新
                if st.session_state.get('editing_exam'):
                    eid = st.session_state.editing_exam
                    bp = _get_backup_path(eid)
                    if bp and os.path.exists(bp):
                        st.info(f'已打开备份文件，编辑保存后点击下方按钮更新数据')
                        if st.button("📥 已编辑完成，重新读取更新", key=f"reload_{eid}", type="primary"):
                            try:
                                import pandas as pd
                                df = pd.read_excel(bp) if bp.endswith('.xlsx') else pd.read_excel(bp, engine='xlrd')
                                platform = detect_platform(df)
                                if platform == '新教育':
                                    new_scores = parse_xinjiaoyu(df)
                                elif platform == '智学网':
                                    new_scores = parse_zhixuewang(df)
                                else:
                                    st.error('无法识别文件格式')
                                    st.session_state.editing_exam = None
                                    st.rerun()
                                if new_scores:
                                    conn = get_conn()
                                    conn.execute("DELETE FROM scores WHERE exam_id=?", (eid,))
                                    conn.commit()
                                    conn.close()
                                    add_scores(eid, new_scores)
                                    st.success('✅ 更新成功！')
                                st.session_state.editing_exam = None
                                st.rerun()
                            except Exception as ex:
                                st.error(f'重新读取失败: {ex}')
                    else:
                        st.session_state.editing_exam = None
        else:
            st.markdown('<div class="card">📭 还没有考试数据，点击左侧「导入新成绩」开始吧！</div>', unsafe_allow_html=True)

        # 📈 各班平均分变化曲线
        if exams:
            conn = get_conn()
            trend_data = get_class_avg_trends(conn)
            conn.close()
            if trend_data['exams'] and trend_data['classes']:
                n_exams = len(trend_data['exams'])
                cat_labels = [e['date'][5:] for e in trend_data['exams']]
                fig_class = go.Figure()
                colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b',
                          '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
                for i, (cls, avgs) in enumerate(sorted(trend_data['classes'].items())):
                    color = colors[i % len(colors)]
                    fig_class.add_trace(go.Scatter(
                        x=cat_labels, y=avgs,
                        mode='lines+markers+text',
                        name=f'{cls}班',
                        line=dict(color=color, width=2.5),
                        marker=dict(size=8, color=color),
                        text=[str(avgs[j]) if avgs[j] else '' for j in range(n_exams)],
                        textposition='top center',
                        textfont=dict(size=10, color=color),
                        connectgaps=True,
                        hovertemplate=f'{cls}班<br>%{{x}}<br>平均分: %{{y}}<extra></extra>',
                    ))
                fig_class.update_layout(
                    title=dict(text="📈 各班平均分变化趋势", font=dict(size=16)),
                    xaxis_title="考试日期", yaxis_title="平均分",
                    yaxis=dict(range=[0, 105]),
                    xaxis=dict(type='category'),
                    height=400, hovermode='x unified',
                    margin=dict(l=20, r=20, t=40, b=40),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                )
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.plotly_chart(fig_class, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

        # ⚠️ 退步预警
        if exams:
            conn = get_conn()
            # 找最新考试日期，合并同一天的各班考试
            latest_date = conn.execute("SELECT MAX(exam_date) FROM exams").fetchone()[0]
            latest_exams = conn.execute(
                "SELECT id, name FROM exams WHERE exam_date=? ORDER BY id", (latest_date,)
            ).fetchall()
            all_exam_ids = [e['id'] for e in latest_exams]
            exam_name = latest_exams[0]['name'] if latest_exams else ''

            # 获取这些考试涉及的所有班级
            placeholders = ','.join('?' * len(all_exam_ids))
            all_cls = [r['class_name'] for r in conn.execute(
                f"SELECT DISTINCT class_name FROM scores WHERE exam_id IN ({placeholders}) AND is_absent=0 ORDER BY class_name",
                all_exam_ids
            ).fetchall()]
            if all_cls:
                if 'top_n' not in st.session_state:
                    st.session_state.top_n = 5
                st.markdown(f'<div class="card card-warn"><b>⚠️ 退步预警</b> — 「{exam_name}」', unsafe_allow_html=True)
                c_sel1, c_sel2 = st.columns(2)
                with c_sel1:
                    sel_cls = st.selectbox("选择班级", all_cls, key="decline_class")
                # 找到该班级在最新日期对应的考试 ID（各班级独立一条记录）
                cls_exam = conn.execute(
                    "SELECT e.id FROM exams e "
                    "JOIN scores s ON s.exam_id = e.id "
                    "WHERE e.exam_date = ? AND s.class_name = ? AND s.is_absent = 0 "
                    "LIMIT 1",
                    (latest_date, sel_cls)
                ).fetchone()
                if cls_exam:
                    # 直接在这里查退步，绕开 analyzer 的缓存问题
                    exam_id = cls_exam['id']
                    exam_row = get_exam_by_id(exam_id)
                    prev_row = conn.execute("""
                        SELECT e.id FROM exams e
                        WHERE e.exam_date < ? AND e.id IN (
                            SELECT DISTINCT s.exam_id FROM scores s WHERE s.class_name = ?
                        )
                        ORDER BY e.exam_date DESC LIMIT 1
                    """, (exam_row['exam_date'], sel_cls)).fetchone()
                    cls_decliners = []
                    if prev_row:
                        prev_scores = get_exam_scores(prev_row['id'])
                        cur_scores = get_exam_scores(exam_id)
                        prev_map = {}
                        for ps in prev_scores:
                            if not ps['is_absent'] and ps['class_rank'] is not None and ps['class_name'] == sel_cls:
                                prev_map[ps['student_name']] = ps['class_rank']
                        for cs in cur_scores:
                            if cs['is_absent'] or cs['class_rank'] is None or cs['class_name'] != sel_cls:
                                continue
                            if cs['student_name'] in prev_map:
                                rd = cs['class_rank'] - prev_map[cs['student_name']]
                                if rd > 0:
                                    cls_decliners.append({
                                        'student_name': cs['student_name'],
                                        'class_name': sel_cls,
                                        'prev_rank': prev_map[cs['student_name']],
                                        'current_rank': cs['class_rank'],
                                        'rank_diff': rd,
                                    })
                    cls_decliners.sort(key=lambda x: x['rank_diff'], reverse=True)
                    max_n = len(cls_decliners)
                    with c_sel2:
                        if max_n > 0:
                            top_n = st.number_input(f"显示人数（最大{max_n}）", min_value=1, max_value=max_n,
                                                     value=min(st.session_state.top_n, max_n), step=1,
                                                     key="top_n_input")
                            st.session_state.top_n = top_n
                        else:
                            st.markdown('<div style="height:2.5rem"></div>', unsafe_allow_html=True)
                            top_n = 0
                    for s in cls_decliners[:top_n]:
                            st.markdown(
                                f'<div class="decline-row">'
                                f'<span class="name">🔻 {s["student_name"]}</span>'
                                f'<span class="rank">{s["prev_rank"]}名 → {s["current_rank"]}名</span>'
                                f'<span class="arrow">↓{s["rank_diff"]}名</span>'
                                f'</div>',
                                unsafe_allow_html=True
                            )
                            if st.button(f"查看 {s['student_name']}", key=f"d_{s['student_name']}_{cls_exam['id']}", use_container_width=True):
                                st.session_state.selected_student = s['student_name']
                                st.session_state.page = 'student'
                                st.rerun()
                    else:
                        st.info(f'{sel_cls}班 本次没有退步学生')
                st.markdown('</div>', unsafe_allow_html=True)
            conn.close()

            # 🔄 连续退步预警
            conn = get_conn()
            consec_declines = find_consecutive_declines(conn, min_times=2)
            if consec_declines:
                cd_by_class = {}
                for cd in consec_declines:
                    cls = cd['class_name']
                    if cls not in cd_by_class:
                        cd_by_class[cls] = []
                    cd_by_class[cls].append(cd)

                st.markdown(f'<div class="card card-warn"><b>🔄 连续退步预警（≥2次）</b>', unsafe_allow_html=True)
                cls_list2 = sorted(cd_by_class.keys(), key=lambda x: int(x) if x.isdigit() else x)
                sel_cls2 = st.selectbox("选择班级", cls_list2, key="consec_class")
                for cd in cd_by_class.get(sel_cls2, []):
                    st.markdown(
                        f'<div class="decline-row">'
                        f'<span class="name">🔻 {cd["student_name"]}</span>'
                        f'<span class="rank">最近 {cd["consec_declines"]} 次连续下降</span>'
                        f'<span class="arrow">{cd["latest_score"]}分 ← {cd["prev_score"]}分</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                    if st.button(f"查看 {cd['student_name']}", key=f"cd_{cd['student_name']}_{sel_cls2}", use_container_width=True):
                        st.session_state.selected_student = cd['student_name']
                        st.session_state.page = 'student'
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            conn.close()

    with col2:
        st.markdown('<div class="card"><b>🔍 搜索学生</b>', unsafe_allow_html=True)
        query = st.text_input("输入学生姓名", label_visibility="collapsed",
                              placeholder="输入姓名搜索...")
        if query:
            results = search_students(query)
            if results:
                for r in results:
                    if st.button(f"👤 {r['student_name']} · {r['class_name']}班",
                                 key=f"search_{r['student_name']}",
                                 use_container_width=True):
                        st.session_state.selected_student = r['student_name']
                        st.session_state.page = 'student'
                        st.rerun()
            else:
                st.caption("未找到该学生")
        st.markdown('</div>', unsafe_allow_html=True)



# ════════════════════════════════════════════════
# 页面：导入
# ════════════════════════════════════════════════
def render_import():
    st.markdown('<div class="app-header"><span>📥</span><h1>导入新成绩</h1></div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "选择 Excel 文件（支持 .xlsx / .xls）",
        type=['xlsx', 'xls']
    )

    if uploaded_file is not None:
        # 读取文件
        try:
            if uploaded_file.name.endswith('.xls'):
                df = pd.read_excel(uploaded_file, engine='xlrd')
            else:
                df = pd.read_excel(uploaded_file, engine='openpyxl')
        except Exception as e:
            st.error(f"读取文件失败：{e}")
            return

        # 自动识别平台
        platform = detect_platform(df)
        if not platform:
            st.error("❌ 无法识别文件格式。请确认是从新教育智能平台或智学网导出的成绩单。")
            st.markdown("**支持的格式：**")
            st.markdown("- 📘 新教育平台：包含「学号」「总得分」「客观题得分」等列")
            st.markdown("- 📗 智学网：包含「准考证号」「得分」「班次」等列")
            return

        st.success(f"✅ 识别到：**{platform}**")

        # 解析数据
        if platform == '新教育':
            scores = parse_xinjiaoyu(df)
        else:
            scores = parse_zhixuewang(df)

        if not scores:
            st.warning("未能从文件中解析出有效成绩数据，请检查文件格式。")
            return

        # 统计
        total = len(scores)
        absent = sum(1 for s in scores if s['is_absent'])
        valid = total - absent

        st.success(f"共识别 **{total}** 名学生，其中缺考 **{absent}** 人，有效成绩 **{valid}** 人")

        # 显示预览
        st.markdown('<div class="card"><b>📋 数据预览</b>（前 20 条）', unsafe_allow_html=True)
        preview_df = pd.DataFrame([{
            '姓名': s['student_name'],
            '班级': s['class_name'],
            '得分': s['total_score'] if not s['is_absent'] else '缺考',
            '班级排名': s['class_rank'] if s.get('class_rank') else '',
            '年级排名': s['grade_rank'] if s.get('grade_rank') else '',
        } for s in scores[:20]])
        st.dataframe(preview_df, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 考试信息
        st.markdown('<div class="card"><b>📋 考试信息</b>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            exam_type = st.selectbox("考试类型", ["限时练习", "月考", "期中", "期末", "统考", "自定义"])
            if exam_type == "自定义":
                exam_name = st.text_input("自定义考试名称", placeholder="请输入名称")
            else:
                exam_name = exam_type
        with col2:
            exam_date = st.date_input("考试日期", value=date.today())

        # 重名检测
        if exam_name:
            existing_names = set()
            for s in get_all_students():
                existing_names.add(s['student_name'])
            current_names = {s['student_name'] for s in scores if not s['is_absent']}
            duplicate_names = existing_names & current_names
            if duplicate_names:
                st.warning(
                    f"⚠️ 检测到 **{len(duplicate_names)}** 名同学与历史数据重名："
                    f"{'、'.join(list(duplicate_names)[:10])}"
                    f"{'…' if len(duplicate_names) > 10 else ''}"
                    "\n\n如果确认是同一批学生，直接导入即可。"
                )

        if st.button("✅ 确认导入", type="primary", use_container_width=True):
            if not exam_name:
                st.error("请输入考试名称")
                return
            exam_id = add_exam(exam_name, platform, str(exam_date))
            add_scores(exam_id, scores)
            # 备份原始 Excel
            ext = os.path.splitext(uploaded_file.name)[1] or '.xlsx'
            _save_backup(exam_id, uploaded_file.getvalue(), ext)
            st.session_state.import_success = f"✅ 「{exam_name}」导入成功！共 {valid} 条有效成绩"
            st.session_state.page = 'home'
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════
# 页面：学生详情
# ════════════════════════════════════════════════
def render_student():
    name = st.session_state.selected_student
    if not name:
        st.session_state.page = 'home'
        st.rerun()
        return

    scores = get_student_scores(name)
    if not scores:
        st.error(f"未找到学生「{name}」的成绩数据")
        if st.button("← 返回首页"):
            st.session_state.page = 'home'
            st.session_state.selected_student = None
            st.rerun()
        return

    # 学生基本信息
    class_name = scores[0]['class_name']
    st.markdown(
        f'<div class="student-header">'
        f'<h2>👤 {name}</h2>'
        f'<div class="sub">{class_name}班</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    # 返回按钮
    if st.button("← 返回首页"):
        st.session_state.page = 'home'
        st.session_state.selected_student = None
        st.rerun()

    # 计算趋势数据
    trend = calc_trend_data(scores)

    # ── 总分趋势图 ──
    st.markdown('<div class="card"><b>📈 化学总分趋势</b>', unsafe_allow_html=True)

    fig_total = go.Figure()
    # 横轴：考试名称在上，日期在下
    x_labels = []
    for s in scores:
        d = str(s['exam_date'])
        if len(d) >= 10:
            label = f"{s['exam_name']}<br>{d[5:10]}"
        else:
            label = s['exam_name']
        x_labels.append(label)

    # 有效成绩点
    valid_x = []
    valid_y = []
    valid_text = []
    absent_x = []
    absent_y = []

    for i, s in enumerate(scores):
        if s['is_absent']:
            absent_x.append(x_labels[i])
            absent_y.append(0)  # 占位
        else:
            valid_x.append(x_labels[i])
            valid_y.append(s['total_score'])
            valid_text.append(f"{s['total_score']}分")

    # 绘制折线（只连接有效点）
    if len(valid_y) >= 1:
        fig_total.add_trace(go.Scatter(
            x=valid_x, y=valid_y,
            mode='lines+markers+text',
            name='总分',
            line=dict(color='#1f77b4', width=2.5),
            marker=dict(size=10, color='#1f77b4'),
            text=valid_text,
            textposition='top center',
            textfont=dict(size=11, color='#1f77b4'),
            hovertemplate='%{x}<br>%{text}<extra></extra>'
        ))

    # 标注缺考
    for ax in absent_x:
        fig_total.add_annotation(
            x=ax, y=50,
            text="✗ 缺考",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowcolor='#999',
            font=dict(color='#999', size=12)
        )

    fig_total.update_layout(
        xaxis_title="考试",
        yaxis_title="得分",
        yaxis=dict(range=[0, 105]),
        xaxis=dict(type='category'),  # 明确为分类轴，不让 Plotly 当成日期
        height=400,
        hovermode='x unified',
        margin=dict(l=20, r=20, t=20, b=40)
    )
    st.plotly_chart(fig_total, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 进退步分析 ──
    st.markdown('<div class="card"><b>📉 进退步分析</b>', unsafe_allow_html=True)

    current = None
    previous = None
    for s in reversed(scores):
        if not s['is_absent']:
            if current is None:
                current = s
            elif previous is None:
                previous = s
            break
    if current:
        for s in reversed(scores):
            if not s['is_absent'] and s['exam_id'] != current['exam_id']:
                previous = s
                break

    if current:
        c = {
            'total_score': current['total_score'],
            'class_rank': current['class_rank'],
            'grade_rank': current['grade_rank'],
        }
        p = {
            'total_score': previous['total_score'] if previous else None,
            'class_rank': previous['class_rank'] if previous else None,
            'grade_rank': previous['grade_rank'] if previous else None,
        } if previous else None

        # 用自定义 metric box
        col1, col2, col3 = st.columns(3)
        cur_score = current['total_score']
        score_color = 'green' if cur_score >= 80 else 'orange' if cur_score >= 60 else 'red'

        with col1:
            st.markdown(
                f'<div class="metric-box {score_color}">'
                f'<div class="num">{cur_score}</div>'
                f'<div class="label">本次得分</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        with col2:
            if p and p['total_score']:
                diff = round(c['total_score'] - p['total_score'], 1)
                dcolor = 'red' if diff < 0 else 'green'
                st.markdown(
                    f'<div class="metric-box {dcolor}">'
                    f'<div class="num">{diff:+.1f}</div>'
                    f'<div class="label">较上次（{p["total_score"]}分）</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown('<div class="metric-box blue"><div class="num">—</div><div class="label">首次考试</div></div>', unsafe_allow_html=True)
        with col3:
            if c['class_rank']:
                if p and p['class_rank']:
                    rdiff = p['class_rank'] - c['class_rank']
                    rcolor = 'red' if rdiff < 0 else 'green'
                    label = f'较上次（第{p["class_rank"]}名）'
                    st.markdown(
                        f'<div class="metric-box {rcolor}">'
                        f'<div class="num">第{c["class_rank"]}名</div>'
                        f'<div class="label">{label}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f'<div class="metric-box blue"><div class="num">第{c["class_rank"]}名</div><div class="label">班级排名</div></div>',
                        unsafe_allow_html=True
                    )
            else:
                st.markdown('<div class="metric-box blue"><div class="num">—</div><div class="label">班级排名</div></div>', unsafe_allow_html=True)

        # 连续退步检测
        consec_decline = 0
        for i in range(len(scores) - 1, 0, -1):
            if scores[i]['is_absent'] or scores[i-1]['is_absent']:
                break
            cur_s = scores[i]['total_score']
            prev_s = scores[i-1]['total_score']
            if cur_s is not None and prev_s is not None and cur_s < prev_s:
                consec_decline += 1
            else:
                break

        if consec_decline >= 2:
            st.warning(f"连续 {consec_decline} 次成绩下降！")
        elif consec_decline >= 1:
            st.info(f"最近 1 次成绩下降")
        else:
            if p and p['total_score'] and c['total_score'] >= p['total_score']:
                st.success("状态稳定/上升")
    else:
        st.info("暂无有效成绩数据")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 智能分析评语 ──
    analysis = analyze_student_trend(scores)
    if analysis.get('comment'):
        comments = analysis['comment'].split('\n')
        st.markdown(f'<div class="card"><b>{analysis["tag"]} 综合分析</b>', unsafe_allow_html=True)
        for line in comments:
            st.markdown(line)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── 年级排名趋势 ──
    has_grade_rank = any(s['grade_rank'] is not None for s in scores)
    if has_grade_rank:
        st.markdown('<div class="card"><b>🏆 年级排名趋势</b>', unsafe_allow_html=True)

        fig_rank = go.Figure()
        rank_x = []
        rank_y = []

        for i, s in enumerate(scores):
            if s['is_absent'] or s['grade_rank'] is None:
                continue
            d = str(s['exam_date'])
            label = f"{s['exam_name']}<br>{d[5:10]}" if len(d) >= 10 else s['exam_name']
            rank_x.append(label)
            rank_y.append(s['grade_rank'])

        if rank_y:
            rank_text = [f'第{r}名' for r in rank_y]
            fig_rank.add_trace(go.Scatter(
                x=rank_x, y=rank_y,
                mode='lines+markers+text',
                name='年级排名',
                line=dict(color='#8b5cf6', width=2.5),
                marker=dict(size=9, color='#8b5cf6'),
                text=rank_text,
                textposition='top center',
                textfont=dict(size=11, color='#8b5cf6'),
                hovertemplate='%{x}<br>年级排名: 第%{y}名<extra></extra>',
            ))
            # 排名 Y 轴倒置（排名越小越靠前，应该在图表上方）
            fig_rank.update_layout(
                xaxis_title="考试",
                yaxis_title="年级排名",
                yaxis=dict(
                    autorange='reversed',
                    tickmode='linear',
                    dtick=max(1, (max(rank_y) - min(rank_y)) // 5) if len(rank_y) > 1 and (max(rank_y) - min(rank_y)) > 5 else 1,
                ),
                xaxis=dict(type='category'),
                height=350,
                hovermode='x unified',
                margin=dict(l=20, r=20, t=20, b=40)
            )
            st.plotly_chart(fig_rank, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── 客观题 vs 主观题趋势（仅新教育平台数据） ──
    has_obj_subj = any(s['objective_score'] is not None for s in scores)
    if has_obj_subj:
        st.markdown('<div class="card"><b>🎯 选择题 vs 填空题 得分率趋势</b>', unsafe_allow_html=True)

        fig_os = go.Figure()

        obj_x = []
        obj_y = []
        subj_x = []
        subj_y = []

        for i, s in enumerate(scores):
            if s['is_absent']:
                continue
            d = str(s['exam_date'])
            label = f"{s['exam_name']}<br>{d[5:10]}" if len(d) >= 10 else s['exam_name']
            if s['objective_score'] is not None:
                obj_x.append(label)
                obj_y.append(s['objective_score'])
            if s['subjective_score'] is not None:
                subj_x.append(label)
                subj_y.append(s['subjective_score'])

        if obj_y:
            obj_text = [f'{v}分' for v in obj_y]
            fig_os.add_trace(go.Scatter(
                x=obj_x, y=obj_y,
                mode='lines+markers+text',
                name='选择题',
                line=dict(color='#2ca02c', width=2),
                marker=dict(size=8),
                text=obj_text,
                textposition='top center',
                textfont=dict(size=10, color='#2ca02c'),
            ))
        if subj_y:
            subj_text = [f'{v}分' for v in subj_y]
            fig_os.add_trace(go.Scatter(
                x=subj_x, y=subj_y,
                mode='lines+markers+text',
                name='填空题',
                line=dict(color='#d62728', width=2),
                marker=dict(size=8),
                text=subj_text,
                textposition='top center',
                textfont=dict(size=10, color='#d62728'),
            ))

        fig_os.update_layout(
            xaxis_title="考试",
            yaxis_title="得分",
            yaxis=dict(range=[0, 55]),
            height=350,
            hovermode='x unified',
            margin=dict(l=20, r=20, t=20, b=40)
        )
        st.plotly_chart(fig_os, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── 历次成绩明细表 ──
    st.markdown('<div class="card"><b>📋 历次成绩明细</b>', unsafe_allow_html=True)

    detail_rows = []
    for s in scores:
        if s['is_absent']:
            detail_rows.append({
                '考试': s['exam_name'],
                '日期': s['exam_date'],
                '得分': '缺考',
                '选择题': '-',
                '填空题': '-',
                '班级排名': '-',
                '年级排名': '-',
            })
        else:
            detail_rows.append({
                '考试': s['exam_name'],
                '日期': s['exam_date'],
                '得分': s['total_score'],
                '选择题': s['objective_score'] if s['objective_score'] is not None else '-',
                '填空题': s['subjective_score'] if s['subjective_score'] is not None else '-',
                '班级排名': s['class_rank'] if s['class_rank'] else '-',
                '年级排名': s['grade_rank'] if s['grade_rank'] else '-',
            })

    st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 导出成绩报告 ──
    report_lines = [f"【{name}】化学成绩报告", f"班级：{class_name}", f"导出日期：{date.today()}", ""]
    report_lines.append("=" * 60)
    report_lines.append(f"{'考试名称':<20} {'日期':<12} {'得分':<6} {'选择题':<6} {'填空题':<6} {'班排':<4} {'年排':<4}")
    report_lines.append("=" * 60)
    for s in scores:
        if s['is_absent']:
            report_lines.append(f"{s['exam_name']:<20} {str(s['exam_date']):<12} {'缺考':<6}")
        else:
            obj = f"{s['objective_score']:.0f}" if s['objective_score'] is not None else '-'
            subj = f"{s['subjective_score']:.0f}" if s['subjective_score'] is not None else '-'
            cr = str(s['class_rank']) if s['class_rank'] else '-'
            gr = str(s['grade_rank']) if s['grade_rank'] else '-'
            report_lines.append(f"{s['exam_name']:<20} {str(s['exam_date']):<12} {s['total_score']:<6.0f} {obj:<6} {subj:<6} {cr:<4} {gr:<4}")

    if trend and trend['total']:
        avg = round(sum(t for t in trend['total'] if t is not None) / len([t for t in trend['total'] if t is not None]), 1)
        report_lines.extend(["", "─" * 40, f"平均分：{avg}", f"考试次数：{len(trend['total'])}"])
    report_text = "\n".join(report_lines)

    st.download_button(
        "📤 导出成绩报告",
        data=report_text,
        file_name=f"{name}_成绩报告.txt",
        mime="text/plain",
        use_container_width=True,
    )


# ════════════════════════════════════════════════
# 页面：班级分析
# ════════════════════════════════════════════════
def render_class_overview():
    st.markdown('<div class="app-header"><span>📉</span><h1>班级进退步分析</h1></div>', unsafe_allow_html=True)

    if st.button("← 返回首页"):
        st.session_state.page = 'home'
        st.rerun()

    conn = get_conn()
    all_classes = [r['class_name'] for r in conn.execute(
        "SELECT DISTINCT class_name FROM scores WHERE is_absent=0 ORDER BY class_name"
    ).fetchall()]
    conn.close()

    if not all_classes:
        st.info("还没有班级数据")
        return

    exams = get_exams()
    if not exams:
        st.info("还没有考试数据")
        return
    exam_labels = list(dict.fromkeys([f'{e["name"]}（{e["exam_date"]}）' for e in exams]))

    col_a, col_b = st.columns(2)
    with col_a:
        sel_cls = st.selectbox("选择班级", all_classes)
    with col_b:
        sel_exam_label = st.selectbox("选择考试", exam_labels)

    sel_date = sel_exam_label.split('（')[1].rstrip('）')

    # 找到该班级在所选日期的考试 ID
    conn = get_conn()
    cls_exam = conn.execute("""
        SELECT e.id FROM exams e
        JOIN scores s ON s.exam_id = e.id
        WHERE e.exam_date = ? AND s.class_name = ? AND s.is_absent = 0
        LIMIT 1
    """, (sel_date, sel_cls)).fetchone()
    if not cls_exam:
        st.warning(f"{sel_cls}班 在该日没有考试数据")
        conn.close()
        return
    exam_id = cls_exam['id']

    # 获取对比数据
    data = get_class_comparison(exam_id, sel_cls, conn)
    conn.close()

    if not data:
        st.info("暂无对比数据")
        return

    current = data['current_exam']
    prev = data['prev_exam']
    decliners = data['big_decliners']
    improvers = data['big_improvers']
    consec = data['consec_declines']
    stats = data['class_stats']
    prev_stats = data['prev_class_stats']
    rows = data['detail_rows']

    prev_label = f'上次：{prev["name"]}（{prev["exam_date"]}）' if prev else "首次考试无对比"
    compare_label = f'  ← 对比 {prev["name"]}' if prev else ''
    st.markdown(f'<div class="card"><b>📊 {sel_cls}班 · {current["name"]}</b>{compare_label}', unsafe_allow_html=True)
    st.markdown(f'参考人数：{data["student_count"]} 人　{prev_label}')
    st.markdown('</div>', unsafe_allow_html=True)

    # ⚠️ 退步明显 + 🔥 进步明显 并排
    col_l, col_r = st.columns(2)
    with col_l:
        if decliners:
            st.markdown(f'<div class="card card-warn"><b>⚠️ 退步明显（降 ≥ 10 分）</b> — {len(decliners)} 人', unsafe_allow_html=True)
            for d in decliners:
                st.markdown(f'<div class="decline-row"><span class="name">🔻 {d["student_name"]}</span><span class="rank">{d["current_score"]}分</span><span class="arrow" style="color:#dc2626">↓{abs(d["score_diff"]):.0f}</span><span class="rank">班级排名 {d["prev_rank"]} → {d["current_rank"]}{" （↓"+str(abs(d["rank_diff"]))+"名）" if d["rank_diff"] and d["rank_diff"] < 0 else ""}</span></div>', unsafe_allow_html=True)
                if st.button(f"查看 {d['student_name']}", key=f"cd_{d['student_name']}", use_container_width=True):
                    st.session_state.selected_student = d['student_name']; st.session_state.page = 'student'; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    with col_r:
        if improvers:
            st.markdown(f'<div class="card card-good"><b>🔥 进步明显（升 ≥ 10 分）</b> — {len(improvers)} 人', unsafe_allow_html=True)
            for d in improvers:
                st.markdown(f'<div class="decline-row"><span class="name" style="color:#16a34a">🔥 {d["student_name"]}</span><span class="rank">{d["current_score"]}分</span><span class="arrow" style="color:#16a34a">↑{d["score_diff"]:.0f}</span><span class="rank">班级排名 {d["prev_rank"]} → {d["current_rank"]}{" （↑"+str(d["rank_diff"])+"名）" if d["rank_diff"] and d["rank_diff"] > 0 else ""}</span></div>', unsafe_allow_html=True)
                if st.button(f"查看 {d['student_name']}", key=f"up_{d['student_name']}", use_container_width=True):
                    st.session_state.selected_student = d['student_name']; st.session_state.page = 'student'; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # 🔄 连续退步
    if consec:
        st.markdown(f'<div class="card card-warn"><b>🔄 连续退步预警（≥2次）</b>', unsafe_allow_html=True)
        for c in consec:
            st.markdown(f'<div class="decline-row"><span class="name">🔻 {c["student_name"]}</span><span class="rank">最近 {c["consec_declines"]} 次连续下降</span><span class="arrow" style="color:#dc2626">{c["latest_score"]}分</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 🎯 全班统计
    if stats:
        st.markdown('<div class="card"><b>🎯 全班成绩统计</b>', unsafe_allow_html=True)
        ms1, ms2, ms3, ms4 = st.columns(4)
        with ms1: st.markdown(f'<div class="metric-box blue"><div class="num">{stats["avg"]}</div><div class="label">平均分</div></div>', unsafe_allow_html=True)
        with ms2: st.markdown(f'<div class="metric-box blue"><div class="num">{stats["pass_rate"]}%</div><div class="label">及格率</div></div>', unsafe_allow_html=True)
        with ms3: st.markdown(f'<div class="metric-box blue"><div class="num">{stats["excellent_rate"]}%</div><div class="label">优秀率</div></div>', unsafe_allow_html=True)
        with ms4:
            diff = (stats['avg'] - prev_stats['avg']) if prev_stats and prev_stats.get('avg') else None
            if diff is not None:
                st.markdown(f'<div class="metric-box {"green" if diff>=0 else "red"}"><div class="num">{diff:+.1f}</div><div class="label">较上次</div></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="metric-box blue"><div class="num">-</div><div class="label">较上次</div></div>', unsafe_allow_html=True)

        # 分数段分布
        st.markdown('---<b>📊 分数段分布</b>', unsafe_allow_html=True)
        ranges = [('90-100',90,101),('80-89',80,90),('70-79',70,80),('60-69',60,70),('<60',0,60)]
        counts = {}
        valid_scores = [s['current_score'] for s in rows if s.get('current_score')]
        for label, lo, hi in ranges:
            counts[label] = sum(1 for sc in valid_scores if lo <= sc < hi)
        if valid_scores:
            st.plotly_chart(go.Figure(data=[go.Bar(x=list(counts.keys()), y=list(counts.values()), text=list(counts.values()), textposition='outside', marker_color=['#22c55e','#86efac','#fde047','#f97316','#ef4444'])]).update_layout(height=300, margin=dict(l=20,r=20,t=20,b=40), yaxis=dict(tickmode='linear', dtick=1)), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 全班明细表
    if rows:
        st.markdown('<div class="card"><b>📋 全班明细表</b>', unsafe_allow_html=True)
        detail_df = pd.DataFrame([{'排名': r.get('current_rank',''),'姓名': r['student_name'],'上次': f"{r['prev_score']:.0f}" if r['prev_score'] is not None else '-','本次': f"{r['current_score']:.0f}",'±分': f"{r['score_diff']:+.0f}" if r['score_diff'] is not None else '-','上次排名': r['prev_rank'] if r['prev_rank'] else '-','±排名': f"{r['rank_diff']:+d}" if r['rank_diff'] is not None else '-'} for r in rows])
        st.dataframe(detail_df, use_container_width=True, hide_index=True, height=400)
        csv_data = detail_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button("📤 导出全班数据（CSV）", data=csv_data, file_name=f"{sel_cls}班_{current['name']}_成绩明细.csv", mime="text/csv", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

def analyze_student_trend(scores):
    """综合分析学生历次成绩趋势，生成评语"""
    valid = [s for s in scores if not s['is_absent'] and s['total_score'] is not None]
    if len(valid) < 2:
        return {'tag': '📊', 'comment': '数据不足，至少需要 2 次有效成绩才能分析趋势。', 'details': {}}

    n = len(valid)
    scores_list = [s['total_score'] for s in valid]
    avg_score = round(sum(scores_list) / n, 1)
    max_score = max(scores_list)
    min_score = min(scores_list)

    # 总体趋势（线性回归斜率）
    xs = list(range(n))
    mean_x = (n - 1) / 2
    mean_y = avg_score
    num = sum((x - mean_x) * (scores_list[x] - mean_y) for x in xs)
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = round(num / den, 2) if den != 0 else 0

    # 波动性
    variance = sum((s - avg_score) ** 2 for s in scores_list) / n
    std_dev = round(variance ** 0.5, 1)

    # 最近趋势
    if n >= 3:
        recent_3 = scores_list[-3:]
        before = scores_list[:3] if n >= 6 else scores_list[:n-3]
        recent_avg = round(sum(recent_3) / 3, 1)
        before_avg = round(sum(before) / len(before), 1) if before else recent_avg
        recent_diff = round(recent_avg - before_avg, 1)
    else:
        recent_diff = round(scores_list[-1] - scores_list[0], 1)

    # 等级
    def level(s):
        if s >= 90: return '优秀'
        if s >= 80: return '良好'
        if s >= 70: return '中等'
        if s >= 60: return '及格'
        return '待提升'
    current_level = level(scores_list[-1])

    # 排名趋势
    rank_trend = None
    rank_scores = [s for s in valid if s['class_rank'] is not None]
    if len(rank_scores) >= 2:
        rd = rank_scores[0]['class_rank'] - rank_scores[-1]['class_rank']
        rank_trend = f'进步了 {rd} 名' if rd > 0 else (f'退步了 {abs(rd)} 名' if rd < 0 else '排名稳定')

    # 客观/主观
    obj_subj_comment = None
    obj_scores = [s['objective_score'] for s in valid if s['objective_score'] is not None]
    subj_scores = [s['subjective_score'] for s in valid if s['subjective_score'] is not None]
    if obj_scores and subj_scores and len(obj_scores) >= 2:
        obj_avg = round(sum(obj_scores) / len(obj_scores), 1)
        subj_avg = round(sum(subj_scores) / len(subj_scores), 1)
        obj_rate = round(obj_avg / 50 * 100)
        subj_rate = round(subj_avg / 50 * 100)
        if obj_rate - subj_rate > 15:
            obj_subj_comment = f'选择题比填空题强（{obj_rate}% vs {subj_rate}%），建议加强主观题训练'
        elif subj_rate - obj_rate > 15:
            obj_subj_comment = f'填空题比选择题强（{subj_rate}% vs {obj_rate}%），选择题还有提升空间'
        else:
            obj_subj_comment = f'选择题和填空题发展均衡（{obj_rate}% / {subj_rate}%）'

    # 连续升降
    consec_up = consec_down = 0
    for i in range(n - 1, 0, -1):
        d = scores_list[i] - scores_list[i - 1]
        if d > 0: consec_up += 1; consec_down = 0
        elif d < 0: consec_down += 1; consec_up = 0
        else: break

    # 生成分析（老师视角：我该怎么做）
    parts = []

    # 总体趋势
    if slope > 1.5:
        parts.append(f'📈 该生成绩一直在进步，我应多鼓励，让他保持势头。')
    elif slope > 0.5:
        parts.append(f'📈 该生成绩总体在往上走，我应趁热打铁，再推他一把。')
    elif slope > -0.5:
        parts.append(f'➡️ 该生成绩总体平稳，我可以帮他找找突破口，稳中求进。')
    elif slope > -1.5:
        parts.append(f'📉 该生最近成绩有所下滑，我需要找他聊聊，看看问题出在哪。')
    else:
        parts.append(f'📉 该生成绩下滑比较明显，我必须认真对待了，得和家长沟通一下。')

    # 当前水平
    if current_level == '优秀':
        parts.append(f'🏆 目前优秀（{scores_list[-1]}分），我应提醒他不要骄傲，继续保持。')
    elif current_level == '良好':
        target = round(90 - scores_list[-1])
        parts.append(f'👍 目前良好（{scores_list[-1]}分），离优秀只差 {target} 分，我可以重点点拨一下他的薄弱环节。')
    elif current_level == '中等':
        target = round(80 - scores_list[-1])
        parts.append(f'💪 目前中等（{scores_list[-1]}分），还差 {target} 分到良好，我应多关注他的作业和课堂表现。')
    elif current_level == '及格':
        parts.append(f'⚠️ 目前刚及格（{scores_list[-1]}分），我需要多盯着点，别让他掉下去。')
    else:
        parts.append(f'🔴 目前分数偏低（{scores_list[-1]}分），我得重点辅导，看看到底是哪里没跟上。')

    # 波动性
    if std_dev > 10:
        parts.append(f'📊 该生成绩波动较大，我需要关注他的学习状态和考试心态。')
    elif std_dev > 5:
        parts.append(f'📊 该生成绩有些小波动，我可以帮他巩固基础，减少起伏。')
    else:
        parts.append(f'📊 该生成绩稳定，这是好事，我可以在此基础上帮他提升。')

    # 近期趋势
    if n >= 3:
        if recent_diff > 5:
            parts.append(f'🔥 近期进步明显，比之前平均高了 {recent_diff} 分，我的方法对他有效，继续坚持。')
        elif recent_diff > 0:
            parts.append(f'📈 近期略有进步，高了 {recent_diff} 分，积少成多，值得肯定。')
        elif recent_diff > -5:
            parts.append(f'📉 近期稍微下滑了一点，我应提醒他调整状态，不用太着急。')
        else:
            parts.append(f'⚠️ 近期下滑了 {abs(recent_diff)} 分，幅度不小，我需要介入干预了。')

    # 连续升降
    if consec_down >= 2:
        parts.append(f'⚠️ 已经连续 {consec_down} 次下降，我该找他谈谈，看看是不是遇到了什么困难。')
    if consec_up >= 2:
        parts.append(f'🔥 连续 {consec_up} 次进步，我的辅导有效果，继续保持这个节奏。')

    # 排名
    if rank_trend:
        parts.append(f'🏅 班级排名{rank_trend}，我要根据这个调整对他的关注力度。')

    # 客观/主观
    if obj_subj_comment:
        parts.append(f'🎯 {obj_subj_comment}，我可以针对性地给他布置练习。')

    # 高低分差
    if max_score - min_score > 20:
        parts.append(f'📉 最高 {max_score} 分、最低 {min_score} 分，差了 {max_score - min_score} 分，发挥太不稳定了，我需要帮他找到稳定发挥的方法。')
    elif max_score - min_score > 10:
        parts.append(f'📊 最高 {max_score} 分、最低 {min_score} 分，还有提升空间，我可以帮他把底线往上拉一拉。')

    # 标签
    if current_level == '优秀' and slope > 0: tag = '🌟 优等生'
    elif consec_down >= 2: tag = '⚠️ 需关注'
    elif slope > 1: tag = '🚀 进步之星'
    elif slope < -1: tag = '📉 需要加油'
    elif current_level in ('优秀', '良好') and std_dev < 5: tag = '✅ 稳定优秀'
    elif current_level in ('良好', '中等') and slope > 0: tag = '📈 稳步提升'
    else: tag = f'📊 {current_level}'

    return {'tag': tag, 'comment': '\n'.join(parts)}


# ════════════════════════════════════════════════
# 路由
# ════════════════════════════════════════════════
if st.session_state.page == 'home':
    render_home()
elif st.session_state.page == 'import':
    render_import()
elif st.session_state.page == 'student':
    render_student()
elif st.session_state.page == 'class_overview':
    render_class_overview()
else:
    render_home()
