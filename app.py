"""化学成绩分析系统 - Streamlit 主程序"""
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
    normalize_class_name, get_top_decliners
)
from database import get_conn

# ── 页面配置 ──
st.set_page_config(page_title="化学成绩分析", page_icon="📊", layout="wide")

# ── 自定义样式 ──
st.markdown("""
<style>
    /* 整体色调 */
    .stApp { background: #f5f7fb; }

    .main > div { padding: 0 0.5rem; }

    /* ✕ 删除按钮：红色文字，无框，跟旁边对齐 */
    button[kind="tertiary"],
    button[data-testid="baseButton-tertiary"] {
        color: #dc2626 !important;
        background: none !important;
        border: none !important;
        box-shadow: none !important;
        font-size: inherit !important;
        padding: 2px 0 0 4px !important;
        min-width: auto !important;
        min-height: auto !important;
        height: auto !important;
        line-height: inherit !important;
    }

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

    col1, col2 = st.columns([7, 3])
    with col1:
        exams = get_exams()
        if exams:
            st.markdown(f'<div class="card"><b>📋 考试记录</b>（共 {len(exams)} 次）', unsafe_allow_html=True)
            for e in exams:
                c1, c2, c3 = st.columns([5, 4, 1])
                with c1:
                    st.markdown(f'<b>{e["name"]}</b>', unsafe_allow_html=True)
                with c2:
                    st.markdown(f'📅 {e["exam_date"]}　👥 {e["student_count"]} 人', unsafe_allow_html=True)
                with c3:
                    if st.button("删除", key=f"del_{e['id']}", help="删除本次考试", type="tertiary"):
                        delete_exam(e['id'])
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="card">📭 还没有考试数据，点击左侧「导入新成绩」开始吧！</div>', unsafe_allow_html=True)

        # ⚠️ 退步预警
        if exams:
            latest = get_exams()[0]
            conn = get_conn()
            decliners = get_top_decliners(latest['id'], conn)
            conn.close()
            if decliners:
                st.markdown(f'<div class="card card-warn"><b>⚠️ 退步预警</b> — 「{latest["name"]}」各班名次退步最大前五名', unsafe_allow_html=True)
                for cls_name in sorted(decliners.keys(), key=lambda x: int(x) if x.isdigit() else x):
                    students = decliners[cls_name]
                    st.markdown(f'<b style="color:#92400e">🏫 {cls_name}班</b>', unsafe_allow_html=True)
                    for s in students:
                        st.markdown(
                            f'<div class="decline-row">'
                            f'<span class="name">🔻 {s["student_name"]}</span>'
                            f'<span class="rank">{s["prev_rank"]}名 → {s["current_rank"]}名</span>'
                            f'<span class="arrow">↓{s["rank_diff"]}名</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                        if st.button(f"查看 {s['student_name']}", key=f"d_{s['student_name']}_{latest['id']}", use_container_width=True):
                            st.session_state.selected_student = s['student_name']
                            st.session_state.page = 'student'
                            st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

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
            exam_name = st.text_input("考试名称", placeholder="如：6.2限时练习")
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
    # 横轴：用考试名+月份-日期，明确转成字符串防 Plotly 误判为日期
    x_labels = []
    for s in scores:
        d = str(s['exam_date'])
        if len(d) >= 10:
            label = f"{s['exam_name']}（{d[5:10]}）"
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
            label = f"{s['exam_name']}（{d[5:10]}）" if len(d) >= 10 else s['exam_name']
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
            label = f"{s['exam_name']}（{d[5:10]}）" if len(d) >= 10 else s['exam_name']
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


# ════════════════════════════════════════════════
# 路由
# ════════════════════════════════════════════════
if st.session_state.page == 'home':
    render_home()
elif st.session_state.page == 'import':
    render_import()
elif st.session_state.page == 'student':
    render_student()
else:
    render_home()
