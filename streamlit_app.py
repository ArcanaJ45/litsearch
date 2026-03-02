"""
LitSearch Streamlit 入口（包装文件）
实际代码在 src/streamlit_app.py
"""
import sys
import os
import runpy

# 将 src/ 加入模块搜索路径
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
sys.path.insert(0, src_dir)

# 以 run_path 方式执行，正确设置 __file__ 为 src/streamlit_app.py
runpy.run_path(os.path.join(src_dir, "streamlit_app.py"), run_name="__main__")
