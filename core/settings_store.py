import json
from pathlib import Path


class SettingsStore:
    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self.file = self.config_dir / "settings.json"
        self.data = {}

    def load(self) -> dict:
        self.data = {}
        if self.file.exists():
            try:
                with self.file.open('r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}
        return self.data

    def save(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with self.file.open('w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    # convenience getters/setters
    def get_download_path(self) -> str:
        return str(self.data.get('download_path', ''))

    def set_download_path(self, path: str) -> None:
        self.data['download_path'] = path

    def get_proxy(self) -> str:
        return str(self.data.get('proxy', ''))

    def set_proxy(self, proxy: str) -> None:
        self.data['proxy'] = proxy

    def get_timeout(self) -> int:
        v = self.data.get('timeout', 30)
        try:
            return int(v)
        except Exception:
            return 30

    def set_timeout(self, seconds: int) -> None:
        self.data['timeout'] = int(seconds)

    # download settings
    def get_thread_count(self) -> int:
        try:
            return int(self.data.get('thread_count', 3))
        except Exception:
            return 3

    def set_thread_count(self, v: int) -> None:
        self.data['thread_count'] = int(v)

    def get_retry_count(self) -> int:
        try:
            return int(self.data.get('retry_count', 3))
        except Exception:
            return 3

    def set_retry_count(self, v: int) -> None:
        self.data['retry_count'] = int(v)

    def get_image_format(self) -> str:
        return str(self.data.get('image_format', '原始格式'))

    def set_image_format(self, fmt: str) -> None:
        self.data['image_format'] = fmt

    # ui settings
    def get_theme(self) -> str:
        return str(self.data.get('theme', '深色主题'))

    def set_theme(self, theme: str) -> None:
        self.data['theme'] = theme

    def get_auto_update(self) -> bool:
        return bool(self.data.get('auto_update', True))

    def set_auto_update(self, enabled: bool) -> None:
        self.data['auto_update'] = bool(enabled)
