#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JMComic 漫画下载器
基于 PyQt5 和 JMComic API 的现代化漫画下载工具
"""

import sys
import os
import json
import threading
from pathlib import Path
from typing import List, Dict, Optional
import re
from urllib.parse import quote_plus
import shutil

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QListWidget,
    QListWidgetItem, QProgressBar, QTextEdit, QMessageBox,
    QFileDialog, QSplitter, QFrame, QGroupBox, QCheckBox,
    QSpinBox, QComboBox, QStatusBar, QMenuBar, QMenu, QAction,
    QTableWidget, QTableWidgetItem, QHeaderView, QGridLayout,
    QScrollArea, QToolButton, QStyle
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPalette, QColor, QImage

# 依赖：JMComic API（可选）与网络抓取库
try:
    import jmcomic

    JM_AVAILABLE = True
except ImportError:
    JM_AVAILABLE = False
    print("警告: 未安装jmcomic库，部分功能将无法使用")
    print("请运行: pip install jmcomic")

# 抓取依赖
try:
    import cloudscraper
    from bs4 import BeautifulSoup
    SCRAPER_AVAILABLE = True
except ImportError:
    SCRAPER_AVAILABLE = False
    print("警告: 未安装cloudscraper或beautifulsoup4，搜索功能将受限")
    print("请运行: pip install cloudscraper beautifulsoup4")


class DownloadThread(QThread):
    """下载线程类"""
    progress_updated = pyqtSignal(int, int)  # 当前, 总数
    status_changed = pyqtSignal(str)
    download_finished = pyqtSignal(bool, str)

    def __init__(self, album_id: str, save_path: str, option=None, workspace_dir: str = ""):
        super().__init__()
        self.album_id = album_id
        self.save_path = save_path
        self.option = option
        self.is_running = True
        self.workspace_dir = workspace_dir

    def run(self):
        """执行下载"""
        try:
            self.status_changed.emit(f"开始下载漫画 {self.album_id}...")

            if JM_AVAILABLE:
                # 使用官方API进行整本下载（同步调用）
                option = self.option if self.option else jmcomic.JmOption.default()
                # 切换到用户选择的工作目录，确保生成在该目录下
                old_cwd = os.getcwd()
                # 记录EXE目录（PyInstaller下 sys.executable 所在目录）
                exe_dir = Path(getattr(sys, 'frozen', False) and os.path.dirname(sys.executable) or old_cwd)
                try:
                    if self.workspace_dir:
                        os.makedirs(self.workspace_dir, exist_ok=True)
                        os.chdir(self.workspace_dir)
                    # 直接调用下载接口，保存目录由option指定的workspace控制
                    jmcomic.download_album(self.album_id, option)
                finally:
                    try:
                        os.chdir(old_cwd)
                    except Exception:
                        pass

                # 下载完成
                self.progress_updated.emit(100, 100)
                # 纠错：若库仍将内容写到了EXE目录的 JMComic 下，则迁移到目标 workspace/JMComic
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
                                    # 合并内容
                                    for root, dirs, files in os.walk(s):
                                        rel = Path(root).relative_to(s)
                                        (d / rel).mkdir(parents=True, exist_ok=True)
                                        for f in files:
                                            shutil.move(str(Path(root) / f), str(d / rel / f))
                                    shutil.rmtree(s, ignore_errors=True)
                            else:
                                shutil.move(str(s), str(d))
                        # 若空则删除源
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
                                # 合并目录/文件
                                if s.is_dir():
                                    for root, dirs, files in os.walk(s):
                                        rel = Path(root).relative_to(s)
                                        (d / rel).mkdir(parents=True, exist_ok=True)
                                        for f in files:
                                            shutil.move(str(Path(root) / f), str(d / rel / f))
                                    shutil.rmtree(s, ignore_errors=True)
                                else:
                                    # 文件重名则追加后缀
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
                # 模拟下载过程
                for i in range(101):
                    if not self.is_running:
                        break
                    self.progress_updated.emit(i, 100)
                    self.msleep(50)
                self.download_finished.emit(True, f"模拟下载完成 (ID: {self.album_id})")

        except Exception as e:
            self.download_finished.emit(False, f"下载失败: {str(e)}")

    def stop(self):
        """停止下载"""
        self.is_running = False


class CoverLoadThread(QThread):
    """封面加载线程"""
    loaded = pyqtSignal(int, object)  # row, QPixmap or None

    def __init__(self, row: int, url: str, proxy: str = "", timeout: int = 15):
        super().__init__()
        self.row = row
        self.url = url
        self.proxy = proxy
        self.timeout = timeout

    def run(self):
        try:
            if not SCRAPER_AVAILABLE or not self.url:
                self.loaded.emit(self.row, None)
                return
            proxies = None
            if self.proxy and (self.proxy.startswith("http://") or self.proxy.startswith("https://")):
                proxies = {"http": self.proxy, "https": self.proxy}
            scraper = cloudscraper.create_scraper()
            resp = scraper.get(self.url, timeout=self.timeout, proxies=proxies)
            if resp.status_code != 200:
                self.loaded.emit(self.row, None)
                return
            data = resp.content
            pix = QPixmap()
            if pix.loadFromData(data):
                self.loaded.emit(self.row, pix)
            else:
                self.loaded.emit(self.row, None)
        except Exception:
            self.loaded.emit(self.row, None)


class SearchThread(QThread):
    """搜索线程类"""
    search_finished = pyqtSignal(list, str)

    def __init__(self, keyword: str, search_type: str = "album", page: int = 1, proxy: str = "", timeout: int = 30):
        super().__init__()
        self.keyword = keyword
        self.search_type = search_type
        self.page = max(1, int(page) if isinstance(page, int) else 1)
        self.proxy = proxy.strip() if proxy else ""
        self.timeout = int(timeout) if timeout else 30

    def run(self):
        """执行搜索"""
        try:
            # 如果输入是纯数字，则作为专辑ID展示一个可下载条目
            kw = self.keyword.strip()
            if kw.isdigit():
                self.search_finished.emit([
                    {
                        'id': kw,
                        'title': f'专辑 {kw}',
                        'author': '-',
                        'tags': [],
                        'score': '-'
                    }
                ], "")
                return

            # 实际网站抓取搜索
            results = self._scrape_search(kw, self.page)
            self.search_finished.emit(results, "")

        except Exception as e:
            self.search_finished.emit([], f"搜索失败: {str(e)}")

    def _scrape_search(self, keyword: str, page: int) -> List[Dict]:
        """抓取站点搜索结果，返回标准化的漫画项列表"""
        if not SCRAPER_AVAILABLE:
            return []

        # 备用域名按顺序尝试
        bases = [
            "https://18comic.vip",
            "https://18comic.org",
            "https://jmcomic1.me",
            "https://jmcomic.me",
        ]

        # 代理
        proxies = None
        if self.proxy and (self.proxy.startswith("http://") or self.proxy.startswith("https://")):
            proxies = {"http": self.proxy, "https": self.proxy}

        try:
            scraper = cloudscraper.create_scraper()
        except Exception:
            return []

        query = quote_plus(keyword)
        last_err = None

        for base in bases:
            try:
                url = f"{base}/search/photos?search_query={query}&page={page}"
                resp = scraper.get(url, timeout=self.timeout, proxies=proxies)
                if resp.status_code != 200 or not resp.text:
                    last_err = f"HTTP {resp.status_code}"
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")

                anchors = soup.find_all('a', href=re.compile(r"/album/\d+"))
                seen = set()
                items: List[Dict] = []
                for a in anchors:
                    href = a.get('href') or ""
                    m = re.search(r"/album/(\d+)", href)
                    if not m:
                        continue
                    album_id = m.group(1)
                    if album_id in seen:
                        continue
                    seen.add(album_id)

                    title = a.get('title') or a.get_text(strip=True) or f"专辑 {album_id}"
                    # 查找卡片容器（向上寻找含有图片或元信息的父级）
                    card = a
                    for _ in range(3):
                        if card and not card.find('img'):
                            card = card.parent
                    # 查找封面
                    img_tag = (card.find('img') if card else None) or a.find('img') or (a.parent.find('img') if a.parent else None)
                    cover_url = None
                    if img_tag:
                        cover_url = img_tag.get('data-original') or img_tag.get('src') or None
                        if cover_url:
                            if cover_url.startswith('//'):
                                cover_url = 'https:' + cover_url
                            elif cover_url.startswith('/'):
                                cover_url = base.rstrip('/') + cover_url
                    # 解析作者、标签、评分（启发式）
                    author = '-'
                    score = '-'
                    tags: List[str] = []
                    if card:
                        # 常见作者链接样式
                        author_a = card.find('a', href=re.compile(r"/search/.*(author|artist|uploader).*"))
                        if author_a and author_a.get_text(strip=True):
                            author = author_a.get_text(strip=True)
                        # 标签常见样式：badge/label
                        for tag_el in card.find_all(['a','span'], class_=re.compile(r"(badge|tag|category)")):
                            t = tag_el.get_text(strip=True)
                            if t and len(tags) < 6:
                                tags.append(t)
                        # 评分常见样式：包含星星或数字
                        score_el = card.find(['span','div'], class_=re.compile(r"(score|rating)"))
                        if score_el:
                            st = score_el.get_text(strip=True)
                            if st:
                                score = st

                    items.append({
                        'id': album_id,
                        'title': title,
                        'author': author or '-',
                        'tags': tags,
                        'score': score or '-',
                        'cover': cover_url or ''
                    })

                if items:
                    return items
            except Exception as e:
                last_err = str(e)
                continue

        return []


class MangaViewer(QWidget):
    """漫画阅读器组件"""

    def __init__(self):
        super().__init__()

        self.current_manga_path = None
        self.current_page = 0
        self.total_pages = 0
        self.image_files = []
        self.setup_ui()

    def setup_ui(self):
        """设置阅读器界面"""
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QHBoxLayout()

        self.prev_btn = QPushButton("上一页")
        self.prev_btn.clicked.connect(self.previous_page)
        toolbar.addWidget(self.prev_btn)

        self.page_label = QLabel("0 / 0")
        self.page_label.setAlignment(Qt.AlignCenter)
        toolbar.addWidget(self.page_label)

        self.next_btn = QPushButton("下一页")
        self.next_btn.clicked.connect(self.next_page)
        toolbar.addWidget(self.next_btn)

        self.jump_input = QLineEdit()
        self.jump_input.setPlaceholderText("跳转到页码")
        self.jump_input.returnPressed.connect(self.jump_to_page)
        toolbar.addWidget(self.jump_input)

        toolbar.addStretch()

        layout.addLayout(toolbar)

        # 图片显示区域
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 300)

        scroll_area = QScrollArea()
        scroll_area.setWidget(self.image_label)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

    def load_manga(self, manga_path: str):
        """加载漫画"""
        self.current_manga_path = manga_path
        self.image_files = []

        # 扫描图片文件
        if os.path.exists(manga_path):
            for file in sorted(os.listdir(manga_path)):
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    self.image_files.append(os.path.join(manga_path, file))

        self.total_pages = len(self.image_files)
        self.current_page = 0

        if self.total_pages > 0:
            self.show_page(0)
        else:
            self.image_label.setText("未找到图片文件")

        self.update_page_info()

    def show_page(self, page_num: int):
        """显示指定页面"""
        if 0 <= page_num < self.total_pages:
            image_path = self.image_files[page_num]
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # 缩放图片以适应窗口
                scaled_pixmap = pixmap.scaled(
                    self.image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
            else:
                self.image_label.setText("无法加载图片")

    def previous_page(self):
        """上一页"""
        if self.current_page > 0:
            self.current_page -= 1
            self.show_page(self.current_page)
            self.update_page_info()

    def next_page(self):
        """下一页"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.show_page(self.current_page)
            self.update_page_info()

    def jump_to_page(self):
        """跳转到指定页面"""
        try:
            page_num = int(self.jump_input.text()) - 1
            if 0 <= page_num < self.total_pages:
                self.current_page = page_num
                self.show_page(self.current_page)
                self.update_page_info()
                self.jump_input.clear()
        except ValueError:
            pass

    def update_page_info(self):
        """更新页面信息"""
        self.page_label.setText(f"{self.current_page + 1} / {self.total_pages}")
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < self.total_pages - 1)


class JMComicDownloader(QMainWindow):
    """主窗口类"""

    def create_jm_option(self, workspace: Optional[str] = None):
        """创建JMComic下载选项，workspace为保存根目录（包含JMComic子目录）"""
        if not JM_AVAILABLE:
            return None
        # 如果指定了workspace，则生成一个临时的option.yml并加载
        if workspace:
            try:
                # 若用户选择的就是 JMComic 目录，向上取父级作为 workspace，避免嵌套 JMComic/JMComic
                ws_path = Path(workspace)
                if ws_path.name.lower() == 'jmcomic':
                    ws_path = ws_path.parent
                option_yml = self.config_dir / 'option.yml'
                # 写入最小配置，仅设置工作空间目录
                yml_content = (
                    "log: true\n"
                    "path:\n"
                    f"  workspace: {str(ws_path).replace('\\', '/')}\n"
                )
                with open(option_yml, 'w', encoding='utf-8') as f:
                    f.write(yml_content)
                option = jmcomic.create_option_by_file(str(option_yml))
                return option
            except Exception:
                # 失败则回退默认配置
                pass

        # 使用默认配置
        option = jmcomic.JmOption.default()
        return option

    def __init__(self):
        super().__init__()
        self.download_thread = None
        self.search_thread = None
        self.download_queue = []
        self.is_downloading = False
        self.first_run = False

        # 配置文件夹
        self.config_dir = Path.home() / ".jmcomic_downloader"
        self.config_dir.mkdir(exist_ok=True)

        # 下载文件夹（默认值，会在load_settings中根据配置覆盖）
        self.download_dir = Path.home() / "Downloads" / "JMComic"
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.setup_ui()
        self.load_settings()
        self.apply_dark_theme()

    def get_resource_path(self, relative: str) -> str:
        """获取资源路径，兼容PyInstaller打包后的临时目录"""
        base_path = getattr(sys, '_MEIPASS', os.path.abspath(".."))
        return os.path.join(base_path, relative)

    def setup_ui(self):
        """设置用户界面"""
        self.setWindowTitle("JMComic 漫画下载器")
        self.setGeometry(100, 100, 1200, 800)

        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # 创建标签页
        self.tab_widget = QTabWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.addWidget(self.tab_widget)

        # 创建各个功能页面
        self.create_search_tab()
        self.create_download_tab()
        self.create_library_tab()
        self.create_settings_tab()

        # 创建菜单栏
        self.create_menu_bar()

        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def create_search_tab(self):
        """创建搜索标签页"""
        search_widget = QWidget()
        layout = QVBoxLayout(search_widget)

        # 搜索区域
        search_group = QGroupBox("搜索漫画")
        search_layout = QHBoxLayout(search_group)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入漫画名称、作者或标签...")
        self.search_input.returnPressed.connect(self.search_manga)
        search_layout.addWidget(self.search_input)

        self.search_type_combo = QComboBox()
        self.search_type_combo.addItems(["专辑", "作者", "标签"])
        search_layout.addWidget(self.search_type_combo)

        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self.search_manga)
        search_layout.addWidget(self.search_btn)

        layout.addWidget(search_group)

        # 搜索结果表格
        self.search_table = QTableWidget()
        self.search_table.setColumnCount(7)
        self.search_table.setHorizontalHeaderLabels(["封面", "ID", "标题", "作者", "标签", "评分", "操作"])
        self.search_table.horizontalHeader().setStretchLastSection(True)
        self.search_table.setSelectionBehavior(QTableWidget.SelectRows)
        # 固定封面列宽与行高，避免缩略图挤在一起
        self.search_table.verticalHeader().setDefaultSectionSize(120)
        self.search_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.search_table.setColumnWidth(0, 100)
        # 其他列自适应，操作列固定
        for col in range(1, 6):
            self.search_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Stretch)
        self.search_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.search_table.setColumnWidth(6, 96)
        layout.addWidget(self.search_table)

        # 分页与状态栏
        pager_layout = QHBoxLayout()
        self.prev_page_btn = QPushButton("上一页")
        self.prev_page_btn.clicked.connect(self.go_prev_page)
        pager_layout.addWidget(self.prev_page_btn)

        self.page_info_label = QLabel("第 1 页")
        self.page_info_label.setAlignment(Qt.AlignCenter)
        pager_layout.addWidget(self.page_info_label)

        self.next_page_btn = QPushButton("下一页")
        self.next_page_btn.clicked.connect(self.go_next_page)
        pager_layout.addWidget(self.next_page_btn)

        pager_layout.addStretch()
        layout.addLayout(pager_layout)

        # 初始化分页与防抖
        self.current_page = 1
        self.prev_page_btn.setEnabled(False)
        self.search_debounce = QTimer(self)
        self.search_debounce.setSingleShot(True)
        self.search_debounce.setInterval(400)
        self.search_debounce.timeout.connect(lambda: self.start_search(self.current_page))
        self.search_input.textChanged.connect(self.on_search_text_changed)

        self.tab_widget.addTab(search_widget, "🔍 搜索")

    def create_download_tab(self):
        """创建下载标签页"""
        download_widget = QWidget()
        layout = QVBoxLayout(download_widget)

        # 下载控制区域
        control_group = QGroupBox("下载控制")
        control_layout = QGridLayout(control_group)

        # 漫画ID输入
        control_layout.addWidget(QLabel("漫画ID:"), 0, 0)
        self.album_id_input = QLineEdit()
        self.album_id_input.setPlaceholderText("输入要下载的漫画ID...")
        control_layout.addWidget(self.album_id_input, 0, 1)

        # 下载路径
        control_layout.addWidget(QLabel("保存路径:"), 1, 0)
        path_layout = QHBoxLayout()
        self.download_path_input = QLineEdit(str(self.download_dir))

        path_layout.addWidget(self.download_path_input)
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_download_path)

        path_layout.addWidget(self.browse_btn)
        control_layout.addLayout(path_layout, 1, 1)

        # 下载按钮
        self.download_btn = QPushButton("开始下载")
        self.download_btn.clicked.connect(self.start_download)
        control_layout.addWidget(self.download_btn, 2, 1)

        layout.addWidget(control_group)

        # 下载队列
        queue_group = QGroupBox("下载队列")
        queue_layout = QVBoxLayout(queue_group)

        self.download_list = QListWidget()
        queue_layout.addWidget(self.download_list)

        layout.addWidget(queue_group)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # 日志输出
        self.log_output = QTextEdit()
        self.log_output.setMaximumHeight(150)
        layout.addWidget(self.log_output)

        self.tab_widget.addTab(download_widget, "⬇️ 下载")

    def create_library_tab(self):
        """创建漫画库标签页"""
        library_widget = QWidget()
        outer_layout = QVBoxLayout(library_widget)

        # 使用分隔器，居中强调阅读器
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：筛选 + 列表（窄）
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        filter_group = QGroupBox("筛选")
        filter_layout = QVBoxLayout(filter_group)
        self.category_combo = QComboBox()
        self.category_combo.addItems(["全部", "已下载", "正在下载", "收藏"])
        self.category_combo.currentTextChanged.connect(self.filter_manga)
        filter_layout.addWidget(self.category_combo)
        left_layout.addWidget(filter_group)

        self.manga_list = QListWidget()
        self.manga_list.itemClicked.connect(self.show_manga_details)
        left_layout.addWidget(self.manga_list)

        # 中间：阅读器（宽）
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        self.reader = MangaViewer()
        center_layout.addWidget(self.reader)

        # 右侧：详情（窄）
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self.manga_details = QGroupBox("漫画详情")
        details_layout = QVBoxLayout(self.manga_details)
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)
        btn_layout = QHBoxLayout()
        self.read_btn = QPushButton("阅读")
        self.read_btn.clicked.connect(self.open_manga_reader)
        btn_layout.addWidget(self.read_btn)
        self.delete_btn = QPushButton("删除")
        self.delete_btn.clicked.connect(self.delete_manga)
        btn_layout.addWidget(self.delete_btn)
        details_layout.addLayout(btn_layout)
        right_layout.addWidget(self.manga_details)

        splitter.addWidget(left_widget)
        splitter.addWidget(center_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([200, 700, 260])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        outer_layout.addWidget(splitter)

        self.tab_widget.addTab(library_widget, "📚 漫画库")

    def create_settings_tab(self):
        """创建设置标签页"""
        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)

        # 下载设置
        download_group = QGroupBox("下载设置")
        download_layout = QGridLayout(download_group)

        # 线程数设置
        download_layout.addWidget(QLabel("同时下载线程数:"), 0, 0)
        self.thread_count_spin = QSpinBox()
        self.thread_count_spin.setRange(1, 10)
        self.thread_count_spin.setValue(3)
        download_layout.addWidget(self.thread_count_spin, 0, 1)

        # 重试次数
        download_layout.addWidget(QLabel("重试次数:"), 1, 0)
        self.retry_count_spin = QSpinBox()
        self.retry_count_spin.setRange(1, 5)
        self.retry_count_spin.setValue(3)
        download_layout.addWidget(self.retry_count_spin, 1, 1)

        # 图片格式
        download_layout.addWidget(QLabel("图片格式:"), 2, 0)
        self.image_format_combo = QComboBox()
        self.image_format_combo.addItems(["原始格式", "JPG", "PNG", "WEBP"])
        download_layout.addWidget(self.image_format_combo, 2, 1)

        layout.addWidget(download_group)

        # 界面设置
        ui_group = QGroupBox("界面设置")
        ui_layout = QGridLayout(ui_group)

        # 主题选择
        ui_layout.addWidget(QLabel("主题:"), 0, 0)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["深色主题", "浅色主题"])
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        ui_layout.addWidget(self.theme_combo, 0, 1)

        # 自动检查更新
        self.auto_update_check = QCheckBox("自动检查更新")
        self.auto_update_check.setChecked(True)
        ui_layout.addWidget(self.auto_update_check, 1, 0, 1, 2)

        layout.addWidget(ui_group)

        # 网络设置
        network_group = QGroupBox("网络设置")
        network_layout = QGridLayout(network_group)

        # 代理设置
        network_layout.addWidget(QLabel("HTTP代理:"), 0, 0)
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("例如: http://127.0.0.1:7890")
        network_layout.addWidget(self.proxy_input, 0, 1)

        # 超时时间
        network_layout.addWidget(QLabel("超时时间(秒):"), 1, 0)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 60)
        self.timeout_spin.setValue(30)
        network_layout.addWidget(self.timeout_spin, 1, 1)

        layout.addWidget(network_group)

        # 保存按钮
        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()

        self.tab_widget.addTab(settings_widget, "⚙️ 设置")

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu('文件')

        open_action = QAction('打开下载文件夹', self)
        open_action.triggered.connect(self.open_download_folder)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction('退出', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 工具菜单
        tools_menu = menubar.addMenu('工具')

        clear_cache_action = QAction('清理缓存', self)
        clear_cache_action.triggered.connect(self.clear_cache)
        tools_menu.addAction(clear_cache_action)

        # 帮助菜单
        help_menu = menubar.addMenu('帮助')

        about_action = QAction('关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def apply_dark_theme(self):
        """应用深色主题"""
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)

        self.setPalette(dark_palette)

        # 设置样式表
        self.setStyleSheet("""
            QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }
            QPushButton { background-color: #2a82da; border: none; color: white; padding: 5px 15px; }
            QPushButton:hover { background-color: #3a92ea; }
            QPushButton:pressed { background-color: #1a72ca; }
            QLineEdit { background-color: #2b2b2b; border: 1px solid #555; color: white; padding: 5px; }
            QTextEdit { background-color: #2b2b2b; border: 1px solid #555; color: white; }
            QTableWidget { background-color: #2b2b2b; border: 1px solid #555; color: white; }
            QHeaderView::section { background-color: #353535; color: white; border: 1px solid #555; }
            QProgressBar { border: 1px solid #555; border-radius: 3px; text-align: center; }
            QProgressBar::chunk { background-color: #2a82da; }
        """)

    def change_theme(self, theme_name: str):
        """切换主题"""
        if theme_name == "浅色主题":
            self.setPalette(QApplication.palette())
            self.setStyleSheet("")
        else:
            self.apply_dark_theme()

    def search_manga(self):
        """搜索漫画"""
        keyword = self.search_input.text().strip()
        if not keyword:
            QMessageBox.warning(self, "警告", "请输入搜索关键词")
            return
        # 重置到第一页并开始搜索
        self.current_page = 1
        self.start_search(self.current_page)

    def start_search(self, page: int):
        """开始执行搜索，支持分页"""
        keyword = self.search_input.text().strip()
        if not keyword:
            return
        self.search_btn.setEnabled(False)
        self.status_bar.showMessage(f"正在搜索: {keyword}（第 {page} 页）")
        # 启动搜索线程，支持分页参数
        proxy = self.proxy_input.text().strip() if hasattr(self, 'proxy_input') else ""
        timeout = self.timeout_spin.value() if hasattr(self, 'timeout_spin') else 30
        self.search_thread = SearchThread(keyword, page=page, proxy=proxy, timeout=timeout)
        self.search_thread.search_finished.connect(self.on_search_finished)
        self.search_thread.start()

    def on_search_finished(self, results: List[Dict], error: str):
        """搜索完成回调"""
        self.search_btn.setEnabled(True)

        if error:
            QMessageBox.warning(self, "搜索失败", error)
            self.status_bar.showMessage("搜索失败")
            return

        # 更新搜索结果表格
        self.search_table.setRowCount(len(results))

        # 确保封面相关缓存与线程容器
        if not hasattr(self, 'cover_cache'):
            self.cover_cache = {}
        if not hasattr(self, '_cover_threads'):
            self._cover_threads = []
        if not hasattr(self, 'cover_row_url'):
            self.cover_row_url = {}

        for row, manga in enumerate(results):
            # 封面
            cover_label = QLabel()
            cover_label.setAlignment(Qt.AlignCenter)
            cover_label.setFixedSize(80, 110)
            cover_label.setText("加载中")
            self.search_table.setCellWidget(row, 0, cover_label)

            cover_url = manga.get('cover', '')
            if cover_url:
                self._load_cover_async(row, cover_url)

            # ID
            self.search_table.setItem(row, 1, QTableWidgetItem(manga['id']))

            # 标题
            self.search_table.setItem(row, 2, QTableWidgetItem(manga['title']))

            # 作者
            self.search_table.setItem(row, 3, QTableWidgetItem(manga['author']))

            # 标签
            tags = ', '.join(manga['tags'])
            self.search_table.setItem(row, 4, QTableWidgetItem(tags))

            # 评分
            self.search_table.setItem(row, 5, QTableWidgetItem(manga['score']))

            # 下载按钮
            download_btn = QPushButton("下载")
            download_btn.clicked.connect(lambda checked, mid=manga['id']: self.add_to_download_queue(mid))
            self.search_table.setCellWidget(row, 6, download_btn)

        self.status_bar.showMessage(f"搜索完成，找到 {len(results)} 个结果")
        self.update_pagination_ui()

    def _load_cover_async(self, row: int, url: str):
        """异步加载封面到表格单元格"""
        # 命中缓存
        if url in self.cover_cache:
            pix: QPixmap = self.cover_cache[url]
            self._set_cover_pixmap(row, pix)
            return
        proxy = self.proxy_input.text().strip() if hasattr(self, 'proxy_input') else ""
        timeout = self.timeout_spin.value() if hasattr(self, 'timeout_spin') else 15
        # 记录行到URL的映射以便缓存
        self.cover_row_url[row] = url
        t = CoverLoadThread(row=row, url=url, proxy=proxy, timeout=timeout)
        t.loaded.connect(self._on_cover_loaded)
        self._cover_threads.append(t)
        t.start()

    def _on_cover_loaded(self, row: int, pix: object):
        label = self.search_table.cellWidget(row, 0)
        if isinstance(pix, QPixmap):
            # 写入缓存
            url = None
            if hasattr(self, 'cover_row_url'):
                url = self.cover_row_url.get(row)
            if url:
                self.cover_cache[url] = pix
            self._set_cover_pixmap(row, pix)
        else:
            if isinstance(label, QLabel):
                label.setText("-")

    def _set_cover_pixmap(self, row: int, pix: QPixmap):
        label = self.search_table.cellWidget(row, 0)
        if not isinstance(label, QLabel):
            return
        target = pix.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(target)

    def go_prev_page(self):
        """上一页"""
        if getattr(self, 'current_page', 1) > 1:
            self.current_page -= 1
            self.start_search(self.current_page)

    def go_next_page(self):
        """下一页"""
        self.current_page = getattr(self, 'current_page', 1) + 1
        self.start_search(self.current_page)

    def update_pagination_ui(self):
        """更新分页按钮与信息显示"""
        page = getattr(self, 'current_page', 1)
        self.page_info_label.setText(f"第 {page} 页")
        self.prev_page_btn.setEnabled(page > 1)

    def on_search_text_changed(self, _text: str):
        """搜索框文本变更防抖处理"""
        self.current_page = 1
        # 仅在非空时触发防抖
        if self.search_input.text().strip():
            self.search_debounce.start()
        else:
            self.search_debounce.stop()

    def add_to_download_queue(self, manga_id: str):
        """添加到下载队列"""
        # 检查是否已在队列中
        for i in range(self.download_list.count()):
            item = self.download_list.item(i)
            if item and manga_id in item.text():
                QMessageBox.information(self, "提示", "该漫画已在下载队列中")
                return

        # 添加到队列
        item = QListWidgetItem(f"漫画ID: {manga_id}")
        self.download_list.addItem(item)
        self.download_queue.append(manga_id)

        self.status_bar.showMessage(f"已添加漫画 {manga_id} 到下载队列")

    def start_download(self):
        """开始下载"""
        if self.is_downloading:
            QMessageBox.information(self, "提示", "正在下载中，请稍候...")
            return

        # 检查是否有下载任务
        if self.download_queue:
            manga_id = self.download_queue.pop(0)
        else:
            manga_id = self.album_id_input.text().strip()
            if not manga_id:
                QMessageBox.warning(self, "警告", "请输入漫画ID或添加下载队列")
                return

        # 获取保存路径（首次下载时引导选择）
        save_path = self.download_path_input.text().strip()
        if not save_path:
            save_path = str(self.download_dir)

        # 首次运行：提示选择保存路径，用户可取消
        if self.first_run:
            chosen = QFileDialog.getExistingDirectory(self, "选择漫画保存位置（会创建JMComic文件夹）", str(Path.home() / "Downloads"))
            if chosen:
                base_dir = Path(chosen)
            else:
                base_dir = Path.home() / "Downloads"
            self.first_run = False
        else:
            base_dir = Path(save_path) if save_path else (Path.home() / "Downloads")
            if not base_dir.exists():
                base_dir = Path.home() / "Downloads"
        # 使用用户选择的目录本身作为工作目录（不再创建 JMComic 子目录）
        base_dir.mkdir(parents=True, exist_ok=True)
        ws_path = base_dir
        self.download_dir = ws_path
        self.download_path_input.setText(str(self.download_dir))
        # 持久化设置（静默，不弹窗）
        self.save_settings(silent=True)

        # 创建JMComic选项，workspace=用户选择目录
        jm_option = self.create_jm_option(str(ws_path))

        # 创建下载线程
        self.is_downloading = True
        self.download_btn.setEnabled(False)
        # 设置为不确定进度（忙碌状态）
        self.progress_bar.setRange(0, 0)

        self.download_thread = DownloadThread(manga_id, save_path, jm_option, workspace_dir=str(ws_path))
        self.download_thread.progress_updated.connect(self.update_progress)
        self.download_thread.status_changed.connect(self.update_status)
        self.download_thread.download_finished.connect(self.on_download_finished)
        self.download_thread.start()

        self.log_output.append(f"开始下载漫画: {manga_id}")

    def update_progress(self, current: int, total: int):
        """更新下载进度"""
        if total == 0:
            # 不确定进度
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)

    def update_status(self, status: str):
        """更新状态信息"""
        self.log_output.append(status)
        self.status_bar.showMessage(status)

    def on_download_finished(self, success: bool, message: str):
        """下载完成回调"""
        self.is_downloading = False
        self.download_btn.setEnabled(True)

        if success:
            # 从下载列表中移除
            if self.download_list.count() > 0:
                self.download_list.takeItem(0)

            # 检查队列中的下一个任务
            if self.download_queue:
                QTimer.singleShot(2000, self.start_download)
            else:
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(100)

        self.log_output.append(message)
        self.status_bar.showMessage(message)

        QMessageBox.information(self, "下载完成", message)

        # 刷新漫画库
        self.refresh_library()

        

    def browse_download_path(self):
        """浏览下载路径"""
        path = QFileDialog.getExistingDirectory(self, "选择下载文件夹", str(self.download_dir))
        if path:
            chosen = Path(path)
            chosen.mkdir(parents=True, exist_ok=True)
            self.download_dir = chosen
            self.download_path_input.setText(str(self.download_dir))
            # 保存设置并刷新漫画库（静默）
            self.save_settings(silent=True)
            self.refresh_library()

    def open_download_folder(self):
        """打开下载文件夹"""
        path = self.download_path_input.text() or str(self.download_dir)
        if os.path.exists(path):
            os.startfile(path)
        else:
            QMessageBox.warning(self, "警告", "下载文件夹不存在")

    def filter_manga(self, category: str):
        """筛选漫画"""
        self.refresh_library()

    def show_manga_details(self, item: QListWidgetItem):
        """显示漫画详情"""
        manga_name = item.text()
        manga_path = os.path.join(str(self.download_dir), manga_name)

        if os.path.exists(manga_path):
            # 统计文件信息
            file_count = len([f for f in os.listdir(manga_path) if f.lower().endswith(('.jpg', '.png', '.gif'))])
            total_size = sum(os.path.getsize(os.path.join(manga_path, f)) for f in os.listdir(manga_path))

            details = f"""
漫画名称: {manga_name}
文件路径: {manga_path}
图片数量: {file_count} 张
总大小: {total_size / 1024 / 1024:.2f} MB
状态: 已下载
            """

            self.details_text.setText(details)

            # 启用阅读按钮
            self.read_btn.setEnabled(True)
            self.current_manga_path = manga_path
        else:
            self.details_text.setText("漫画信息加载失败")
            self.read_btn.setEnabled(False)

    def open_manga_reader(self):
        """打开漫画阅读器"""
        if self.current_manga_path:
            self.reader.load_manga(self.current_manga_path)

    def delete_manga(self):
        """删除漫画"""
        if self.current_manga_path:
            reply = QMessageBox.question(self, "确认删除",
                                         f"确定要删除漫画吗？\n{self.current_manga_path}",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                import shutil
                try:
                    shutil.rmtree(self.current_manga_path)
                    QMessageBox.information(self, "成功", "漫画已删除")
                    self.refresh_library()
                except Exception as e:
                    QMessageBox.warning(self, "失败", f"删除失败: {str(e)}")

    def refresh_library(self):
        """刷新漫画库"""
        self.manga_list.clear()

        if os.path.exists(str(self.download_dir)):
            for item in os.listdir(str(self.download_dir)):
                item_path = os.path.join(str(self.download_dir), item)
                if os.path.isdir(item_path):
                    self.manga_list.addItem(item)

    def load_settings(self):
        """加载设置"""
        settings_file = self.config_dir / "settings.json"
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

                # 应用设置
                if 'download_path' in settings and settings['download_path']:
                    # 统一保证路径为JMComic根目录
                    dp = Path(settings['download_path'])
                    dp.mkdir(parents=True, exist_ok=True)
                    self.download_dir = dp
                    self.download_path_input.setText(str(self.download_dir))
                else:
                    # 没有保存路径，标记首次运行
                    self.first_run = True
                if 'thread_count' in settings:
                    self.thread_count_spin.setValue(settings['thread_count'])
                if 'theme' in settings:
                    self.theme_combo.setCurrentText(settings['theme'])
                

            except Exception as e:
                print(f"加载设置失败: {e}")
                # 若读取失败，也提示首次运行
                self.first_run = True
        else:
            # 未创建设置文件，首次运行
            self.first_run = True

    def save_settings(self, silent: bool = False):
        """保存设置"""
        settings = {
            'download_path': str(self.download_dir),
            'thread_count': self.thread_count_spin.value(),
            'retry_count': self.retry_count_spin.value(),
            'image_format': self.image_format_combo.currentText(),
            'theme': self.theme_combo.currentText(),
            'auto_update': self.auto_update_check.isChecked(),
            'proxy': self.proxy_input.text(),
            'timeout': self.timeout_spin.value()
        }

        settings_file = self.config_dir / "settings.json"
        try:
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            if not silent:
                QMessageBox.information(self, "成功", "设置已保存")
        except Exception as e:
            QMessageBox.warning(self, "失败", f"保存设置失败: {e}")

    def clear_cache(self):
        """清理缓存"""
        # 这里可以添加清理缓存的逻辑
        QMessageBox.information(self, "提示", "缓存清理功能待实现")

    def show_about(self):
        """显示关于对话框"""
        about_text = """
        <h2>JMComic 漫画下载器</h2>
        <p>版本: 1.0.0</p>
        <p>基于 PyQt5 和 JMComic API 开发的现代化漫画下载工具</p>
        <p>GitHub: <a href="https://github.com/hect0x7/JMComic-Crawler-Python">JMComic-Crawler-Python</a></p>
        <p> 2025 JMComic Downloader</p>
        """

        QMessageBox.about(self, "关于", about_text)

    def closeEvent(self, event):
        """关闭事件"""
        # 停止所有线程
        if self.download_thread and self.download_thread.isRunning():
            reply = QMessageBox.question(self, "确认退出",
                                         "正在下载中，确定要退出吗？",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                event.ignore()
                return
            # 请求线程停止（若为同步下载，可能需要等待当前任务结束）
            try:
                self.download_thread.stop()
            except Exception:
                pass
            self.download_thread.wait()

        # 保存设置
        self.save_settings()
        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 设置应用信息
    app.setApplicationName("JMComic Downloader")
    app.setOrganizationName("JMComic")

    # 检查JMComic库是否可用
    if not JM_AVAILABLE:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("依赖库缺失")
        msg.setText("未检测到jmcomic库，应用将以演示模式运行。\n\n"
                    "要启用完整功能，请安装jmcomic库:\n"
                    "pip install jmcomic")
        msg.exec_()

    # 创建并显示主窗口
    window = JMComicDownloader()
    window.show()

    # 启动应用
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()