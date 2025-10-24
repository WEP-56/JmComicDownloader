import sys
import os
import subprocess
from PyQt5.QtWidgets import QMainWindow, QTableWidgetItem, QPushButton, QFileDialog, QListWidgetItem, QLabel
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.uic import loadUi

from core.resources import get_resource_path
from core.settings_store import SettingsStore


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ui_path = get_resource_path('ui/MainWindow.ui')
        loadUi(ui_path, self)

        # 搜索分页与防抖
        self.current_page = 1
        self.search_debounce = QTimer(self)
        self.search_debounce.setSingleShot(True)
        self.search_debounce.setInterval(400)
        self.search_debounce.timeout.connect(lambda: self.start_search(self.current_page))

        # 事件绑定
        if hasattr(self, 'search_btn'):
            self.search_btn.clicked.connect(self.on_search_clicked)
        if hasattr(self, 'search_input'):
            self.search_input.textChanged.connect(self.on_search_text_changed)
        if hasattr(self, 'prev_page_btn'):
            self.prev_page_btn.clicked.connect(self.go_prev_page)
        if hasattr(self, 'next_page_btn'):
            self.next_page_btn.clicked.connect(self.go_next_page)

        # 表格基本设置（封面/操作列）
        if hasattr(self, 'search_table'):
            self.search_table.setRowCount(0)
            self.search_table.setColumnCount(7)
            try:
                header = self.search_table.horizontalHeader()
                self.search_table.verticalHeader().setDefaultSectionSize(120)
                header.setSectionResizeMode(0, header.Fixed)
                self.search_table.setColumnWidth(0, 100)
                for col in range(1, 6):
                    header.setSectionResizeMode(col, header.Stretch)
                header.setSectionResizeMode(6, header.Fixed)
                self.search_table.setColumnWidth(6, 96)
            except Exception:
                pass

    # ========== 阅读器功能 ==========
    def _reader_update_page_label(self):
        if hasattr(self, 'reader_page_label') and hasattr(self, '_reader_files'):
            total = len(self._reader_files)
            cur = (self._reader_index + 1) if total > 0 else 0
            self.reader_page_label.setText(f"{cur} / {total}")
        if hasattr(self, 'reader_prev_btn'):
            self.reader_prev_btn.setEnabled(getattr(self, '_reader_index', 0) > 0)
        if hasattr(self, 'reader_next_btn'):
            total = len(getattr(self, '_reader_files', []))
            self.reader_next_btn.setEnabled(getattr(self, '_reader_index', 0) < total - 1)

    def _reader_show_current(self, offset=None):
        files = getattr(self, '_reader_files', [])
        idx = getattr(self, '_reader_index', 0)
        if not files or not (0 <= idx < len(files)):
            return
        img = files[idx]
        if hasattr(self, 'reader_image_label'):
            pix = QPixmap(img)
            if not pix.isNull():
                lab_size = self.reader_image_label.size()
                use_offset = self._drag_offset if offset is None else offset
                if getattr(self, '_reader_fit', True):
                    # 适配模式：按比例缩放至标签尺寸，拖拽仅作临时位移（回弹）
                    spix = pix.scaled(lab_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    if use_offset != (0, 0):
                        canvas = QPixmap(lab_size)
                        canvas.fill(Qt.transparent)
                        painter = QPainter(canvas)
                        painter.drawPixmap(use_offset[0], use_offset[1], spix)
                        painter.end()
                        self.reader_image_label.setPixmap(canvas)
                    else:
                        self.reader_image_label.setPixmap(spix)
                else:
                    # 原始大小：允许拖拽平移，偏移需要被约束并持久化
                    ox, oy = self._clamp_offset(pix.width(), pix.height(), lab_size.width(), lab_size.height(), use_offset)
                    self._drag_offset = (ox, oy)
                    canvas = QPixmap(lab_size)
                    canvas.fill(Qt.transparent)
                    painter = QPainter(canvas)
                    painter.drawPixmap(ox, oy, pix)
                    painter.end()
                    self.reader_image_label.setPixmap(canvas)
            else:
                self.reader_image_label.setText("无法加载图片")
        self._reader_update_page_label()

    def _center_offset(self, pw: int, ph: int, lw: int, lh: int):
        # 将图片在标签内居中（若图片小于容器）
        x = (lw - pw) // 2 if pw < lw else 0
        y = (lh - ph) // 2 if ph < lh else 0
        return (x, y)

    def _clamp_offset(self, pw: int, ph: int, lw: int, lh: int, offset):
        # 约束偏移，避免出现空白边（当图片大于容器时）；若图片小于容器，始终居中
        if pw <= lw:
            ox = (lw - pw) // 2
        else:
            min_x = lw - pw
            max_x = 0
            ox = max(min(offset[0], max_x), min_x)
        if ph <= lh:
            oy = (lh - ph) // 2
        else:
            min_y = lh - ph
            max_y = 0
            oy = max(min(offset[1], max_y), min_y)
        return (ox, oy)

    def _reader_prev(self):
        if getattr(self, '_reader_index', 0) > 0:
            self._reader_index -= 1
            self._reader_show_current()

    def _reader_next(self):
        total = len(getattr(self, '_reader_files', []))
        if getattr(self, '_reader_index', 0) < total - 1:
            self._reader_index += 1
            self._reader_show_current()

    def _reader_jump(self):
        try:
            v = int(self.reader_jump_input.text()) - 1
            files = getattr(self, '_reader_files', [])
            if 0 <= v < len(files):
                self._reader_index = v
                self._reader_show_current()
            self.reader_jump_input.clear()
        except Exception:
            pass

    # 事件过滤：滚轮翻页、双击缩放
    def eventFilter(self, obj, event):
        try:
            from PyQt5.QtCore import QEvent
            if obj is getattr(self, 'reader_image_label', None):
                if event.type() == QEvent.Wheel:
                    if event.angleDelta().y() < 0:
                        self._reader_next()
                    else:
                        self._reader_prev()
                    return True
                if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                    self._dragging = True
                    self._drag_start = event.pos()
                    self._drag_origin_offset = self._drag_offset
                    return True
                if event.type() == QEvent.MouseMove and self._dragging and self._drag_start is not None:
                    d = event.pos() - self._drag_start
                    cand = (self._drag_origin_offset[0] + d.x(), self._drag_origin_offset[1] + d.y())
                    if getattr(self, '_reader_fit', True):
                        # 适配模式：临时偏移即可
                        self._reader_show_current(offset=cand)
                    else:
                        # 原始模式：持久化偏移并裁剪
                        self._drag_offset = cand
                        self._reader_show_current()
                    return True
                if event.type() == QEvent.MouseButtonRelease and self._dragging and event.button() == Qt.LeftButton:
                    self._dragging = False
                    self._drag_start = None
                    if getattr(self, '_reader_fit', True):
                        # 适配模式：回弹
                        self._drag_offset = (0, 0)
                        self._reader_show_current()
                    else:
                        # 原始模式：保留最后偏移
                        self._reader_show_current()
                    return True
                if event.type() == QEvent.MouseButtonDblClick:
                    # 切换适应窗口/原始尺寸
                    self._reader_fit = not getattr(self, '_reader_fit', True)
                    try:
                        # 切换到原始大小时，居中显示；切换到适配模式时，清空偏移
                        if not self._reader_fit and getattr(self, 'reader_image_label', None):
                            files = getattr(self, '_reader_files', [])
                            idx = getattr(self, '_reader_index', 0)
                            if files and 0 <= idx < len(files):
                                pix = QPixmap(files[idx])
                                if not pix.isNull():
                                    lab = self.reader_image_label.size()
                                    self._drag_offset = self._center_offset(pix.width(), pix.height(), lab.width(), lab.height())
                        else:
                            self._drag_offset = (0, 0)
                    except Exception:
                        self._drag_offset = (0, 0)
                    self._reader_show_current()
                    return True
        except Exception:
            pass
        return super().eventFilter(obj, event)

    # 键盘：左右/PgUp/PgDn 翻页
    def keyPressEvent(self, event):
        try:
            from PyQt5.QtCore import Qt
            key = event.key()
            if key in (Qt.Key_Left, Qt.Key_A, Qt.Key_PageUp):
                self._reader_prev()
                return
            if key in (Qt.Key_Right, Qt.Key_D, Qt.Key_PageDown):
                self._reader_next()
                return
        except Exception:
            pass
        super().keyPressEvent(event)

    # 窗口尺寸变化时，适配模式下重绘当前页
    def resizeEvent(self, event):
        try:
            if getattr(self, '_reader_fit', True):
                self._reader_show_current()
        except Exception:
            pass
        super().resizeEvent(event)

        self.update_pagination_ui()

        # 线程占位
        self.search_thread = None
        self.download_thread = None
        # 初始化设置存储
        from pathlib import Path
        self._settings = SettingsStore(Path.home() / ".jmcomic_downloader")
        data = self._settings.load()
        if hasattr(self, 'download_path_input'):
            dlp = self._settings.get_download_path()
            if not dlp:
                # 默认下载目录：
                # - 打包为 exe 时：使用可执行文件所在目录
                # - 开发环境：使用项目根目录
                try:
                    if getattr(sys, 'frozen', False):
                        default_dl = str(Path(sys.executable).parent.resolve())
                    else:
                        # bindings.py 位于 ui/ 下，项目根为上上级
                        default_dl = str((Path(__file__).resolve().parents[1].parent).resolve())
                except Exception:
                    default_dl = str((Path.home() / "Downloads" / "JMComic").resolve())
                self._settings.set_download_path(default_dl)
                self._settings.save()
                dlp = default_dl
            self.download_path_input.setText(dlp)
        if hasattr(self, 'timeout_spin'):
            self.timeout_spin.setValue(self._settings.get_timeout())
        if hasattr(self, 'proxy_input'):
            self.proxy_input.setText(self._settings.get_proxy())
        if hasattr(self, 'thread_count_spin'):
            self.thread_count_spin.setValue(self._settings.get_thread_count())
        if hasattr(self, 'retry_count_spin'):
            self.retry_count_spin.setValue(self._settings.get_retry_count())
        if hasattr(self, 'image_format_combo'):
            # 尝试匹配保存的文本
            fmt = self._settings.get_image_format()
            idx = self.image_format_combo.findText(fmt)
            if idx >= 0:
                self.image_format_combo.setCurrentIndex(idx)
        if hasattr(self, 'theme_combo'):
            theme = self._settings.get_theme()
            idx = self.theme_combo.findText(theme)
            if idx >= 0:
                self.theme_combo.setCurrentIndex(idx)
        if hasattr(self, 'auto_update_check'):
            self.auto_update_check.setChecked(self._settings.get_auto_update())
        # 应用主题：默认浅色以保证可读性
        theme_to_apply = self._settings.get_theme() if hasattr(self, '_settings') else '浅色主题'
        if not theme_to_apply:
            theme_to_apply = '浅色主题'
        self._apply_theme(theme_to_apply)

        # 绑定设置与漫画库按钮
        if hasattr(self, 'save_settings_btn'):
            self.save_settings_btn.clicked.connect(self._save_settings)
        if hasattr(self, 'library_refresh_btn'):
            self.library_refresh_btn.clicked.connect(self._refresh_library)
        if hasattr(self, 'library_list'):
            self.library_list.itemClicked.connect(self._on_library_item_clicked)
            # 兼容键盘/程序改变选中项
            try:
                self.library_list.currentRowChanged.connect(self._on_library_row_changed)
            except Exception:
                pass
        if hasattr(self, 'read_btn'):
            self.read_btn.clicked.connect(self._open_manga_reader)
        if hasattr(self, 'delete_btn'):
            self.delete_btn.clicked.connect(self._delete_manga)
        if hasattr(self, 'reader_prev_btn'):
            self.reader_prev_btn.clicked.connect(self._reader_prev)
        if hasattr(self, 'reader_next_btn'):
            self.reader_next_btn.clicked.connect(self._reader_next)
        if hasattr(self, 'reader_jump_input'):
            self.reader_jump_input.returnPressed.connect(self._reader_jump)
        if hasattr(self, 'remove_queue_btn'):
            self.remove_queue_btn.clicked.connect(self._remove_queue_selected)
        if hasattr(self, 'stop_download_btn'):
            self.stop_download_btn.clicked.connect(self._stop_download)

        # 阅读器交互增强：滚轮翻页、双击缩放、键盘左右翻页
        self._reader_fit = True
        self._dragging = False
        self._drag_start = None
        self._drag_origin_offset = (0, 0)
        self._drag_offset = (0, 0)
        if hasattr(self, 'reader_image_label'):
            try:
                from PyQt5.QtCore import Qt
                self.reader_image_label.setFocusPolicy(Qt.StrongFocus)
                self.reader_image_label.installEventFilter(self)
            except Exception:
                pass

        # 绑定下载路径与漫画库：路径变化即刷新；启动后立即刷新
        try:
            if hasattr(self, 'download_path_input'):
                self.download_path_input.textChanged.connect(self._on_download_path_changed)
        except Exception:
            pass
        # 某些 UI 下存在 tabWidget，切换到漫画库页时刷新
        try:
            if hasattr(self, 'tab_widget'):
                self.tab_widget.currentChanged.connect(lambda idx: self._refresh_library())
        except Exception:
            pass
        # 初始刷新一次，保证无需额外操作即可浏览
        self._refresh_library()

    # ========== 搜索逻辑 ==========
    def on_search_clicked(self):
        self.current_page = 1
        self.start_search(self.current_page)

    def on_search_text_changed(self, _text: str):
        self.current_page = 1
        if self.search_input.text().strip():
            self.search_debounce.start()
        else:
            self.search_debounce.stop()

    def start_search(self, page: int):
        kw = self.search_input.text().strip() if hasattr(self, 'search_input') else ''
        if not kw:
            return

        try:
            from core.search_worker import SearchWorker
        except Exception:
            return

        if hasattr(self, 'search_btn'):
            self.search_btn.setEnabled(False)
        if hasattr(self, 'statusbar'):
            self.statusbar.showMessage(f"正在搜索: {kw}（第 {page} 页）")

        # 使用设置中的代理与超时
        proxy = self._settings.get_proxy() if hasattr(self, '_settings') else ''
        timeout = self._settings.get_timeout() if hasattr(self, '_settings') else 30
        self.search_thread = SearchWorker(kw, page=page, proxy=proxy, timeout=timeout)
        self.search_thread.search_finished.connect(self.on_search_finished)
        self.search_thread.start()

    def on_search_finished(self, results, error: str):
        if hasattr(self, 'search_btn'):
            self.search_btn.setEnabled(True)
        if hasattr(self, 'statusbar') and error:
            self.statusbar.showMessage(f"搜索失败: {error}")
            return

        # 顺序加载：每次渲染一行并等待封面加载完成再继续，避免卡顿
        if hasattr(self, 'search_table'):
            self.search_table.setRowCount(0)
            self._pending_results = list(results)
            self._start_sequential_results()

    def _start_sequential_results(self):
        # 启动或继续逐条渲染
        if not hasattr(self, '_pending_results'):
            return
        if not self._pending_results:
            if hasattr(self, 'statusbar'):
                total = getattr(self, '_last_result_count', 0)
                self.statusbar.showMessage(f"搜索完成，找到 {total} 个结果")
            self.update_pagination_ui()
            return
        if not hasattr(self, '_cover_loaders'):
            self._cover_loaders = []
        if not hasattr(self, '_last_result_count'):
            self._last_result_count = len(self._pending_results)
        item = self._pending_results.pop(0)
        row = self.search_table.rowCount()
        self.search_table.insertRow(row)
        # 封面占位
        cover_label = QLabel("加载中…")
        cover_label.setAlignment(Qt.AlignCenter)
        self.search_table.setCellWidget(row, 0, cover_label)
        # ID/标题/作者/标签/评分
        self.search_table.setItem(row, 1, QTableWidgetItem(item.get('id', '')))
        self.search_table.setItem(row, 2, QTableWidgetItem(item.get('title', '')))
        self.search_table.setItem(row, 3, QTableWidgetItem(item.get('author', '-')))
        tags = ', '.join(item.get('tags', []))
        self.search_table.setItem(row, 4, QTableWidgetItem(tags))
        self.search_table.setItem(row, 5, QTableWidgetItem(item.get('score', '-')))
        # 操作按钮
        # 操作列：下载/添加 垂直排列
        from PyQt5.QtWidgets import QWidget, QVBoxLayout
        op_widget = QWidget()
        op_layout = QVBoxLayout(op_widget)
        op_layout.setContentsMargins(2, 2, 2, 2)
        op_layout.setSpacing(4)
        btn_dl = QPushButton("下载")
        btn_dl.clicked.connect(lambda _=False, album_id=item.get('id',''): self._download_single(album_id))
        btn_add = QPushButton("添加")
        btn_add.clicked.connect(lambda _=False, album_id=item.get('id',''): self._add_id_to_queue(album_id))
        op_layout.addWidget(btn_dl)
        op_layout.addWidget(btn_add)
        self.search_table.setCellWidget(row, 6, op_widget)

        # 封面：加载完成后继续下一条；没有封面则立即继续
        if item.get('cover'):
            loader = _CoverLoader(row, item['cover'], self._settings.get_proxy() if hasattr(self, '_settings') else '', self._settings.get_timeout() if hasattr(self, '_settings') else 15)
            def _after_loaded(r: int, data: bytes):
                self._on_cover_loaded(r, data)
                QTimer.singleShot(0, self._start_sequential_results)
            loader.loaded.connect(_after_loaded)
            self._cover_loaders.append(loader)
            loader.start()
        else:
            QTimer.singleShot(0, self._start_sequential_results)

    def go_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.start_search(self.current_page)

    def go_next_page(self):
        self.current_page += 1
        self.start_search(self.current_page)

    def update_pagination_ui(self):
        if hasattr(self, 'page_info_label'):
            self.page_info_label.setText(f"第 {self.current_page} 页")
        if hasattr(self, 'prev_page_btn'):
            self.prev_page_btn.setEnabled(self.current_page > 1)

    # ========== 下载逻辑 ==========
    def _browse_download(self):
        path = QFileDialog.getExistingDirectory(self, "选择下载文件夹", self.download_path_input.text() if hasattr(self, 'download_path_input') else "")
        if path and hasattr(self, 'download_path_input'):
            self.download_path_input.setText(path)

    def _add_to_queue(self):
        if not hasattr(self, 'album_id_input') or not hasattr(self, 'download_list'):
            return
        album_id = self.album_id_input.text().strip()
        if not album_id:
            if hasattr(self, 'statusbar'):
                self.statusbar.showMessage("请输入漫画ID")
            return
        for i in range(self.download_list.count()):
            if album_id in self.download_list.item(i).text():
                return
        self.download_list.addItem(QListWidgetItem(f"漫画ID: {album_id}"))

    def _add_id_to_queue(self, album_id: str):
        if not album_id or not hasattr(self, 'download_list'):
            return
        for i in range(self.download_list.count()):
            if album_id in self.download_list.item(i).text():
                return
        self.download_list.addItem(QListWidgetItem(f"漫画ID: {album_id}"))

    def _start_download(self, album_id_override: str = ""):
        # 简化：取队列第一个或输入框（仅在成功启动后再移除队列项）
        album_id = album_id_override or None
        deque_index = None
        if album_id is None and hasattr(self, 'download_list') and self.download_list.count() > 0:
            text = self.download_list.item(0).text()
            album_id = ''.join(ch for ch in text if ch.isdigit())
            deque_index = 0
        if not album_id and hasattr(self, 'album_id_input'):
            album_id = self.album_id_input.text().strip()
        if not album_id:
            if hasattr(self, 'statusbar'):
                self.statusbar.showMessage("请输入漫画ID")
            return

        save_path = self.download_path_input.text().strip() if hasattr(self, 'download_path_input') else ""
        if not save_path:
            if hasattr(self, 'statusbar'):
                self.statusbar.showMessage("请先选择保存目录")
            return
        import os
        if not os.path.isdir(save_path):
            if hasattr(self, 'statusbar'):
                self.statusbar.showMessage("保存目录不存在")
            return

        try:
            from core.download_worker import DownloadWorker
            from core.jm_option import create_jm_option
            jm_option = create_jm_option(save_path)
            if jm_option is None:
                raise RuntimeError("JMComic 配置创建失败")
        except Exception as e:
            if hasattr(self, 'log_output'):
                self.log_output.append(f"无法开始下载: {e}")
            if hasattr(self, 'statusbar'):
                self.statusbar.showMessage(f"无法开始下载: {e}")
            return

        self.download_thread = DownloadWorker(album_id, save_path, jm_option, workspace_dir=save_path)
        self.download_thread.progress_updated.connect(self._update_progress)
        self.download_thread.status_changed.connect(self._update_status)
        self.download_thread.download_finished.connect(self._on_download_finished)
        self.progress_bar.setRange(0, 0)
        if hasattr(self, 'start_download_btn'):
            self.start_download_btn.setEnabled(False)
        # 成功启动后再移除队列项
        if deque_index is not None and hasattr(self, 'download_list') and self.download_list.count() > deque_index and not album_id_override:
            self.download_list.takeItem(deque_index)
        self.download_thread.start()

    def _download_single(self, album_id: str):
        if not album_id:
            return
        # 直接下载，不移除队列
        self._start_download(album_id_override=album_id)

    def _remove_queue_selected(self):
        if not hasattr(self, 'download_list'):
            return
        for item in self.download_list.selectedItems():
            row = self.download_list.row(item)
            self.download_list.takeItem(row)

    def _stop_download(self):
        # 尝试终止当前下载线程（尽力而为，第三方库可能阻塞）
        if hasattr(self, 'download_thread') and self.download_thread:
            try:
                if self.download_thread.isRunning():
                    self.download_thread.requestInterruption()
                    # 不推荐但作为最后手段
                    self.download_thread.terminate()
                    self.download_thread.wait(1000)
                    if hasattr(self, 'statusbar'):
                        self.statusbar.showMessage("下载已停止")
            except Exception:
                pass
        if hasattr(self, 'start_download_btn'):
            self.start_download_btn.setEnabled(True)
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)

    def _update_progress(self, cur: int, total: int):
        if total <= 0:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            val = int(cur * 100 / max(total, 1))
            self.progress_bar.setValue(val)

    def _update_status(self, msg: str):
        if hasattr(self, 'log_output'):
            self.log_output.append(msg)
        if hasattr(self, 'statusbar'):
            self.statusbar.showMessage(msg)

    def _on_download_finished(self, success: bool, message: str):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if success else 0)
        if hasattr(self, 'log_output'):
            self.log_output.append(message)
        if hasattr(self, 'statusbar'):
            self.statusbar.showMessage(message)
        # 刷新漫画库
        self._refresh_library()
        if hasattr(self, 'start_download_btn'):
            self.start_download_btn.setEnabled(True)

    # ========== 设置 & 漫画库 ==========
    def _save_settings(self):
        if hasattr(self, 'download_path_input'):
            self._settings.set_download_path(self.download_path_input.text().strip())
        if hasattr(self, 'proxy_input'):
            self._settings.set_proxy(self.proxy_input.text().strip())
        if hasattr(self, 'timeout_spin'):
            self._settings.set_timeout(self.timeout_spin.value())
        if hasattr(self, 'thread_count_spin'):
            self._settings.set_thread_count(self.thread_count_spin.value())
        if hasattr(self, 'retry_count_spin'):
            self._settings.set_retry_count(self.retry_count_spin.value())
        if hasattr(self, 'image_format_combo'):
            self._settings.set_image_format(self.image_format_combo.currentText())
        if hasattr(self, 'theme_combo'):
            self._settings.set_theme(self.theme_combo.currentText())
        if hasattr(self, 'auto_update_check'):
            self._settings.set_auto_update(self.auto_update_check.isChecked())
        self._settings.save()
        if hasattr(self, 'statusbar'):
            self.statusbar.showMessage("设置已保存")
        # 保存后应用主题
        if hasattr(self, 'theme_combo'):
            self._apply_theme(self.theme_combo.currentText())
        # 同步刷新漫画库，使其始终与下载路径一致
        self._refresh_library()

    def _on_download_path_changed(self, *_):
        try:
            if hasattr(self, 'download_path_input'):
                path = self.download_path_input.text().strip()
                self._settings.set_download_path(path)
                self._settings.save()
                self._refresh_library()
        except Exception:
            pass

    def closeEvent(self, event):
        try:
            if hasattr(self, 'download_path_input'):
                self._settings.set_download_path(self.download_path_input.text().strip())
            if hasattr(self, 'proxy_input'):
                self._settings.set_proxy(self.proxy_input.text().strip())
            if hasattr(self, 'timeout_spin'):
                self._settings.set_timeout(self.timeout_spin.value())
            self._settings.save()
        except Exception:
            pass
        super().closeEvent(event)

    def _apply_theme(self, theme_text: str):
        try:
            from PyQt5.QtGui import QPalette, QColor
            # 强制使用系统浅色标准调色板：白底黑字，屏蔽主题切换
            pal = self.style().standardPalette()
            self.setPalette(pal)
        except Exception:
            pass

    def _refresh_library(self):
        if not hasattr(self, 'library_list'):
            return
        self.library_list.clear()
        root = self.download_path_input.text().strip() if hasattr(self, 'download_path_input') else ''
        if not root:
            return
        import os
        try:
            for name in os.listdir(root):
                p = os.path.join(root, name)
                if os.path.isdir(p):
                    self.library_list.addItem(name)
        except Exception:
            pass

    def _on_library_item_clicked(self, item):
        # 展示选中目录的详情与封面预览
        if not item:
            return
        root = self.download_path_input.text().strip() if hasattr(self, 'download_path_input') else ''
        if not root:
            return
        import os
        import math
        sel_path = os.path.join(root, item.text())
        # 统计文件数与体积
        total_files = 0
        total_size = 0
        first_image = None
        exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
        for r, _ds, fs in os.walk(sel_path):
            for f in fs:
                total_files += 1
                fp = os.path.join(r, f)
                try:
                    total_size += os.path.getsize(fp)
                except Exception:
                    pass
                if not first_image and os.path.splitext(f)[1].lower() in exts:
                    first_image = fp
        # 详情
        if hasattr(self, 'details_text'):
            mb = total_size / (1024 * 1024.0)
            self.details_text.setPlainText(f"目录: {sel_path}\n文件数: {total_files}\n大小: {mb:.2f} MB")
        # 预览
        if hasattr(self, 'reader_image_label'):
            if first_image:
                pix = QPixmap(first_image)
                if not pix.isNull():
                    target = pix.scaled(self.reader_image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.reader_image_label.setPixmap(target)
                else:
                    self.reader_image_label.setText("预览不可用")
            else:
                self.reader_image_label.setText("无图片")
        # 更新阅读器状态
        self._reader_files = []
        for r, _ds, fs in os.walk(sel_path):
            for f in sorted(fs):
                if os.path.splitext(f)[1].lower() in exts:
                    self._reader_files.append(os.path.join(r, f))
        self._reader_index = 0
        self._reader_update_page_label()

    def _on_library_row_changed(self, row: int):
        try:
            if row < 0 or not hasattr(self, 'library_list'):
                return
            item = self.library_list.item(row)
            if item is not None:
                self._on_library_item_clicked(item)
        except Exception:
            pass

    def _open_manga_reader(self):
        # 在应用内打开并从第1张开始阅读；若未装载当前选中项，先装载
        if (not hasattr(self, '_reader_files')) or (not self._reader_files):
            if hasattr(self, 'library_list') and self.library_list.currentItem():
                self._on_library_item_clicked(self.library_list.currentItem())
        if not self._reader_files:
            return
        self._reader_index = 0
        self._reader_show_current()

    def _delete_manga(self):
        # 删除选中目录（无确认）
        if not hasattr(self, 'library_list'):
            return
        item = self.library_list.currentItem()
        if item is None:
            sels = self.library_list.selectedItems()
            item = sels[0] if sels else None
        if not item:
            return
        root = self.download_path_input.text().strip() if hasattr(self, 'download_path_input') else ''
        if not root:
            return
        sel_path = os.path.join(root, item.text())
        try:
            import shutil
            shutil.rmtree(sel_path)
            self._refresh_library()
        except Exception:
            pass

    def _on_cover_loaded(self, row: int, data: bytes):
        try:
            label = self.search_table.cellWidget(row, 0)
            if isinstance(label, QLabel):
                pix = QPixmap()
                if data and pix.loadFromData(data):
                    label.setPixmap(pix.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                else:
                    label.setText("无图")
        except Exception:
            pass


class _CoverLoader(QThread):
    loaded = pyqtSignal(int, bytes)  # row, image bytes

    def __init__(self, row: int, url: str, proxy: str = "", timeout: int = 15):
        super().__init__()
        self.row = row
        self.url = url
        self.proxy = proxy
        self.timeout = timeout

    def run(self):
        try:
            try:
                import cloudscraper
            except Exception:
                self.loaded.emit(self.row, QPixmap())
                return
            proxies = None
            if self.proxy and (self.proxy.startswith("http://") or self.proxy.startswith("https://")):
                proxies = {"http": self.proxy, "https": self.proxy}
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(self.url, timeout=self.timeout, proxies=proxies)
            if resp.status_code != 200:
                self.loaded.emit(self.row, QPixmap())
                return
            data = resp.content or b''
            self.loaded.emit(self.row, data)
        except Exception:
            self.loaded.emit(self.row, b'')


def load_main_window() -> QMainWindow:
    win = MainWindow()
    # 绑定下载区按钮事件
    if hasattr(win, 'browse_download_btn'):
        win.browse_download_btn.clicked.connect(win._browse_download)
    if hasattr(win, 'add_queue_btn'):
        win.add_queue_btn.clicked.connect(win._add_to_queue)
    if hasattr(win, 'start_download_btn'):
        win.start_download_btn.clicked.connect(win._start_download)
    return win
