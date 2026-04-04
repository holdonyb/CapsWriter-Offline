# coding: utf-8
"""
开机自启动管理 (Windows)

通过注册表 HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run 实现。
支持 .exe (PyInstaller) 和 python script 两种运行方式。
"""

import sys
import os

APP_NAME = 'CapsWriter'
REG_PATH = r'Software\Microsoft\Windows\CurrentVersion\Run'


def _get_launch_command() -> str:
    """获取启动命令：frozen exe 用自身路径，否则用 python + script"""
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}"'
    else:
        script = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', '..', 'core_client.py'
        ))
        return f'"{sys.executable}" "{script}"'


def is_auto_start_enabled() -> bool:
    """检查当前是否已设置开机自启"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


def set_auto_start(enable: bool) -> bool:
    """设置或取消开机自启。返回是否成功。"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0,
                             winreg.KEY_SET_VALUE)
        try:
            if enable:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ,
                                  _get_launch_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
            return True
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False
