"""数据源配置加密/解密工具

使用 Fernet 对称加密（基于 cryptography 库，项目已有此依赖）。
密钥通过环境变量 DATASOURCE_ENCRYPT_KEY 配置，未配置时使用 base64 编码（仅开发环境）。
"""

import base64
import json
import os
from typing import Any

from src.utils import logger

# Fernet 密钥（32 字节 URL-safe base64 编码）
_FERNET_KEY = os.getenv("DATASOURCE_ENCRYPT_KEY", "")


def _get_fernet():
    """获取 Fernet 加密器实例"""
    try:
        from cryptography.fernet import Fernet

        if _FERNET_KEY:
            return Fernet(_FERNET_KEY.encode())
        # 未配置密钥时返回 None，降级到 base64
        return None
    except Exception:
        return None


def encrypt_datasource_config(config: dict[str, Any]) -> str:
    """加密数据源配置"""
    config_str = json.dumps(config, ensure_ascii=False)

    fernet = _get_fernet()
    if fernet:
        return fernet.encrypt(config_str.encode("utf-8")).decode("utf-8")

    # 降级：base64 编码（仅开发环境）
    logger.warning("DATASOURCE_ENCRYPT_KEY 未配置，使用 base64 编码（不安全，仅限开发环境）")
    return base64.b64encode(config_str.encode("utf-8")).decode("utf-8")


def decrypt_datasource_config(encrypted_config: str) -> dict[str, Any]:
    """解密数据源配置"""
    fernet = _get_fernet()
    if fernet:
        try:
            decrypted = fernet.decrypt(encrypted_config.encode("utf-8"))
            return json.loads(decrypted.decode("utf-8"))
        except Exception:
            pass

    # 降级：尝试 base64 解码
    try:
        config_str = base64.b64decode(encrypted_config).decode("utf-8")
        return json.loads(config_str)
    except Exception as e:
        logger.error(f"解密数据源配置失败: {e}")
        raise ValueError("无法解密数据源配置") from e
