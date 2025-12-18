import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QCheckBox, QPushButton, QFileDialog, QScrollArea, QMessageBox, QGroupBox, QTabWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

class ParamRow(QWidget):
    def __init__(self, name, line, pos, group=None, phase=None, parent=None):
        super().__init__(parent)
        # 名称小写并在有 phase 时追加后缀，如 scale_1
        self.name = name.lower() if phase is None else f"{name.lower()}_{phase}"
        self.line = line
        self.pos = pos
        self.group = group
        self.phase = phase
        layout = QHBoxLayout()
        # 显示时直接展示按定位逻辑得到的行/列值（即显示存储的值）
        layout.addWidget(QLabel(f"{self.name} (line {self.line}, pos {self.pos})"))
        self.min_edit = QLineEdit()
        self.min_edit.setPlaceholderText("最小值")
        self.max_edit = QLineEdit()
        self.max_edit.setPlaceholderText("最大值")
        self.checkbox = QCheckBox("启用监控")
        layout.addWidget(self.min_edit)
        layout.addWidget(self.max_edit)
        layout.addWidget(self.checkbox)
        self.setLayout(layout)

    def get_setting(self):
        if self.checkbox.isChecked():
            try:
                minv = float(self.min_edit.text())
                maxv = float(self.max_edit.text())
                return {
                    "name": self.name,
                    "line": self.line,
                    "position": self.pos,
                    "min": minv,
                    "max": maxv
                }
            except Exception:
                return None
        return None

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PCR原子参数监控阈值设置")
        self.resize(800, 600)
        self.param_rows = []
        self.json_data = None

        main_layout = QVBoxLayout()
        btn_layout = QHBoxLayout()
        self.load_btn = QPushButton("加载JSON文件")
        self.export_btn = QPushButton("导出监控配置")
        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.export_btn)
        main_layout.addLayout(btn_layout)

        # 添加 tab widget 用于展示每个 phase（每个 phase 一个 tab）
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 保留底部的滚动区域用于显示没有 phase 的参数（如仪器/背底）
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.param_widget = QWidget()
        self.param_layout = QVBoxLayout()
        self.param_widget.setLayout(self.param_layout)
        self.scroll.setWidget(self.param_widget)
        main_layout.addWidget(self.scroll)

        self.setLayout(main_layout)

        self.load_btn.clicked.connect(self.load_json)
        self.export_btn.clicked.connect(self.export_config)

    def load_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择JSON文件", "", "JSON Files (*.json)")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            self.json_data = json.load(f)
        # 清空原有控件（滚动区域内）和 tabs
        for i in reversed(range(self.param_layout.count())):
            widget = self.param_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        self.tab_widget.clear()
        self.param_rows = []

        # 按 phase 和 group 分组
        phases = {}         # { phase_int: { group_name: [ParamRow,...], ... }, ... }
        non_phase = {}      # { group_name: [ParamRow,...], ... }

        for param in self.json_data.get("parameters_library", []):
            if "line" in param and "position" in param and "name" in param:
                group_name = param.get("group", "其他")
                phase = param.get("phase", None)
                display_name = param["name"]
                # 默认：非特殊参数按原逻辑 line = json_line - 1, pos = json_position
                name_l = param["name"].lower()
                special_names = {"zero", "dtt1", "dtt2", "dtt_1overd", "abs1", "abs2"}
                if name_l in special_names or name_l.startswith("bg"):
                    # 特殊参数：line 与 JSON 相同（不减1），列为 JSON 列号 - 1
                    raw_line = param["line"]
                    raw_pos = param["position"] - 1
                else:
                    # 其他参数保持原有逻辑
                    raw_line = param["line"] - 1
                    raw_pos = param["position"]
                # 防止出现负值（若 json 出错）
                if raw_pos < 0:
                    raw_pos = 0
                row = ParamRow(display_name, raw_line, raw_pos, group=group_name, phase=phase)
                if phase is None:
                    non_phase.setdefault(group_name, []).append(row)
                else:
                    phases.setdefault(phase, {}).setdefault(group_name, []).append(row)

        # 将非 phase 参数（仪器/背底等）显示在滚动区域
        for group_name, rows in non_phase.items():
            group_box = QGroupBox(group_name)
            gb_layout = QVBoxLayout()
            for r in rows:
                gb_layout.addWidget(r)
                self.param_rows.append(r)
            group_box.setLayout(gb_layout)
            self.param_layout.addWidget(group_box)

        # 为每个 phase 创建一个 tab（tab 内使用滚动区域）
        for phase in sorted(phases.keys()):
            tab = QWidget()
            tab_layout = QVBoxLayout()
            group_dict = phases[phase]
            # 保持 group 顺序可按需要调整，这里按字典顺序
            for group_name, rows in group_dict.items():
                group_box = QGroupBox(group_name)
                gb_layout = QVBoxLayout()
                for r in rows:
                    gb_layout.addWidget(r)
                    self.param_rows.append(r)
                group_box.setLayout(gb_layout)
                tab_layout.addWidget(group_box)
            tab_layout.addStretch()
            tab_content = QWidget()
            tab_content.setLayout(tab_layout)
            tab_scroll = QScrollArea()
            tab_scroll.setWidgetResizable(True)
            tab_scroll.setWidget(tab_content)
            self.tab_widget.addTab(tab_scroll, f"phase{phase}")

    def export_config(self):
        settings = []
        for row in self.param_rows:
            setting = row.get_setting()
            if setting is not None:
                settings.append(setting)
        if not settings:
            QMessageBox.warning(self, "提示", "没有启用任何参数监控！")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出为py文件", "PCR_check_gui_export.py", "Python Files (*.py)")
        if not path:
            return
        # 生成py文件
        with open(path, "w", encoding="utf-8") as f:
            f.write("# 由PCR_check_gui.py自动生成\n")
            f.write("import sys\n\n")
            f.write("PARAM_LIMITS = [\n")
            for s in settings:
                f.write(f"    {repr(s)},\n")
            f.write("]\n\n")
            f.write('''\
def check_pcr_limits(pcr_file):
            """
            检查pcr文件中PARAM_LIMITS中所有参数是否超出范围
            返回: 错误信息列表（如无超限则返回空列表）
            """
            try:
                with open(pcr_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except Exception as e:
                return [f"无法读取pcr文件: {e}"]
            errors = []
            for param in PARAM_LIMITS:
                # 说明：导出时 line 使用的是 1-based 行号，这里转换为 0-based 索引
                idx = param['line']
                pos = param['position']
                name = param['name']
                minv = param['min']
                maxv = param['max']
                idx0 = idx - 1
                if idx0 < 0 or idx0 >= len(lines):
                    errors.append(f"{name} 参数所在行 {idx} 超出pcr文件范围")
                    continue
                line = lines[idx0]
                if line.strip().startswith("!"):
                    errors.append(f"{name} 参数所在行 {idx} 是注释行")
                    continue
                parts = line.strip().split()
                if pos < 0 or pos >= len(parts):
                    errors.append(f"{name} 参数在第 {idx} 行的第 {pos} 列不存在")
                    continue
                try:
                    value = float(parts[pos])
                except Exception:
                    errors.append(f"{name} 参数在第 {idx} 行的第 {pos} 列无法转换为数值")
                    continue
                if not (minv <= value <= maxv):
                    errors.append(f"{name} 参数的值为 {value}，超出范围 {minv}~{maxv}")
            return errors
        
if __name__ == "__main__":
            if len(sys.argv) < 2:
                print("Usage: PCR_check_gui_export.py <pcr_file>")
                sys.exit(1)
            errs = check_pcr_limits(sys.argv[1])
            if errs:
                print("ERROR")
                for e in errs:
                    print(e)
                sys.exit(2)
            else:
                print("所有参数ok")
                sys.exit(0)
        ''')
        QMessageBox.information(self, "导出成功", f"已导出到 {path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("微软雅黑"))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())