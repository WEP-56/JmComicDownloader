from pathlib import Path

try:
    import jmcomic
    JM_AVAILABLE = True
except Exception:
    jmcomic = None
    JM_AVAILABLE = False


def create_jm_option(workspace: str, config_dir: Path | None = None):
    """创建 jmcomic 的 Option。
    为适配不同版本的 jmcomic，这里优先返回默认选项，不直接传入 path 等可能不兼容的参数。
    下载目录通过 DownloadWorker 的工作目录切换与后续迁移逻辑确保正确落地。
    """
    if not JM_AVAILABLE:
        return None

    try:
        # 始终返回默认配置，避免因 __init__ 签名变化导致报错
        return jmcomic.JmOption.default()
    except Exception:
        return None
