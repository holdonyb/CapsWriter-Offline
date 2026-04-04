"""
润色角色 - 用于按要求改写一段原文

说明：
- 可被“命令模式”调用（如：把前面这一段改得更有礼貌一些）
- 也可手动作为普通角色触发
"""

# ==================== 基本信息 ====================
name = '润色'                           # 角色名称，说「润色」触发
match = True                            # 是否启用前缀匹配
process = True                          # 是否启用 LLM 处理

# ==================== API 配置 ====================
provider = 'ollama'                     # API 提供商
api_url = ''
api_key = ''
model = 'gemma3:4b'                     # 模型名称

# ==================== 上下文管理 ====================
max_context_length = 4096               # 最大上下文长度（token 数）

# ==================== 功能配置 ====================
enable_hotwords = False                 # 是否启用热词
enable_rectify = False                  # 是否读取潜在纠错记录
enable_thinking = False                 # 是否启用思考（仅 Ollama）
enable_history = False                  # 润色模式每次独立，不保留历史
enable_read_selection = True            # 普通角色模式下可读选区；命令模式会临时关闭此项并直接传入原文
selection_max_length = 4096             # 选中文字最大长度
allow_selection_same_as_last_output = True   # 允许润色刚输出的内容（选中=上次输出时也处理）

# ==================== 输出配置 ====================
# typing + paste：润色结果通过粘贴输出，会替换当前选中的文字
output_mode = 'typing'
force_paste_for_replace = True                   # 强制粘贴，确保替换选中内容

# ==================== Toast 弹窗配置（本角色不使用） ====================
toast_initial_width = 0.5
toast_initial_height = 0
toast_font_family = '楷体'
toast_font_size = 23
toast_font_color = 'white'
toast_bg_color = '#075077'
toast_duration = 3000
toast_editable = False

# ==================== 生成参数 ====================
temperature = 0.5                       # 润色可稍低温度，更稳定
top_p = 0.9
max_tokens = 4096
stop = ''

# ==================== 高级选项 ====================
extra_options = {}

# ==================== 提示词前缀 ====================
prompt_prefix_hotwords = '热词列表：'
prompt_prefix_rectify = '纠错历史：'
prompt_prefix_selection = '选中文字：'
prompt_prefix_input = '用户指令：'

# ==================== System Prompt ====================
system_prompt = '''
# 角色

你是文字改写与润色助手。用户会提供“修改要求”和“原文”，你的任务是严格按要求改写原文。

# 要求

- 先理解“要求”，再改写“原文”
- 保持原意，不要新增事实
- 修正错别字、病句和口语赘词
- 仅输出改写后的完整文本
- 严禁解释、严禁加前后缀、严禁输出多版本
- 不要翻译语言（除非要求明确要翻译）
'''
