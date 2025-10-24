import sys, os
from PyQt5.QtWidgets import QApplication

# 直接加载基于 .ui 的主窗口
def main():
    # 确保可以从项目根导入 ui/* 与 core/*
    project_root = os.path.dirname(os.path.dirname(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    app = QApplication(sys.argv)
    from ui.bindings import load_main_window
    window = load_main_window()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
