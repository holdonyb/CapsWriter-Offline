# coding: utf-8
"""
提示信息显示模块

提供 TipsDisplay 类用于显示启动提示信息。
"""

from __future__ import annotations

import os

from rich.markdown import Markdown

from util.client.state import console
from config_client import ClientConfig as Config, __version__
from . import logger



def _format_shortcut_name(key: str) -> str:
    """
    格式化快捷键名称用于显示

    Args:
        key: 快捷键名称（如 'caps_lock', 'f12'）

    Returns:
        str: 格式化后的名称（如 'CapsLock', 'F12'）
    """
    # 将下划线替换为空格，然后标题化
    return key.replace('_', ' ').title()


def _get_shortcuts_display() -> str:
    """
    获取所有启用快捷键的显示字符串

    Returns:
        str: 格式化的快捷键列表，用逗号分隔
    """
    enabled_shortcuts = [sc for sc in Config.shortcuts if sc.get('enabled', True)]
    if not enabled_shortcuts:
        return '未配置快捷键'

    # 格式化每个快捷键名称
    formatted = [_format_shortcut_name(sc['key']) for sc in enabled_shortcuts]
    return '、'.join(formatted)


class TipsDisplay:
    """
    提示信息显示器
    
    显示客户端启动时的提示信息。
    """
    
    @staticmethod
    def show_mic_tips() -> None:
        """显示麦克风模式的启动提示"""
        shortcuts_display = _get_shortcuts_display()

        console.rule('[bold #d55252]CapsWriter Offline Client')
        console.print(f'\n版本：[bold green]{__version__}')

        markdown = f'''

项目地址：https://github.com/HaujetZhao/CapsWriter-Offline

**CapsWriter-Offline** 是一个专为 Windows 打造的**完全离线**语音输入工具。

使用步骤：

1. 运行 **Server** 端，它作为「大脑」负责 AI 推理，约占用 1.5G 内存。
2. 运行 **Client** 端，它作为「耳朵」负责听音和打字上屏。
3. 按住快捷键（`{shortcuts_display}`）说话，松开即输入。
4. 将音视频文件拖动到 **Client** 端 exe 文件后松开，可转录生成字幕。


特性：

1. **快、准、稳**：完全离线运行，响应极快，支持自动标点、数字 ITN 和中英间距调整。
2. **热词系统**：支持 `hot.txt` 音素级模糊匹配，准确替换专业术语，支持中英。
3. **正则替换**：支持 `hot-rule.txt` 强制替换规则。
4. **LLM 助手**：支持调用大语言模型，用于润色、翻译、格式化、代码助手等角色，可配置读取选中文字。
5. **日记归档**：自动归档每日语音记录及其识别结果。
6. **托盘管理**：右键托盘图标可快速切换模型、修改配置、查看日志或隐藏黑窗口。
7. **语音清理**：自动去除填充词（嗯/啊/呃）、重复词语、识别自我纠正。
8. **应用感知**：LLM 根据当前活跃窗口自动调整输出语调（微信/邮件/代码编辑器等）。


语音命令（说完后自动触发）：

| 命令 | 效果 |
|------|------|
| `退格` / `删除N次` | 退格删除 |
| `删除XXXX` | 从最近输出中删掉指定词 |
| `全选` | Ctrl+A |
| `上` / `下` / `左` / `右` | 方向键（支持N次，如"右3次"） |
| `Ctrl左` / `Alt右` / `Shift上` | 组合键+方向键 |
| `行首` / `行尾` | Home / End |
| `撤销` / `重做` | Ctrl+Z / Ctrl+Y |
| `切换窗口` | Alt+Tab（保持Alt，上下左右选，说"确定"） |
| `把X换成Y` | 替换最近输出中的词 |
| `润色前文` / `把前面改得更...` | LLM 润色最近输出 |
| `润色最近N次输入` | 润色最近 N 次内容 |
| `问一下 <问题>` | 基于选中文字提问（Toast 显示） |
| `总结一下` / `解释一下` / `翻译一下` | 对选中文字操作（Toast 显示） |
| `格式化` | 整理成 Markdown 结构 |
| `点击 <按钮名>` | 语音点击 UI 元素 |
| `搜索 <内容>` | 浏览器搜索 |
| `打开 <应用名>` | 启动应用 |
| `截图` | Win+Shift+S |


注意事项：

1. 当前快捷键：`{shortcuts_display}`，可在 `config.py` 中修改。
2. 如需在管理员权限运行的程序（如任务管理器、游戏）中输入，请**以管理员权限运行客户端**。
3. 识别结果默认去除末尾逗句号。
4. 录音保存功能：若检测到 `FFmpeg`，会以 `mp3` 压缩保存；否则保存为 `wav` 。
        '''

        console.print(Markdown(markdown), highlight=True)
        console.rule()
        console.print(f'\n当前基文件夹：[cyan underline]{os.getcwd()}')
        console.print(f'\n服务端地址： [cyan underline]{Config.addr}:{Config.port}')
        console.print(f'\n当前所用快捷键：[green4]{shortcuts_display}')
        console.line()

        logger.debug("已显示麦克风模式启动提示")
    
    @staticmethod
    def show_file_tips() -> None:
        """显示文件转录模式的启动提示"""
        console.print(f'\n版本：[bold green]{__version__}')
        
        markdown = '\n项目地址：https://github.com/HaujetZhao/CapsWriter-Offline'
        console.print(Markdown(markdown), highlight=True)
        console.print(f'当前基文件夹：[cyan underline]{os.getcwd()}')
        console.print(f'服务端地址： [cyan underline]{Config.addr}:{Config.port}')
        
        logger.debug("已显示文件转录模式启动提示")
