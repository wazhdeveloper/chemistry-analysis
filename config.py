"""配置"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'grades.db')
FULL_SCORE = 100  # 化学满分固定100分

# 两种平台的列名特征（用于自动识别）
XINJIAOYU_COLUMNS = ['学号', '总得分', '客观题得分']
ZHIXUEWANG_COLUMNS = ['准考证号', '得分', '班名']
