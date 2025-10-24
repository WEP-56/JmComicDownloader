import os, sys
from pathlib import Path

def get_resource_path(relative: str) -> str:
    base_path = getattr(sys, '_MEIPASS', os.path.abspath('.'))
    return os.path.join(base_path, relative)

def ensure_dir(p: Path):
    Path(p).mkdir(parents=True, exist_ok=True)
