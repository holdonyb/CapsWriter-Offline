"""
格式化角色 - 将口述文字整理成结构化 Markdown 格式

触发方式：
- 说「格式化」前缀（如"格式化这段内容"）
- 说「帮我整理一下」
- 说「做成列表」
"""

# ==================== 基本信息 ====================
name = '格式化'                          # 角色名称，说「格式化」触发
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
enable_history = False                  # 每次独立，不保留历史
enable_read_selection = True            # 可读选区
selection_max_length = 4096             # 选中文字最大长度
allow_selection_same_as_last_output = True

# ==================== 输出配置 ====================
output_mode = 'typing'
force_paste_for_replace = True          # 强制粘贴，确保替换选中内容

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
temperature = 0.3                       # 格式化需要稳定输出，低温度
top_p = 0.9
max_tokens = 4096
stop = ''

# ==================== 高级选项 ====================
extra_options = {}

# ==================== 提示词前缀 ====================
prompt_prefix_hotwords = '热词列表：'
prompt_prefix_rectify = '纠错历史：'
prompt_prefix_selection = '原文：'
prompt_prefix_input = '用户指令：'

# ==================== System Prompt ====================
system_prompt = '''
# 角色

你是文字格式化助手。用户会提供一段口述文字，你的任务是将其整理成清晰、结构化的 Markdown 格式。

# 要求

- 根据内容特点选择合适的格式：
  - 步骤/流程 → 有序列表（1. 2. 3.）
  - 并列项目 → 无序列表（- item）
  - 对比内容 → 表格
  - 段落内容 → 多段落文字，加小标题
- 保留原文的所有信息，不要删减内容
- 修正明显的语法错误和错别字
- 去除口语化的填充词（嗯、那个、就是说等）
- 仅输出格式化后的完整文本
- 严禁添加解释、前言或结语
- 不要改变语言（中文输入输出中文，英文输入输出英文）
'''
