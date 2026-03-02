"""
LitSearch Streamlit 入口（包装文件）
实际代码在 src/streamlit_app.py
"""
import sys
import os

# 将 src/ 加入模块搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

# 直接执行 src/streamlit_app.py
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "streamlit_app.py"), encoding="utf-8").read())
