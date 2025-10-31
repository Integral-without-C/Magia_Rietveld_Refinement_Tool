import sys
import json
from collections import defaultdict
import re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTabWidget, QGroupBox, QCheckBox, QScrollArea, QTableWidget,
    QTableWidgetItem, QMessageBox, QHeaderView, QDoubleSpinBox, QAbstractItemView, QAbstractScrollArea, QLineEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPalette, QColor
from PyQt5.QtWidgets import QStyleFactory

'''
优化了GUI界面布局，精修步骤窗口独立显示，原子参数分类显示，字体优化，背景深色
'''

class StepTableWindow(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent  # Reference to main window for shared data and methods
        self.setWindowTitle("Steps Table")
        self.resize(1200, 500)  # Initial size, resizable
        layout = QVBoxLayout(self)
        
        # Step table
        self.step_table = QTableWidget()
        self.step_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.step_table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        self.step_table.setWordWrap(True)
        # Set to pixel scrolling
        self.step_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.step_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        # Optional, auto-adjust size policy
        self.step_table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        
        layout.addWidget(self.step_table)
        self.setLayout(layout)

class StepConfigGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Magia_Step_Generator_v1.0")
        self.resize(1200, 500)
        self.param_lib = []
        self.steps = []
        self.instrument_params = []
        self.bg_params = []
        self.phase_param_dict = defaultdict(list)
        self.phase_group_dict = defaultdict(lambda: defaultdict(list))
        self.current_step_length = 1.00
        self.param_id_map = {}
        self.init_ui()
        self.apply_dark_theme()  # 新增：应用深色主题
        # Create and show the separate table window
        self.table_window = StepTableWindow(self)
        self.table_window.show()

    def apply_dark_theme(self):
        # 设置深色样式表
        dark_stylesheet = """
        QWidget {
            background-color: #232629;
            color: #F0F0F0;
        }
        QGroupBox {
            border: 1px solid #444;
            margin-top: 10px;
        }
        QPushButton {
            background-color: #444;
            color: #F0F0F0;
            border: 1px solid #666;
            padding: 5px;
        }
        QPushButton:hover {
            background-color: #555;
        }
        QLineEdit, QDoubleSpinBox, QTabWidget, QTableWidget, QScrollArea {
            background-color: #2C2F33;
            color: #F0F0F0;
            border: 1px solid #444;
        }
        QHeaderView::section {
            background-color: #444;
            color: #F0F0F0;
        }
        QCheckBox {
            color: #F0F0F0;
        }
        QLabel {
            color: #F0F0F0;
        }
        """
        self.setStyleSheet(dark_stylesheet)
        QApplication.instance().setStyle(QStyleFactory.create("Fusion"))
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(35, 38, 41))
        palette.setColor(QPalette.WindowText, QColor(240, 240, 240))
        palette.setColor(QPalette.Base, QColor(44, 47, 51))
        palette.setColor(QPalette.AlternateBase, QColor(35, 38, 41))
        palette.setColor(QPalette.ToolTipBase, QColor(240, 240, 240))
        palette.setColor(QPalette.ToolTipText, QColor(240, 240, 240))
        palette.setColor(QPalette.Text, QColor(240, 240, 240))
        palette.setColor(QPalette.Button, QColor(68, 68, 68))
        palette.setColor(QPalette.ButtonText, QColor(240, 240, 240))
        palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.Highlight, QColor(76, 163, 224))
        palette.setColor(QPalette.HighlightedText, QColor(35, 38, 41))
        QApplication.instance().setPalette(palette)

    def keyPressEvent(self, event):
        # 回车键添加步骤
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.add_step()
        else:
            super().keyPressEvent(event)

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # 顶部：文件操作与步长设置
        top_layout = QHBoxLayout()
        self.load_param_btn = QPushButton("加载参数库")
        self.load_param_btn.clicked.connect(self.load_param_json)
        top_layout.addWidget(self.load_param_btn)

        self.load_step_btn = QPushButton("导入步骤")
        self.load_step_btn.clicked.connect(self.import_steps)
        top_layout.addWidget(self.load_step_btn)

        self.save_step_btn = QPushButton("导出步骤")
        self.save_step_btn.clicked.connect(self.export_steps)
        top_layout.addWidget(self.save_step_btn)

        self.export_table_btn = QPushButton("导出步骤表格内容")
        self.export_table_btn.clicked.connect(self.export_step_table_to_txt)
        top_layout.addWidget(self.export_table_btn)        

        top_layout.addStretch()

        self.batch_delete_btn = QPushButton("批量删除")
        self.batch_delete_btn.clicked.connect(self.batch_delete_steps)
        top_layout.addWidget(self.batch_delete_btn)

        # 新增：批量删除输入框
        self.delete_input = QLineEdit()
        self.delete_input.setPlaceholderText("输入要删除的步骤序号或范围，如 2,4-6")
        top_layout.addWidget(self.delete_input)

        self.batch_copy_btn = QPushButton("批量复制")
        self.batch_copy_btn.clicked.connect(self.batch_copy_steps)
        top_layout.addWidget(self.batch_copy_btn)

        top_layout.addWidget(QLabel("统一步长:"))
        self.step_length_box = QDoubleSpinBox()
        self.step_length_box.setDecimals(2)
        self.step_length_box.setRange(0.01, 99.99)
        self.step_length_box.setValue(self.current_step_length)
        self.step_length_box.valueChanged.connect(self.on_step_length_changed)
        top_layout.addWidget(self.step_length_box)

        self.batch_step_length_btn = QPushButton("批量应用步长")
        self.batch_step_length_btn.clicked.connect(self.batch_apply_step_length)
        top_layout.addWidget(self.batch_step_length_btn)

        self.add_step_btn = QPushButton("添加步骤")
        self.add_step_btn.clicked.connect(self.add_step)
        top_layout.addWidget(self.add_step_btn)

        self.reset_all_btn = QPushButton("重置所有参数")
        self.reset_all_btn.clicked.connect(self.reset_all_params)
        top_layout.addWidget(self.reset_all_btn)

        main_layout.addLayout(top_layout)

        # 仪器参数和背底参数勾选区（加滚动区和固定高度）
        self.inst_bg_scroll = QScrollArea()
        self.inst_bg_scroll.setWidgetResizable(True)
        self.inst_bg_scroll.setFixedHeight(200)
        self.inst_bg_widget = QWidget()
        self.inst_bg_layout = QHBoxLayout(self.inst_bg_widget)
        self.inst_bg_layout.setContentsMargins(0, 0, 0, 0)
        self.inst_bg_scroll.setWidget(self.inst_bg_widget)
        main_layout.addWidget(self.inst_bg_scroll)

        # 参数库tab
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget, stretch=2)

    def export_step_table_to_txt(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "导出表格内容", "", "Text Files (*.txt)")
        if not file_path:
            return
        lines = []
        headers = ["步骤名称", "  参数名称序列  ", "value序列"]
        lines.append("\t".join(headers))
        for step in self.steps:
            name = step["name"]
            param_names = [self.get_param_name(param["id"]) for param in step["active_params"]]
            param_names_str = "             \n".join(param_names)
            value_str = "\n".join([f"                  {param['value']:.2f}" for param in step["active_params"]])
            # 用制表符分隔，参数和值内部用换行
            lines.append(f"{name}\t{param_names_str}\t{value_str}")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        QMessageBox.information(self, "导出成功", f"表格内容已保存到 {file_path}")    

    def parse_delete_input(self, text):
        """
        支持格式如：2,4-6,8
        返回需要删除的步骤索引列表（从0开始）
        """
        indices = set()
        parts = text.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    for i in range(start, end+1):
                        indices.add(i-1)
                except Exception:
                    continue
            else:
                try:
                    idx = int(part)
                    indices.add(idx-1)
                except Exception:
                    continue
        return sorted([i for i in indices if 0 <= i < len(self.steps)], reverse=True)

    def batch_delete_steps(self):
        # 优先使用输入框，否则用勾选
        input_text = self.delete_input.text().strip()
        if input_text:
            rows = self.parse_delete_input(input_text)
            if not rows:
                QMessageBox.warning(self, "提示", "输入的序号无效或超出范围")
                return
        else:
            rows = sorted(self.get_selected_step_rows(), reverse=True)
            if not rows:
                QMessageBox.warning(self, "提示", "请勾选或输入要删除的步骤")
                return
        for row in rows:
            if 0 <= row < len(self.steps):
                del self.steps[row]
        self.refresh_step_table()
        self.delete_input.clear()

    def load_param_json(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择参数库JSON", "", "JSON Files (*.json)")
        if not file_path:
            return
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.param_lib = data.get("parameters_library", [])
        self.instrument_params = []
        self.bg_params = []
        self.phase_param_dict.clear()
        self.phase_group_dict.clear()
        self.param_id_map.clear()

        # 判断类型（XRD/TOF），并分类
        is_xrd = any(p.get("name", "").startswith("d_") for p in self.param_lib)
        for p in self.param_lib:
            pname = p.get("name", "")
            if "phase" not in p and "group" not in p:
                # 仪器/背底参数
                if is_xrd:
                    if pname.startswith("d_"):
                        self.bg_params.append(p)
                    else:
                        self.instrument_params.append(p)
                else:
                    if pname.startswith("BG"):
                        self.bg_params.append(p)
                    else:
                        self.instrument_params.append(p)
            elif "phase" in p and "group" in p:
                # phase参数命名规则
                if p["group"] != "原子参数":
                    p["name"] = f"{p['name']}_{p['phase']}"
                self.phase_param_dict[p["phase"]].append(p)
                self.phase_group_dict[p["phase"]][p["group"]].append(p)
            if "id" in p:
                self.param_id_map[p["id"]] = p

        self.refresh_inst_bg_checkboxes()
        self.refresh_param_tabs()
        self.refresh_step_table()

    def refresh_inst_bg_checkboxes(self):
        # 清空
        for i in reversed(range(self.inst_bg_layout.count())):
            widget = self.inst_bg_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        # 仪器参数
        self.inst_checkboxes = {}
        inst_group = QGroupBox("仪器参数")
        inst_layout = QVBoxLayout()
        btn_layout = QHBoxLayout()
        select_btn = QPushButton("全选")
        select_btn.clicked.connect(lambda: self.select_group_checkboxes(self.inst_checkboxes))
        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(lambda: self.reset_group_checkboxes(self.inst_checkboxes))
        btn_layout.addWidget(select_btn)
        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()
        inst_layout.addLayout(btn_layout)
        for p in self.instrument_params:
            cb = QCheckBox(p.get("name", ""))
            cb.param_id = p.get("id", None)
            self.inst_checkboxes[p.get("id", None)] = cb
            inst_layout.addWidget(cb)
        inst_group.setLayout(inst_layout)
        self.inst_bg_layout.addWidget(inst_group)
        # 背底参数
        self.bg_checkboxes = {}
        bg_group = QGroupBox("背底参数")
        bg_layout = QVBoxLayout()
        btn_layout2 = QHBoxLayout()
        select_btn2 = QPushButton("全选")
        select_btn2.clicked.connect(lambda: self.select_group_checkboxes(self.bg_checkboxes))
        reset_btn2 = QPushButton("重置")
        reset_btn2.clicked.connect(lambda: self.reset_group_checkboxes(self.bg_checkboxes))
        btn_layout2.addWidget(select_btn2)
        btn_layout2.addWidget(reset_btn2)
        btn_layout2.addStretch()
        bg_layout.addLayout(btn_layout2)
        for p in self.bg_params:
            cb = QCheckBox(p.get("name", ""))
            cb.param_id = p.get("id", None)
            self.bg_checkboxes[p.get("id", None)] = cb
            bg_layout.addWidget(cb)
        bg_group.setLayout(bg_layout)
        self.inst_bg_layout.addWidget(bg_group)

    def refresh_param_tabs(self):
        self.tab_widget.clear()
        self.phase_checkboxes = defaultdict(lambda: defaultdict(dict))  # phase -> group -> varies
        for phase in sorted(self.phase_group_dict.keys()):
            tab = QWidget()
            tab_layout = QVBoxLayout()
            group_dict = self.phase_group_dict[phase]
            for group in ["全局参数", "峰型参数", "晶胞参数", "不对称与择优参数", "吸收矫正参数", "原子参数"]:
                if group not in group_dict:
                    continue
                group_box = QGroupBox(group)
                group_layout = QVBoxLayout()
                btn_layout = QHBoxLayout()
                select_btn = QPushButton("全选")
                select_btn.setMaximumWidth(60)
                select_btn.clicked.connect(lambda _, ph=phase, gr=group: self.select_phase_group_checkboxes(ph, gr))
                reset_btn = QPushButton("重置")
                reset_btn.setMaximumWidth(60)
                reset_btn.clicked.connect(lambda _, ph=phase, gr=group: self.reset_phase_group_checkboxes(ph, gr))
                btn_layout.addWidget(select_btn)
                btn_layout.addWidget(reset_btn)
                btn_layout.addStretch()
                group_layout.addLayout(btn_layout)

                if group == "原子参数":
                    atom_groups = defaultdict(lambda: defaultdict(list))  # element -> atom_label -> params
                    for param in group_dict[group]:
                        name = param.get("name", "")
                        if "_" in name:
                            parts = name.split("_")
                            atom_label = "_".join(parts[:-1])
                            param_type = parts[-1]
                            match = re.match(r'^([A-Za-z]+)', atom_label)
                            element = match.group(1) if match else "Unknown"
                            atom_groups[element][atom_label].append(param)
                    self.phase_checkboxes[phase][group] = defaultdict(lambda: defaultdict(dict))
                    for element in sorted(atom_groups.keys()):
                        element_box = QGroupBox(element)
                        element_layout = QVBoxLayout()
                        for atom_label in sorted(atom_groups[element].keys()):
                            sub_group_box = QGroupBox(atom_label)
                            sub_layout = QVBoxLayout()
                            sub_btn_layout = QHBoxLayout()
                            sub_select_btn = QPushButton("全选")
                            sub_select_btn.setMaximumWidth(60)
                            sub_select_btn.clicked.connect(lambda _, ph=phase, gr=group, el=element, at=atom_label: self.select_atom_checkboxes(ph, gr, el, at))
                            sub_reset_btn = QPushButton("重置")
                            sub_reset_btn.setMaximumWidth(60)
                            sub_reset_btn.clicked.connect(lambda _, ph=phase, gr=group, el=element, at=atom_label: self.reset_atom_checkboxes(ph, gr, el, at))
                            sub_btn_layout.addWidget(sub_select_btn)
                            sub_btn_layout.addWidget(sub_reset_btn)
                            sub_btn_layout.addStretch()
                            sub_layout.addLayout(sub_btn_layout)

                            # 添加原子标签标题
                            label = QLabel(atom_label)
                            label.setStyleSheet("font-weight: bold;")
                            sub_layout.addWidget(label)

                            # 添加 X, Y, Z, Biso, Occ 参数
                            for param in atom_groups[element][atom_label]:
                                pname = param.get("name", "")
                                if pname.split("_")[-1] in ["X", "Y", "Z", "Biso", "Occ"]:
                                    cb = QCheckBox(pname)
                                    cb.param_id = param.get("id", None)
                                    self.phase_checkboxes[phase][group][element][atom_label][param.get("id", None)] = cb
                                    sub_layout.addWidget(cb)
                            sub_group_box.setLayout(sub_layout)
                            element_layout.addWidget(sub_group_box)
                        element_box.setLayout(element_layout)
                        group_layout.addWidget(element_box)
                else:
                    for param in group_dict[group]:
                        cb = QCheckBox(param.get("name", ""))
                        cb.param_id = param.get("id", None)
                        self.phase_checkboxes[phase][group][param.get("id", None)] = cb
                        group_layout.addWidget(cb)
                group_box.setLayout(group_layout)
                tab_layout.addWidget(group_box)
            tab_layout.addStretch()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            tab_content = QWidget()
            tab_content.setLayout(tab_layout)
            scroll.setWidget(tab_content)
            self.tab_widget.addTab(scroll, f"phase{phase}")

    def select_group_checkboxes(self, checkbox_dict):
        for cb in checkbox_dict.values():
            cb.setChecked(True)

    def reset_group_checkboxes(self, checkbox_dict):
        for cb in checkbox_dict.values():
            if cb.isChecked():
                cb.setChecked(False)

    def select_phase_group_checkboxes(self, phase, group):
        group_dict = self.phase_checkboxes[phase][group]
        if group == "原子参数":
            for element in group_dict:
                for atom_label in group_dict[element]:
                    for cb in group_dict[element][atom_label].values():
                        cb.setChecked(True)
        else:
            for cb in group_dict.values():
                cb.setChecked(True)

    def reset_phase_group_checkboxes(self, phase, group):
        group_dict = self.phase_checkboxes[phase][group]
        if group == "原子参数":
            for element in group_dict:
                for atom_label in group_dict[element]:
                    for cb in group_dict[element][atom_label].values():
                        if cb.isChecked():
                            cb.setChecked(False)
        else:
            for cb in group_dict.values():
                if cb.isChecked():
                    cb.setChecked(False)

    def select_atom_checkboxes(self, phase, group, element, atom_label):
        for cb in self.phase_checkboxes[phase][group][element][atom_label].values():
            cb.setChecked(True)

    def reset_atom_checkboxes(self, phase, group, element, atom_label):
        for cb in self.phase_checkboxes[phase][group][element][atom_label].values():
            if cb.isChecked():
                cb.setChecked(False)

    def reset_all_params(self):
        for cb in self.inst_checkboxes.values():
            if cb.isChecked():
                cb.setChecked(False)
        for cb in self.bg_checkboxes.values():
            if cb.isChecked():
                cb.setChecked(False)
        for phase in self.phase_checkboxes:
            for group in self.phase_checkboxes[phase]:
                group_dict = self.phase_checkboxes[phase][group]
                if group == "原子参数":
                    for element in group_dict:
                        for atom_label in group_dict[element]:
                            for cb in group_dict[element][atom_label].values():
                                if cb.isChecked():
                                    cb.setChecked(False)
                else:
                    for cb in group_dict.values():
                        if cb.isChecked():
                            cb.setChecked(False)

    def get_checked_param_ids(self):
        checked_ids = []
        for pid, cb in self.inst_checkboxes.items():
            if cb.isChecked():
                checked_ids.append(pid)
        for pid, cb in self.bg_checkboxes.items():
            if cb.isChecked():
                checked_ids.append(pid)
        for phase in self.phase_checkboxes:
            for group in self.phase_checkboxes[phase]:
                group_dict = self.phase_checkboxes[phase][group]
                if group == "原子参数":
                    for element in group_dict:
                        for atom_label in group_dict[element]:
                            for pid, cb in group_dict[element][atom_label].items():
                                if cb.isChecked():
                                    checked_ids.append(pid)
                else:
                    for pid, cb in group_dict.items():
                        if cb.isChecked():
                            checked_ids.append(pid)
        return checked_ids

    def add_step(self):
        checked_ids = self.get_checked_param_ids()
        if not checked_ids:
            QMessageBox.warning(self, "提示", "请先勾选参数")
            return
        step_idx = len(self.steps) + 1
        step_name = f"Step{step_idx}"
        step_length = self.current_step_length
        step_params = []
        for i, pid in enumerate(checked_ids):
            value = self.generate_value(i, step_length)
            step_params.append({"id": pid, "value": value})
        self.steps.append({"name": step_name, "active_params": step_params})
        self.refresh_step_table()

    def generate_value(self, order, step_length):
        int_part = (order + 1) * 10
        value = float(f"{int_part + step_length:.2f}")
        return value

    def on_step_length_changed(self, val):
        self.current_step_length = float(val)
        # 不自动应用，需点“批量应用步长”才生效

    def batch_apply_step_length(self):
        selected_rows = self.get_selected_step_rows()
        if not selected_rows:
            QMessageBox.warning(self, "提示", "请先勾选要批量修改步长的步骤")
            return
        for row in selected_rows:
            step = self.steps[row]
            for i, param in enumerate(step["active_params"]):
                int_part = int(float(param["value"]) // 10 * 10)
                param["value"] = float(f"{int_part + self.current_step_length:.2f}")
        self.refresh_step_table()

    def refresh_step_table(self):
        step_table = self.table_window.step_table
        step_table.blockSignals(True)
        step_table.setColumnCount(4)
        step_table.setHorizontalHeaderLabels(["选择", "步骤名称", "参数名称序列", "value序列"])
        step_table.setRowCount(len(self.steps))
        for row, step in enumerate(self.steps):
            # 勾选框
            cb = QCheckBox()
            cb.setChecked(False)
            step_table.setCellWidget(row, 0, cb)
            # 步骤名称（可编辑）
            name_item = QTableWidgetItem(step["name"])
            name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)
            step_table.setItem(row, 1, name_item)
            # 参数名称序列（纵向排列）
            param_names = []
            for param in step["active_params"]:
                pid = param["id"]
                pname = self.get_param_name(pid)
                param_names.append(pname)
            param_names_str = "\n".join(param_names)
            param_item = QTableWidgetItem(param_names_str)
            param_item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
            param_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            step_table.setItem(row, 2, param_item)
            # value序列（纵向排列）
            value_str = "\n".join([f"{param['value']:.2f}" for param in step["active_params"]])
            value_item = QTableWidgetItem(value_str)
            value_item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
            value_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)
            step_table.setItem(row, 3, value_item)
        step_table.resizeRowsToContents()
        step_table.blockSignals(False)
        step_table.cellChanged.connect(self.on_step_table_cell_changed)

    def on_step_checkbox_changed(self):
        # 仅用于刷新时同步选中状态
        pass

    def get_selected_step_rows(self):
        step_table = self.table_window.step_table
        selected = []
        for row in range(step_table.rowCount()):
            cb = step_table.cellWidget(row, 0)
            if cb and cb.isChecked():
                selected.append(row)
        return selected

    def batch_copy_steps(self):
        rows = self.get_selected_step_rows()
        if not rows:
            QMessageBox.warning(self, "提示", "请先勾选要复制的步骤")
            return
        import copy
        offset = 0
        for row in rows:
            idx = row + 1 + offset
            new_step = copy.deepcopy(self.steps[row])
            new_step["name"] = f"{new_step['name']}_copy"
            self.steps.insert(idx, new_step)
            offset += 1
        self.refresh_step_table()

    def on_step_table_cell_changed(self, row, col):
        step_table = self.table_window.step_table
        if col == 1:
            # 步骤名称修改
            new_name = step_table.item(row, 1).text()
            self.steps[row]["name"] = new_name
        elif col == 3:
            # value序列修改
            value_str = step_table.item(row, 3).text()
            value_list = [v.strip() for v in value_str.split("\n")]
            for i, v in enumerate(value_list):
                try:
                    self.steps[row]["active_params"][i]["value"] = float(v)
                except Exception:
                    pass

    def delete_step(self):
        btn = self.sender()
        row = btn.property("row")
        if row is not None and 0 <= row < len(self.steps):
            del self.steps[row]
            self.refresh_step_table()

    def copy_step(self):
        btn = self.sender()
        row = btn.property("row")
        if row is not None and 0 <= row < len(self.steps):
            import copy
            new_step = copy.deepcopy(self.steps[row])
            new_step["name"] = f"{new_step['name']}_copy"
            self.steps.insert(row+1, new_step)
            self.refresh_step_table()

    def get_param_name(self, pid):
        param = self.param_id_map.get(pid, {})
        return param.get("name", f"ID{pid}")

    def import_steps(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "导入步骤JSON", "", "JSON Files (*.json)")
        if not file_path:
            return
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.steps = data.get("steps", [])
        self.refresh_step_table()

    def export_steps(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "导出步骤JSON", "", "JSON Files (*.json)")
        if not file_path:
            return
        out = {"steps": self.steps}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "导出成功", f"已保存到 {file_path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("微软雅黑"))
    win = StepConfigGUI()
    win.show()

    sys.exit(app.exec_())
