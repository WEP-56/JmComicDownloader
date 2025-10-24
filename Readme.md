# JMCdownloader
- **[下载]**
  - 支持输入专辑 ID 下载，或从队列启动。
  - 队列管理：添加到队列、删除选中队列项。
  - 控制：开始下载、停止下载（尽力停止）。
  - 实时反馈：进度条、日志输出、状态栏提示。

- **[漫画库]**
  - 与“下载路径”强绑定，自动列出该目录下的漫画文件夹。
  - 详情：目录、文件数、大小；预览第一张图片。
  - 内置阅读器：
    - 上一页/下一页/页码跳转。
    - 滚轮翻页；←/→/PgUp/PgDn 翻页。
    - 双击切换“适应窗口/原始大小”。
    - 左键按住可拖拽查看，松开回弹（适应模式）。
    - 窗口变更自动重绘。
  - 操作：阅读（在应用内）、删除（移除选中目录）。

- **[设置]**
  - 下载设置：线程数、重试次数、图片格式（按库能力逐步穿透）。
  - 界面设置：当前固定浅色（白底黑字）保证可读性。
  - 网络设置：HTTP 代理、超时。
  - 设置持久化：`~/.jmcomic_downloader/settings.json`。

# 环境与安装

- Python 3.8+（Windows/macOS/Linux）
- 依赖：
  - PyQt5
  - cloudscraper
  - beautifulsoup4
  - jmcomic（用于实际下载）

安装命令（PowerShell 或 bash）：
```powershell
pip install PyQt5 cloudscraper beautifulsoup4
pip install jmcomic -i https://pypi.org/project -U   #jm api库下载

**[启动]**
python app/main.py
 首次运行会自动将下载目录初始化为 ~/Downloads/JMComic，可在“设置”中修改并保存。
 若遇到模块导入问题，
 app/main.py会将项目根目录加入 sys.path 以确保 ui/*、core/* 可导入。

**[使用指南]**
 - 搜索
在“搜索”页输入关键词 → 点击“搜索”。
每行结果右侧可“下载”（直接下载）或“添加”（加入队列）。
作者/标签/评分在表格相应列展示。
 - 下载
直接下载：在搜索结果行点击“下载”。
队列下载：下载页输入 ID → “添加到队列” → “开始下载”。
队列管理：选中后点击“删除选中”。
停止下载：点击“停止下载”（尽力终止，第三方库阻塞时可能无法立即停止）。
下载过程中按钮会禁用，完成后自动恢复，日志与状态栏会显示过程信息。
 - 漫画库/阅读器
与“下载路径”一致，启动/切换页签/修改路径时自动刷新。
左侧选择条目 → 点击“阅读”进入阅读器。
 - 交互：
滚轮/←/→/PgUp/PgDn 翻页。
双击切换适应/原图。
左键拖拽查看（松开回弹，适应模式生效）。
窗口大小变化自动重绘当页图片。
设置
下载、界面、网络三类设置，点击“保存设置”立即生效并持久化。
主要实现说明
界面加载
ui/bindings.py: MainWindow.init()
 使用 loadUi 加载 
ui/MainWindow.ui
，完成控件查找/信号绑定/初始状态设置。
搜索线程
core/search_worker.py: SearchWorker 使用 cloudscraper 请求、BeautifulSoup 解析。
子线程仅返回封面二进制数据；主线程 
_on_cover_loaded()
 构造 QPixmap，避免线程违规。
ui/bindings.py
 中顺序插入结果行，每行封面加载完成后再处理下一行，显著降低 UI 卡顿。
下载线程
core/download_worker.py: DownloadWorker 调用 jmcomic.download_album()。
切换工作目录到目标下载路径；下载完成后进行纠偏迁移（如内容误写到 EXE 同级 JMComic 下）与扁平化整理。
_start_download()
 仅在下载线程成功启动后才移除队列首项，失败会在状态栏和日志输出明确信息。
设置存储
core/settings_store.py
 读写 ~/.jmcomic_downloader/settings.json，提供下载/网络/UI 参数的 get/set。
启动时加载设置，保存时立即生效（包括主题应用与漫画库刷新）。
JMComic 选项
core/jm_option.py
 为兼容不同版本的 jmcomic，返回 JmOption.default()；下载落地路径通过 
DownloadWorker
 的工作目录切换与后续迁移保证正确。
资源辅助
core/resources.py
 提供 
get_resource_path()
 定位资源与 .ui 文件。
项目结构
e:/PICDOWNLOADER/
├─ app/
│  └─ main.py                  # 程序入口：修正 sys.path，加载主窗体
├─ core/
│  ├─ download_worker.py       # 下载线程（jmcomic 集成、迁移与扁平化）
│  ├─ jm_option.py             # jmcomic 选项创建（版本兼容）
│  ├─ search_worker.py         # 搜索线程（爬取/解析/返回结果）
│  ├─ settings_store.py        # 设置读写（JSON）
│  └─ resources.py             # 资源路径辅助
├─ ui/
│  ├─ MainWindow.ui            # 主界面（Qt Designer 可编辑）
│  └─ bindings.py              # UI 与逻辑绑定（信号/线程/状态）
├─ jmcomic_downloader.py       # 旧版单文件（对照参考，不作为入口）
└─ readme.md                   # 说明文档（本文件）


常见问题（FAQ）
封面不显示/搜索失败
安装 cloudscraper、beautifulsoup4；在“设置”中配置合适的 HTTP 代理与超时。
下载不开始/失败
安装 jmcomic：pip install jmcomic；检查“保存路径”是否存在；查看右侧日志与底部状态栏提示。
停止下载不生效
第三方库内部可能阻塞；当前实现为“尽力停止”。如需更强控制，可改为子进程下载并用 IPC 管控。
漫画库空白
漫画库与“下载路径”强绑定。修改路径或切换到漫画库页会自动刷新；启动时也会刷新。

开发
安装依赖：
powershell
pip install PyQt5 cloudscraper beautifulsoup4 jmcomic
UI 建议通过 Qt Designer 修改 
ui/MainWindow.ui
，再在 
ui/bindings.py
 绑定事件与逻辑；遵循 PEP 8 代码风格。

打包与发布
pip install pyinstaller

pyinstaller `
  --name JMComicDownloader `
  --icon favicon.ico `
  --onedir `
  --noconsole `
  --noconfirm `
  --clean `
  --paths e:\PICDOWNLOADER `
  --add-data "e:\PICDOWNLOADER\ui\MainWindow.ui;ui" `
  e:\PICDOWNLOADER\app\main.py

致谢
JMComic-Crawler-Python
PyQt5 社区
帮我测试的好兄弟@6DK