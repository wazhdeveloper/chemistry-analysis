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
    st.title("📊 化学成绩分析")

    # 导入成功提示
    if st.session_state.import_success:
        st.success(st.session_state.import_success)
        st.session_state.import_success = None

    col1, col2 = st.columns([3, 1])
    with col1:
        exams = get_exams()
        if exams:
            st.markdown(f"**📋 已有考试数据（共 {len(exams)} 次）**")
            for e in exams:
                cols = st.columns([4, 1, 1, 0.5])
                with cols[0]:
                    st.write(f"📄 **{e['name']}**")
                with cols[1]:
                    st.write(f"📅 {e['exam_date']}")
                with cols[2]:
                    st.write(f"👥 {e['student_count']} 人")
                with cols[3]:
                    if st.button("🗑", key=f"del_{e['id']}", help="删除本次考试"):
                        delete_exam(e['id'])
                        st.rerun()
                st.divider()
        else:
            st.info("还没有考试数据，点击左侧「导入新成绩」开始吧！")

    # ⚠️ 最近一次考试各班退步前五名
    if exams:
        latest = get_exams()[0]
        conn = get_conn()
        decliners = get_top_decliners(latest['id'], conn)
        conn.close()
        if decliners:
            st.markdown("---")
            st.markdown(f"**⚠「{latest['name']}」各班名次退步最大前五名**")
            for cls_name in sorted(decliners.keys(), key=lambda x: int(x) if x.isdigit() else x):
                students = decliners[cls_name]
                with st.expander(f"🏫 {cls_name}班（{len(students)} 人）", expanded=True):
                    for s in students:
                        col_a, col_b, col_c = st.columns([2, 2, 2])
                        with col_a:
                            if st.button(f"🔻{s['student_name']}", key=f"d_{s['student_name']}_{latest['id']}", help="点击查看详情"):
                                st.session_state.selected_student = s['student_name']
                                st.session_state.page = 'student'
                                st.rerun()
                        with col_b:
                            st.markdown(f"{s['prev_rank']}名 → {s['current_rank']}名")
                        with col_c:
                            st.markdown(f"<span style='color:red'>**↓{s['rank_diff']}**</span> 名", unsafe_allow_html=True)

    with col2:
        st.markdown("**🔍 搜索学生**")
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

    # 全部学生快捷入口
    st.markdown("---")
    st.markdown("**👥 全部学生**")
    all_students = get_all_students()
    # 分组显示（按班级）
    classes = {}
    for s in all_students:
        cls = s['class_name']
        if cls not in classes:
            classes[cls] = []
        classes[cls].append(s['student_name'])

    for cls_name in sorted(classes.keys(), key=lambda x: int(x) if x.isdigit() else x):
        with st.expander(f"🏫 {cls_name}班（{len(classes[cls_name])} 人）"):
            for name in sorted(classes[cls_name]):
                if st.button(f"👤 {name}", key=f"student_{name}", use_container_width=True):
                    st.session_state.selected_student = name
                    st.session_state.page = 'student'
                    st.rerun()


# ════════════════════════════════════════════════
# 页面：导入
# ════════════════════════════════════════════════
def render_import():
    st.title("📥 导入新成绩")

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

        st.info(f"共识别 **{total}** 名学生，其中缺考 **{absent}** 人，有效成绩 **{valid}** 人")

        # 显示预览
        preview_df = pd.DataFrame([{
            '姓名': s['student_name'],
            '班级': s['class_name'],
            '得分': s['total_score'] if not s['is_absent'] else '缺考',
            '班级排名': s['class_rank'] if s.get('class_rank') else '',
            '年级排名': s['grade_rank'] if s.get('grade_rank') else '',
        } for s in scores[:20]])

        st.markdown(f"**📋 数据预览（前 20 条）**")
        st.dataframe(preview_df, use_container_width=True, hide_index=True)

        # 考试信息
        st.markdown("---")
        st.markdown("**📋 考试信息**")

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
    st.title(f"👤 {name} · {class_name}班")

    # 返回按钮
    if st.button("← 返回首页"):
        st.session_state.page = 'home'
        st.session_state.selected_student = None
        st.rerun()

    # 计算趋势数据
    trend = calc_trend_data(scores)

    # ── 总分趋势图 ──
    st.markdown("---")
    st.subheader("📈 化学总分趋势")

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
    if len(valid_y) >= 2:
        fig_total.add_trace(go.Scatter(
            x=valid_x, y=valid_y,
            mode='lines+markers',
            name='总分',
            line=dict(color='#1f77b4', width=2.5),
            marker=dict(size=10, color='#1f77b4'),
            text=valid_text,
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

    # ── 进退步分析 ──
    st.markdown("---")
    st.subheader("📉 进退步分析")

    # 本次成绩（最近一次非缺考）
    current = None
    previous = None
    for s in reversed(scores):
        if not s['is_absent']:
            if current is None:
                current = s
            elif previous is None:
                previous = s
            break
    # 找上次成绩（再往前一次）
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

        col1, col2, col3 = st.columns(3)
        with col1:
            cur_score = current['total_score']
            st.metric("本次得分", f"{cur_score} 分")
        with col2:
            if p and p['total_score']:
                diff = round(c['total_score'] - p['total_score'], 1)
                delta = f"{diff:+.1f}"
                st.metric("与上次对比", f"{p['total_score']} 分 → {cur_score} 分", delta=delta)
            else:
                st.metric("与上次对比", "首次考试，无对比")
        with col3:
            if c['class_rank']:
                if p and p['class_rank']:
                    rank_diff = p['class_rank'] - c['class_rank']
                    delta = f"{rank_diff:+d}" if rank_diff != 0 else "持平"
                    st.metric("班级排名", f"第 {c['class_rank']} 名", delta=delta)
                else:
                    st.metric("班级排名", f"第 {c['class_rank']} 名")
            else:
                st.metric("班级排名", "暂缺")

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
            st.warning(f"⚠️ 连续 **{consec_decline}** 次成绩下降！")
        elif consec_decline >= 1:
            st.info(f"📉 最近 1 次成绩下降")
        else:
            if p and p['total_score'] and c['total_score'] >= p['total_score']:
                st.success("✅ 状态稳定/上升")
    else:
        st.info("暂无有效成绩数据")

    # ── 客观题 vs 主观题趋势（仅新教育平台数据） ──
    has_obj_subj = any(s['objective_score'] is not None for s in scores)
    if has_obj_subj:
        st.markdown("---")
        st.subheader("🎯 选择题 vs 填空题 得分率趋势")

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
            fig_os.add_trace(go.Scatter(
                x=obj_x, y=obj_y,
                mode='lines+markers',
                name='选择题',
                line=dict(color='#2ca02c', width=2),
                marker=dict(size=8),
            ))
        if subj_y:
            fig_os.add_trace(go.Scatter(
                x=subj_x, y=subj_y,
                mode='lines+markers',
                name='填空题',
                line=dict(color='#d62728', width=2),
                marker=dict(size=8),
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

    # ── 历次成绩明细表 ──
    st.markdown("---")
    st.subheader("📋 历次成绩明细")

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
