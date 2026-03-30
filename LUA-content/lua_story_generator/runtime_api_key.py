"""运行时 API Key 存储。前端保存后同步至此，UE/TCP 请求缺省时使用。"""
_api_key: str | None = None


def get_default_api_key() -> str | None:
    return _api_key if _api_key and str(_api_key).strip() else None


def set_default_api_key(key: str | None) -> None:
    global _api_key
    _api_key = (key or "").strip() or None
