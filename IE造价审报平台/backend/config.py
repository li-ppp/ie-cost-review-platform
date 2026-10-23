"""
应用配置 - 路径管理
支持开发模式和 PyInstaller 打包模式
"""
import os
import sys


def is_frozen():
    return getattr(sys, 'frozen', False)


def get_base_dir():
    """可写目录：exe 所在目录（打包）或 backend 的上级（开发）"""
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_resources_dir():
    """资源根目录：_MEIPASS（打包）或项目根目录（开发）"""
    if is_frozen():
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = get_base_dir()
RESOURCES_DIR = get_resources_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
