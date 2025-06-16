import sys  # 导入sys模块，用于系统相关操作
import json  # 导入json模块，用于读写JSON文件
from collections import defaultdict  # 导入defaultdict，用于自动创建字典嵌套结构
from PyQt5.QtWidgets import (  # 导入PyQt5相关控件
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTabWidget, QGroupBox, QCheckBox, QScrollArea, QTableWidget,
    QTableWidgetItem, QMessageBox, QHeaderView, QDoubleSpinBox, QAbstractItemView,QAbstractScrollArea
)
from PyQt5.QtCore import Qt  # 导入Qt常量

class StepConfigGUI(QWidget):  # 步骤生成主界面类
    def __init__(self):  # 构造函数
        super().__init__()  # 调用父类构造
        self.setWindowTitle("Magia_Step_Generator_v1.0")  # 设置窗口标题
        self.resize(1200, 700)  # 设置窗口大小
        self.param_lib = []  # 参数库列表
        self.steps = []  # 步骤列表
        self.instrument_params = []  # 仪器参数列表
        self.bg_params = []  # 背底参数列表
        self.phase_param_dict = defaultdict(list)  # 相参数字典 phase->参数列表
        self.phase_group_dict = defaultdict(lambda: defaultdict(list))  # 相-分组参数字典 phase->group->参数列表
        self.current_step_length = 1.00  # 当前步长
        self.param_id_map = {}  # 参数id到参数的映射
        self.init_ui()  # 初始化界面

    def init_ui(self):  # 初始化界面
        main_layout = QVBoxLayout(self)  # 主垂直布局

        # 顶部：文件操作与步长设置
        top_layout = QHBoxLayout()  # 顶部水平布局
        self.load_param_btn = QPushButton("加载参数库")  # 加载参数库按钮
        self.load_param_btn.clicked.connect(self.load_param_json)  # 绑定点击事件
        top_layout.addWidget(self.load_param_btn)  # 添加到布局

        self.load_step_btn = QPushButton("导入步骤")  # 导入步骤按钮
        self.load_step_btn.clicked.connect(self.import_steps)  # 绑定点击事件
        top_layout.addWidget(self.load_step_btn)  # 添加到布局

        self.save_step_btn = QPushButton("导出步骤")  # 导出步骤按钮
        self.save_step_btn.clicked.connect(self.export_steps)  # 绑定点击事件
        top_layout.addWidget(self.save_step_btn)  # 添加到布局

        self.export_table_btn = QPushButton("导出步骤表格内容")  # 导出表格内容按钮
        self.export_table_btn.clicked.connect(self.export_step_table_to_txt)  # 绑定点击事件
        top_layout.addWidget(self.export_table_btn)  # 添加到布局        

        top_layout.addStretch()  # 添加弹性空间

        self.batch_delete_btn = QPushButton("批量删除")  # 批量删除按钮
        self.batch_delete_btn.clicked.connect(self.batch_delete_steps)  # 绑定点击事件
        top_layout.addWidget(self.batch_delete_btn)  # 添加到布局

        self.batch_copy_btn = QPushButton("批量复制")  # 批量复制按钮
        self.batch_copy_btn.clicked.connect(self.batch_copy_steps)  # 绑定点击事件
        top_layout.addWidget(self.batch_copy_btn)  # 添加到布局

        top_layout.addWidget(QLabel("统一步长:"))  # 步长标签
        self.step_length_box = QDoubleSpinBox()  # 步长输入框
        self.step_length_box.setDecimals(2)  # 保留两位小数
        self.step_length_box.setRange(0.01, 99.99)  # 步长范围
        self.step_length_box.setValue(self.current_step_length)  # 默认值
        self.step_length_box.valueChanged.connect(self.on_step_length_changed)  # 绑定事件
        top_layout.addWidget(self.step_length_box)  # 添加到布局

        self.batch_step_length_btn = QPushButton("批量应用步长")  # 批量应用步长按钮
        self.batch_step_length_btn.clicked.connect(self.batch_apply_step_length)  # 绑定事件
        top_layout.addWidget(self.batch_step_length_btn)  # 添加到布局

        self.add_step_btn = QPushButton("添加步骤")  # 添加步骤按钮
        self.add_step_btn.clicked.connect(self.add_step)  # 绑定事件
        top_layout.addWidget(self.add_step_btn)  # 添加到布局

        self.reset_all_btn = QPushButton("重置所有参数")  # 重置所有参数按钮
        self.reset_all_btn.clicked.connect(self.reset_all_params)  # 绑定事件
        top_layout.addWidget(self.reset_all_btn)  # 添加到布局

        main_layout.addLayout(top_layout)  # 添加顶部布局到主布局

        # 仪器参数和背底参数勾选区（加滚动区和固定高度）
        self.inst_bg_scroll = QScrollArea()  # 滚动区
        self.inst_bg_scroll.setWidgetResizable(True)  # 可自适应
        self.inst_bg_scroll.setFixedHeight(200)  # 固定高度
        self.inst_bg_widget = QWidget()  # 滚动区内容部件
        self.inst_bg_layout = QHBoxLayout(self.inst_bg_widget)  # 水平布局
        self.inst_bg_layout.setContentsMargins(0, 0, 0, 0)  # 去除边距
        self.inst_bg_scroll.setWidget(self.inst_bg_widget)  # 设置内容部件
        main_layout.addWidget(self.inst_bg_scroll)  # 添加到主布局

        # 参数库tab
        self.tab_widget = QTabWidget()  # 参数分组标签页
        main_layout.addWidget(self.tab_widget, stretch=2)  # 添加到主布局

        # 步骤表格
        self.step_table = QTableWidget()  # 步骤表格
        self.step_table.setSelectionBehavior(QAbstractItemView.SelectRows)  # 行选中
        self.step_table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)  # 双击或选中可编辑
        self.step_table.setWordWrap(True)  # 自动换行
        # 新增：设置为像素滚动
        self.step_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)  # 垂直像素滚动
        self.step_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)  # 水平像素滚动
        # 新增：可选，自动调整表格大小策略
        self.step_table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)  # 自动调整内容
        main_layout.addWidget(self.step_table, stretch=3)  # 添加到主布局

    def export_step_table_to_txt(self):  # 导出步骤表格内容为txt
        file_path, _ = QFileDialog.getSaveFileName(self, "导出表格内容", "", "Text Files (*.txt)")  # 选择保存路径
        if not file_path:  # 未选择则返回
            return
        lines = []  # 存储所有行
        headers = ["步骤名称", "  参数名称序列  ", "value序列"]  # 表头
        lines.append("\t".join(headers))  # 添加表头
        for step in self.steps:  # 遍历所有步骤
            name = step["name"]  # 步骤名
            param_names = [self.get_param_name(param["id"]) for param in step["active_params"]]  # 参数名列表
            param_names_str = "             \n".join(param_names)  # 参数名换行
            value_str = "\n".join([f"                  {param['value']:.2f}" for param in step["active_params"]])  # value换行
            # 用制表符分隔，参数和值内部用换行
            lines.append(f"{name}\t{param_names_str}\t{value_str}")  # 添加一行
        with open(file_path, "w", encoding="utf-8") as f:  # 写入文件
            f.write("\n".join(lines))
        QMessageBox.information(self, "导出成功", f"表格内容已保存到 {file_path}")  # 弹窗提示

    def load_param_json(self):  # 加载参数库JSON文件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择参数库JSON", "", "JSON Files (*.json)")  # 选择文件
        if not file_path:
            return
        with open(file_path, "r", encoding="utf-8") as f:  # 打开文件
            data = json.load(f)  # 读取JSON
        self.param_lib = data.get("parameters_library", [])  # 获取参数库
        self.instrument_params = []  # 清空仪器参数
        self.bg_params = []  # 清空背底参数
        self.phase_param_dict.clear()  # 清空相参数
        self.phase_group_dict.clear()  # 清空分组参数
        self.param_id_map.clear()  # 清空id映射

        # 判断类型（XRD/TOF），并分类
        is_xrd = any(p.get("name", "").startswith("d_") for p in self.param_lib)  # 判断是否XRD
        for p in self.param_lib:  # 遍历参数
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

        self.refresh_inst_bg_checkboxes()  # 刷新仪器/背底参数勾选框
        self.refresh_param_tabs()  # 刷新参数分组tab
        self.refresh_step_table()  # 刷新步骤表格

    def refresh_inst_bg_checkboxes(self):  # 刷新仪器/背底参数勾选框
        # 清空
        for i in reversed(range(self.inst_bg_layout.count())):
            widget = self.inst_bg_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        # 仪器参数
        self.inst_checkboxes = {}  # 仪器参数勾选框字典
        inst_group = QGroupBox("仪器参数")  # 仪器参数分组框
        inst_layout = QVBoxLayout()  # 垂直布局
        btn_layout = QHBoxLayout()  # 按钮布局
        select_btn = QPushButton("全选")  # 全选按钮
        select_btn.clicked.connect(lambda: self.select_group_checkboxes(self.inst_checkboxes))  # 绑定事件
        reset_btn = QPushButton("重置")  # 重置按钮
        reset_btn.clicked.connect(lambda: self.reset_group_checkboxes(self.inst_checkboxes))  # 绑定事件
        btn_layout.addWidget(select_btn)
        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()
        inst_layout.addLayout(btn_layout)
        for p in self.instrument_params:  # 遍历仪器参数
            cb = QCheckBox(p.get("name", ""))  # 创建勾选框
            cb.param_id = p.get("id", None)  # 绑定参数id
            self.inst_checkboxes[p.get("id", None)] = cb  # 存入字典
            inst_layout.addWidget(cb)  # 添加到布局
        inst_group.setLayout(inst_layout)  # 设置分组框布局
        self.inst_bg_layout.addWidget(inst_group)  # 添加到主布局
        # 背底参数
        self.bg_checkboxes = {}  # 背底参数勾选框字典
        bg_group = QGroupBox("背底参数")  # 背底参数分组框
        bg_layout = QVBoxLayout()  # 垂直布局
        btn_layout2 = QHBoxLayout()  # 按钮布局
        select_btn2 = QPushButton("全选")  # 全选按钮
        select_btn2.clicked.connect(lambda: self.select_group_checkboxes(self.bg_checkboxes))  # 绑定事件
        reset_btn2 = QPushButton("重置")  # 重置按钮
        reset_btn2.clicked.connect(lambda: self.reset_group_checkboxes(self.bg_checkboxes))  # 绑定事件
        btn_layout2.addWidget(select_btn2)
        btn_layout2.addWidget(reset_btn2)
        btn_layout2.addStretch()
        bg_layout.addLayout(btn_layout2)
        for p in self.bg_params:  # 遍历背底参数
            cb = QCheckBox(p.get("name", ""))  # 创建勾选框
            cb.param_id = p.get("id", None)  # 绑定参数id
            self.bg_checkboxes[p.get("id", None)] = cb  # 存入字典
            bg_layout.addWidget(cb)  # 添加到布局
        bg_group.setLayout(bg_layout)  # 设置分组框布局
        self.inst_bg_layout.addWidget(bg_group)  # 添加到主布局

    def refresh_param_tabs(self):  # 刷新参数分组tab
        self.tab_widget.clear()  # 清空tab
        self.phase_checkboxes = defaultdict(lambda: defaultdict(dict))  # phase -> group -> param_id -> checkbox
        for phase in sorted(self.phase_group_dict.keys()):  # 遍历所有相
            tab = QWidget()  # 创建tab
            tab_layout = QVBoxLayout()  # 垂直布局
            group_dict = self.phase_group_dict[phase]  # 获取分组字典
            for group in ["全局参数", "峰型参数", "晶胞参数", "不对称与择优参数", "吸收矫正参数", "原子参数"]:
                if group not in group_dict:
                    continue
                group_box = QGroupBox(group)  # 分组框
                group_layout = QVBoxLayout()  # 垂直布局
                btn_layout = QHBoxLayout()  # 按钮布局
                select_btn = QPushButton("全选")  # 全选按钮
                select_btn.setMaximumWidth(60)
                select_btn.clicked.connect(lambda _, ph=phase, gr=group: self.select_phase_group_checkboxes(ph, gr))  # 绑定事件
                reset_btn = QPushButton("重置")  # 重置按钮
                reset_btn.setMaximumWidth(60)
                reset_btn.clicked.connect(lambda _, ph=phase, gr=group: self.reset_phase_group_checkboxes(ph, gr))  # 绑定事件
                btn_layout.addWidget(select_btn)
                btn_layout.addWidget(reset_btn)
                btn_layout.addStretch()
                group_layout.addLayout(btn_layout)
                for param in group_dict[group]:  # 遍历参数
                    cb = QCheckBox(param.get("name", ""))  # 创建勾选框
                    cb.param_id = param.get("id", None)  # 绑定参数id
                    self.phase_checkboxes[phase][group][param.get("id", None)] = cb  # 存入字典
                    group_layout.addWidget(cb)  # 添加到布局
                group_box.setLayout(group_layout)  # 设置分组框布局
                tab_layout.addWidget(group_box)  # 添加到tab布局
            tab_layout.addStretch()
            scroll = QScrollArea()  # 滚动区
            scroll.setWidgetResizable(True)
            tab_content = QWidget()
            tab_content.setLayout(tab_layout)
            scroll.setWidget(tab_content)
            self.tab_widget.addTab(scroll, f"phase{phase}")  # 添加tab

    def select_group_checkboxes(self, checkbox_dict):  # 全选某组参数
        for cb in checkbox_dict.values():
            cb.setChecked(True)

    def reset_group_checkboxes(self, checkbox_dict):  # 重置某组参数
        for cb in checkbox_dict.values():
            if cb.isChecked():
                cb.setChecked(False)

    def select_phase_group_checkboxes(self, phase, group):  # 全选某相某组参数
        for cb in self.phase_checkboxes[phase][group].values():
            cb.setChecked(True)

    def reset_phase_group_checkboxes(self, phase, group):  # 重置某相某组参数
        for cb in self.phase_checkboxes[phase][group].values():
            if cb.isChecked():
                cb.setChecked(False)

    def reset_all_params(self):  # 重置所有参数
        for cb in self.inst_checkboxes.values():
            if cb.isChecked():
                cb.setChecked(False)
        for cb in self.bg_checkboxes.values():
            if cb.isChecked():
                cb.setChecked(False)
        for phase in self.phase_checkboxes:
            for group in self.phase_checkboxes[phase]:
                for cb in self.phase_checkboxes[phase][group].values():
                    if cb.isChecked():
                        cb.setChecked(False)

    def get_checked_param_ids(self):  # 获取所有勾选参数id
        checked_ids = []
        for pid, cb in self.inst_checkboxes.items():
            if cb.isChecked():
                checked_ids.append(pid)
        for pid, cb in self.bg_checkboxes.items():
            if cb.isChecked():
                checked_ids.append(pid)
        for phase in self.phase_checkboxes:
            for group in self.phase_checkboxes[phase]:
                for pid, cb in self.phase_checkboxes[phase][group].items():
                    if cb.isChecked():
                        checked_ids.append(pid)
        return checked_ids

    def add_step(self):  # 添加步骤
        checked_ids = self.get_checked_param_ids()  # 获取勾选参数id
        if not checked_ids:
            QMessageBox.warning(self, "提示", "请先勾选参数")
            return
        step_idx = len(self.steps) + 1  # 步骤编号
        step_name = f"Step{step_idx}"  # 步骤名称
        step_length = self.current_step_length  # 步长
        step_params = []
        for i, pid in enumerate(checked_ids):
            value = self.generate_value(i, step_length)  # 生成value
            step_params.append({"id": pid, "value": value})  # 添加参数
        self.steps.append({"name": step_name, "active_params": step_params})  # 添加步骤
        self.refresh_step_table()  # 刷新表格

    def generate_value(self, order, step_length):  # 生成参数值
        int_part = (order + 1) * 10  # 整数部分
        value = float(f"{int_part + step_length:.2f}")  # 保留两位小数
        return value

    def on_step_length_changed(self, val):  # 步长变更事件
        self.current_step_length = float(val)
        # 不自动应用，需点“批量应用步长”才生效

    def batch_apply_step_length(self):  # 批量应用步长
        selected_rows = self.get_selected_step_rows()  # 获取选中行
        if not selected_rows:
            QMessageBox.warning(self, "提示", "请先勾选要批量修改步长的步骤")
            return
        for row in selected_rows:
            step = self.steps[row]
            for i, param in enumerate(step["active_params"]):
                int_part = int(float(param["value"]) // 10 * 10)
                param["value"] = float(f"{int_part + self.current_step_length:.2f}")
        self.refresh_step_table()

    def refresh_step_table(self):  # 刷新步骤表格
        self.step_table.blockSignals(True)  # 阻塞信号，防止递归
        self.step_table.setColumnCount(4)  # 4列
        self.step_table.setHorizontalHeaderLabels(["选择", "步骤名称", "参数名称序列", "value序列"])  # 设置表头
        self.step_table.setRowCount(len(self.steps))  # 行数
        for row, step in enumerate(self.steps):  # 遍历步骤
            # 勾选框
            cb = QCheckBox()
            cb.setChecked(False)
            self.step_table.setCellWidget(row, 0, cb)
            # 步骤名称（可编辑）
            name_item = QTableWidgetItem(step["name"])
            name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)
            self.step_table.setItem(row, 1, name_item)
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
            self.step_table.setItem(row, 2, param_item)
            # value序列（纵向排列）
            value_str = "\n".join([f"{param['value']:.2f}" for param in step["active_params"]])
            value_item = QTableWidgetItem(value_str)
            value_item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
            value_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)
            self.step_table.setItem(row, 3, value_item)
        self.step_table.resizeRowsToContents()  # 自动调整行高
        self.step_table.blockSignals(False)  # 解除信号阻塞
        self.step_table.cellChanged.connect(self.on_step_table_cell_changed)  # 绑定单元格变更事件

    def on_step_checkbox_changed(self):  # 步骤勾选框变更事件（未用）
        # 仅用于刷新时同步选中状态
        pass

    def get_selected_step_rows(self):  # 获取所有勾选的步骤行号
        selected = []
        for row in range(self.step_table.rowCount()):
            cb = self.step_table.cellWidget(row, 0)
            if cb and cb.isChecked():
                selected.append(row)
        return selected

    def batch_delete_steps(self):  # 批量删除步骤
        rows = sorted(self.get_selected_step_rows(), reverse=True)  # 倒序删除
        if not rows:
            QMessageBox.warning(self, "提示", "请先勾选要删除的步骤")
            return
        for row in rows:
            if 0 <= row < len(self.steps):
                del self.steps[row]
        self.refresh_step_table()

    def batch_copy_steps(self):  # 批量复制步骤
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

    def on_step_table_cell_changed(self, row, col):  # 步骤表格单元格变更事件
        if col == 1:
            # 步骤名称修改
            new_name = self.step_table.item(row, 1).text()
            self.steps[row]["name"] = new_name
        elif col == 3:
            # value序列修改
            value_str = self.step_table.item(row, 3).text()
            value_list = [v.strip() for v in value_str.split("\n")]
            for i, v in enumerate(value_list):
                try:
                    self.steps[row]["active_params"][i]["value"] = float(v)
                except Exception:
                    pass

    def delete_step(self):  # 删除单步（未用）
        btn = self.sender()
        row = btn.property("row")
        if row is not None and 0 <= row < len(self.steps):
            del self.steps[row]
            self.refresh_step_table()

    def copy_step(self):  # 复制单步（未用）
        btn = self.sender()
        row = btn.property("row")
        if row is not None and 0 <= row < len(self.steps):
            import copy
            new_step = copy.deepcopy(self.steps[row])
            new_step["name"] = f"{new_step['name']}_copy"
            self.steps.insert(row+1, new_step)
            self.refresh_step_table()

    def get_param_name(self, pid):  # 根据参数id获取参数名
        param = self.param_id_map.get(pid, {})
        return param.get("name", f"ID{pid}")

    def import_steps(self):  # 导入步骤JSON
        file_path, _ = QFileDialog.getOpenFileName(self, "导入步骤JSON", "", "JSON Files (*.json)")
        if not file_path:
            return
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.steps = data.get("steps", [])
        self.refresh_step_table()

    def export_steps(self):  # 导出步骤JSON
        file_path, _ = QFileDialog.getSaveFileName(self, "导出步骤JSON", "", "JSON Files (*.json)")
        if not file_path:
            return
        out = {"steps": self.steps}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "导出成功", f"已保存到 {file_path}")

if __name__ == "__main__":  # 主程序入口
    app = QApplication(sys.argv)  # 创建应用
    win = StepConfigGUI()  # 创建主窗口
    win.show()  # 显示窗口
    sys.exit(app.exec_())  # 进入主事件循环