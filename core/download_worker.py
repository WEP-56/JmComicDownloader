import os
import shutil
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal

try:
    import jmcomic
    JM_AVAILABLE = True
except Exception:
    jmcomic = None
    JM_AVAILABLE = False


class DownloadWorker(QThread):
    """从旧 DownloadThread 迁移的下载线程实现"""
    progress_updated = pyqtSignal(int, int)  # current, total
    status_changed = pyqtSignal(str)
    download_finished = pyqtSignal(bool, str)

    def __init__(self, album_id: str, save_path: str, option=None, workspace_dir: str = ""):
        super().__init__()
        self.album_id = album_id
        self.save_path = save_path
        self.option = option
        self.workspace_dir = workspace_dir
        self.is_running = True

    def run(self):
        try:
            self.status_changed.emit(f"开始下载漫画 {self.album_id}...")

            if JM_AVAILABLE:
                option = self.option if self.option else jmcomic.JmOption.default()
                old_cwd = os.getcwd()
                exe_dir = Path(getattr(__import__('sys'), 'frozen', False) and os.path.dirname(__import__('sys').executable) or old_cwd)
                try:
                    if self.workspace_dir:
                        os.makedirs(self.workspace_dir, exist_ok=True)
                        os.chdir(self.workspace_dir)
                    jmcomic.download_album(self.album_id, option)
                finally:
                    try:
                        os.chdir(old_cwd)
                    except Exception:
                        pass

                # 标记完成
                self.progress_updated.emit(100, 100)

                # 纠错迁移：若库把内容写到了 EXE 同级的 JMComic 下，迁移到目标 workspace/JMComic
                try:
                    target_ws = Path(self.workspace_dir) if self.workspace_dir else Path(old_cwd)
                    target_jm = target_ws / 'JMComic'
                    src_jm = exe_dir / 'JMComic'
                    if src_jm.exists() and src_jm.is_dir() and (src_jm.resolve() != target_jm.resolve()):
                        target_jm.mkdir(parents=True, exist_ok=True)
                        for name in os.listdir(src_jm):
                            s = src_jm / name
                            d = target_jm / name
                            if s.is_dir():
                                if not d.exists():
                                    shutil.move(str(s), str(d))
                                else:
                                    for root, _dirs, files in os.walk(s):
                                        rel = Path(root).relative_to(s)
                                        (d / rel).mkdir(parents=True, exist_ok=True)
                                        for f in files:
                                            shutil.move(str(Path(root) / f), str(d / rel / f))
                                    shutil.rmtree(s, ignore_errors=True)
                            else:
                                shutil.move(str(s), str(d))
                        try:
                            os.rmdir(src_jm)
                        except Exception:
                            pass
                    # 扁平化：若目标 workspace 下仍存在 JMComic 子目录，则将其内容上移至 workspace 根并删除 JMComic
                    if target_jm.exists() and target_jm.is_dir():
                        for name in os.listdir(target_jm):
                            s = target_jm / name
                            d = target_ws / name
                            if d.exists():
                                if s.is_dir():
                                    for root, _dirs, files in os.walk(s):
                                        rel = Path(root).relative_to(s)
                                        (d / rel).mkdir(parents=True, exist_ok=True)
                                        for f in files:
                                            shutil.move(str(Path(root) / f), str(d / rel / f))
                                    shutil.rmtree(s, ignore_errors=True)
                                else:
                                    base = d.stem
                                    ext = d.suffix
                                    k = 1
                                    nd = d
                                    while nd.exists():
                                        nd = d.with_name(f"{base}_{k}{ext}")
                                        k += 1
                                    shutil.move(str(s), str(nd))
                            else:
                                shutil.move(str(s), str(d))
                        try:
                            os.rmdir(target_jm)
                        except Exception:
                            pass
                except Exception:
                    pass

                self.download_finished.emit(True, f"漫画 {self.album_id} 下载完成！")
            else:
                # 未安装 jmcomic：发出失败提示
                self.download_finished.emit(False, "未安装 jmcomic 库，无法下载")
        except Exception as e:
            self.download_finished.emit(False, f"下载失败: {e}")
