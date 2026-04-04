"""
LLM 客户端池

功能：
1. 缓存 OpenAI 客户端实例
2. 根据 provider 和 api_url 创建和获取客户端
"""
from openai import OpenAI
from typing import Dict
from util.llm.llm_constants import APIConfig
from . import logger


class ClientPool:
    """OpenAI 客户端池"""

    def __init__(self):
        self._clients: Dict[str, OpenAI] = {}

    def get_client(self, provider: str, api_url: str = '', api_key: str = '') -> OpenAI:
        """获取 OpenAI 客户端（带缓存）

        Args:
            provider: API 提供商（如 'ollama', 'openai'）
            api_url: API 地址（可选，优先使用此值）
            api_key: API Key（可选）

        Returns:
            OpenAI 客户端实例
        """
        final_url = self._resolve_api_url(provider, api_url)
        cache_key = f"{provider}_{final_url}"

        if cache_key not in self._clients:
            # 获取 api_key
            final_key = api_key or APIConfig.DEFAULT_API_KEYS.get(provider, '')

            # 获取超时配置（根据 provider 选择，未配置则使用默认值）
            timeout = APIConfig.DEFAULT_TIMEOUTS.get(provider, APIConfig.DEFAULT_TIMEOUT)

            # 创建客户端
            self._clients[cache_key] = OpenAI(
                base_url=final_url,
                api_key=final_key,
                timeout=timeout,
            )

        return self._clients[cache_key]

    def clear(self):
        """清空客户端缓存"""
        self._clients.clear()

    def _resolve_api_url(self, provider: str, api_url: str = '') -> str:
        """解析最终 API 地址，对明显错误的覆盖值做兜底。"""
        api_url = (api_url or '').strip()
        default_url = APIConfig.DEFAULT_API_URLS.get(provider, '')

        if not api_url:
            return default_url

        if api_url.startswith(('http://', 'https://')):
            return api_url

        if default_url:
            logger.warning(
                "检测到无效 API URL 覆盖，provider=%s, api_url=%r；已回退到默认地址 %s",
                provider,
                api_url,
                default_url,
            )
            return default_url

        return api_url
