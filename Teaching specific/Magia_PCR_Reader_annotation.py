import os  # 导入os模块，用于文件路径操作
import sys  # 导入sys模块，用于系统相关操作
import re  # 导入re模块，用于正则表达式处理
import json  # 导入json模块，用于JSON文件读写
from PyQt5.QtWidgets import (  # 导入PyQt5相关控件
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QTabWidget, QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem, QMessageBox, QTextEdit, QScrollArea, QComboBox
)
from PyQt5.QtCore import Qt  # 导入Qt常量
from PyQt5.QtGui import QFont  # 导入QFont用于字体设置

def detect_and_convert_to_utf8(filepath, encodings=('utf-8', 'gbk', 'gb2312', 'latin1')):
    # 自动检测文件编码并转换为UTF-8编码，返回转换后的文件路径
    last_exc = None  # 记录最后一次异常
    for enc in encodings:  # 遍历所有可能的编码
        try:
            with open(filepath, 'r', encoding=enc) as f:  # 尝试用指定编码读取文件
                content = f.read()  # 读取全部内容
            if enc != 'utf-8':  # 如果不是utf-8编码
                utf8_path = os.path.splitext(filepath)[0] + "_UTF_8.pcr"  # 新文件名
                with open(utf8_path, 'w', encoding='utf-8') as f:  # 用utf-8写入新文件
                    f.write(content)
                return utf8_path  # 返回新文件路径
            else:
                return filepath  # 已是utf-8，直接返回原路径
        except Exception as e:
            last_exc = e  # 记录异常
    raise RuntimeError(f"无法识别pcr文件编码，请尝试另存为UTF-8或GBK编码\n详细信息: {last_exc}")  # 全部失败则报错

def ensure_chi2_line(filepath):
    # 检查并确保pcr文件中有“! Current global Chi2”行，没有则插入
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()  # 读取所有行
    chi2_line = [i for i, l in enumerate(lines) if l.strip().startswith('! Current global Chi2')]  # 查找chi2行
    if not chi2_line:  # 如果没有chi2行
        lines.insert(1, '! Current global Chi2 (Bragg contrib.) =      \n')  # 在第2行插入
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)  # 写回文件
    return filepath  # 返回文件路径

def get_job_type(filepath):
    # 判断pcr文件类型，返回job类型（0为XRD，-1为TOF）
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()  # 读取所有行
    for idx, line in enumerate(lines):  # 遍历所有行
        if line.strip().lower().startswith('!job'):  # 找到!job行
            job_value = int(lines[idx+1].split()[0])  # 取下一行第一个数
            return job_value  # 返回job类型
    return 0  # 默认返回0（XRD）

def parse_poly_bg_params_xrd(lines, param_id):
    # 解析XRD多项式背底参数，返回参数列表和下一个param_id
    params = []  # 参数列表
    for idx, line in enumerate(lines):  # 遍历所有行
        if 'Background coefficients/codes' in line and 'Polynomial' in line:  # 找到多项式背底行
            for i in range(6):  # 假定有6个多项式参数
                params.append({"id": param_id, "name": f"d_{i}", "line": idx+3, "position": i})  # 添加参数
                param_id += 1  # 参数编号递增
            break  # 找到后退出
    return params, param_id  # 返回参数和下一个id

def parse_manual_bg_params_xrd(lines, param_id):
    # 解析XRD手动插值背底参数，返回参数列表和下一个param_id
    params = []  # 参数列表
    for idx, line in enumerate(lines):  # 遍历所有行
        if "Background" in line and "Pattern#" in line:  # 找到手动背底起始行
            bg_idx = idx + 1  # 参数起始行
            while bg_idx < len(lines):  # 向下遍历
                l = lines[bg_idx]
                if l.strip().startswith('!'):  # 遇到注释行停止
                    break
                vals = l.strip().split()  # 拆分参数
                if len(vals) >= 3:  # 至少有3列
                    params.append({
                        "id": param_id,
                        "name": f"BG{len(params)+1}",
                        "line": bg_idx+1,
                        "position": 2,
                        "value": vals[2]
                    })
                    param_id += 1
                bg_idx += 1
            break  # 找到后退出
    return params, param_id  # 返回参数和下一个id

def parse_poly_bg_params_tof(lines, param_id):
    # 解析TOF多项式背底参数（暂未实现），返回空列表和param_id
    return [], param_id

def parse_manual_bg_params_tof(lines, param_id):
    # 解析TOF手动插值背底参数，返回参数列表和下一个param_id
    params = []  # 参数列表
    for idx, line in enumerate(lines):  # 遍历所有行
        if "Background" in line and "Pattern#" in line:  # 找到手动背底起始行
            bg_idx = idx + 1  # 参数起始行
            while bg_idx < len(lines):  # 向下遍历
                l = lines[bg_idx]
                if l.strip().startswith('!'):  # 遇到注释行停止
                    break
                vals = l.strip().split()  # 拆分参数
                if len(vals) >= 3:  # 至少有3列
                    params.append({
                        "id": param_id,
                        "name": f"BG{len(params)+1}",
                        "line": bg_idx+1,
                        "position": 2,
                        "value": vals[2]
                    })
                    param_id += 1
                bg_idx += 1
            break  # 找到后退出
    return params, param_id  # 返回参数和下一个id

def parse_xrd_pcr(filepath, atom_names, bg_mode):
    # 解析XRD类型pcr文件，返回参数列表
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()  # 读取所有行
    params = []  # 参数列表
    param_id = 1  # 参数编号初始值

    # 仪器参数
    for idx, line in enumerate(lines):  # 遍历所有行
        if 'Zero' in line and 'SyCos' in line and 'SySin' in line and 'Lambda' in line:  # 找到仪器参数行
            vals = lines[idx+1].split()  # 取下一行参数
            params.append({"id": param_id, "name": "Zero", "line": idx+2, "position": 1}); param_id += 1
            params.append({"id": param_id, "name": "SyCos", "line": idx+2, "position": 3}); param_id += 1
            params.append({"id": param_id, "name": "SySin", "line": idx+2, "position": 5}); param_id += 1
            params.append({"id": param_id, "name": "Lambda", "line": idx+2, "position": 7}); param_id += 1
            break  # 找到后退出

    # 背底参数
    if bg_mode == "poly":  # 多项式背底
        bg_params, param_id = parse_poly_bg_params_xrd(lines, param_id)
    else:  # 手动插值背底
        bg_params, param_id = parse_manual_bg_params_xrd(lines, param_id)
    params.extend(bg_params)  # 添加到参数列表

    # phase分割
    phase_indices = []  # 相起始行索引
    phase_numbers = []  # 相编号
    for idx, line in enumerate(lines):  # 遍历所有行
        m = re.match(r'!\s*Data for PHASE number:\s*(\d+)', line)  # 匹配phase行
        if m:
            phase_indices.append(idx)  # 记录起始行
            phase_numbers.append(int(m.group(1)))  # 记录相编号
    phase_indices.append(len(lines))  # 末尾补充

    for pidx in range(len(phase_indices)-1):  # 遍历每个phase
        phase_start = phase_indices[pidx]
        phase_end = phase_indices[pidx+1]
        phase_lines = lines[phase_start:phase_end]  # 当前phase的所有行
        phase_no = phase_numbers[pidx]  # 当前phase编号

        # 全局参数
        for idx, l in enumerate(phase_lines):
            if 'Scale' in l and 'Shape1' in l and 'Bov' in l:
                for i, n in enumerate(['Scale','Shape1','Bov','Str1','Str2','Str3']):
                    params.append({"id": param_id, "name": n, "line": phase_start+idx+3, "position": i, "phase": phase_no, "group": "全局参数"})
                    param_id += 1
                break
        # 峰型参数
        for idx, l in enumerate(phase_lines):
            if re.search(r'\bU\b', l) and re.search(r'\bV\b', l) and re.search(r'\bW\b', l):
                for i, n in enumerate(['U','V','W','X','Y','GauSiz','LorSiz']):
                    params.append({"id": param_id, "name": n, "line": phase_start+idx+3, "position": i, "phase": phase_no, "group": "峰型参数"})
                    param_id += 1
                break
        # 晶胞参数
        for idx, l in enumerate(phase_lines):
            if 'a' in l and 'b' in l and 'c' in l and 'alpha' in l:
                for i, n in enumerate(['a','b','c','alpha','beta','gamma']):
                    params.append({"id": param_id, "name": n, "line": phase_start+idx+3, "position": i, "phase": phase_no, "group": "晶胞参数"})
                    param_id += 1
                break
        # 不对称与择优
        for idx, l in enumerate(phase_lines):
            if 'Pref1' in l and 'Pref2' in l and 'Asy1' in l:
                for i, n in enumerate(['Pref1','Pref2','Asy1','Asy2','Asy3','Asy4']):
                    params.append({"id": param_id, "name": n, "line": phase_start+idx+3, "position": i, "phase": phase_no, "group": "不对称与择优参数"})
                    param_id += 1
                break
        # 原子参数
        atom_start = -1  # 原子参数起始行
        for idx, l in enumerate(phase_lines):
            if "Atom" in l and "Typ" in l and "X" in l and "Y" in l and "Z" in l:
                atom_start = idx+1  # 找到原子参数表头
                break
        if atom_start > 0:
            for atom in atom_names:  # 遍历所有原子名
                for idx2 in range(atom_start, len(phase_lines)):
                    if phase_lines[idx2].strip().startswith(atom + " "):  # 找到该原子
                        nums = re.findall(r"[-+]?\d*\.\d+|\d+", phase_lines[idx2])  # 提取数值
                        for i, pname in enumerate(["X", "Y", "Z", "Biso", "Occ"]):  # 坐标、B因子、占位
                            params.append({
                                "id": param_id,
                                "name": f"{atom}_{pname}",
                                "line": phase_start+idx2+2,
                                "position": i,
                                "phase": phase_no,
                                "group": "原子参数"
                            })
                            param_id += 1
                        break
    return params  # 返回所有参数

def parse_tof_pcr(filepath, n_bg, atom_names, bg_mode):
    # 解析TOF类型pcr文件，返回参数列表
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()  # 读取所有行
    params = []  # 参数列表
    param_id = 1  # 参数编号初始值

    # 仪器参数
    for idx, line in enumerate(lines):
        if 'Zero' in line and 'Code' in line and 'Dtt2' in line and '2ThetaBank' in line:
            vals = lines[idx+1].split()
            params.append({"id": param_id, "name": "Zero", "line": idx+2, "position": 1}); param_id += 1
            params.append({"id": param_id, "name": "Dtt1", "line": idx+2, "position": 3}); param_id += 1
            params.append({"id": param_id, "name": "Dtt2", "line": idx+2, "position": 5}); param_id += 1
            params.append({"id": param_id, "name": "Dtt_1overd", "line": idx+2, "position": 7}); param_id += 1
            break

    # 背底参数
    if bg_mode == "poly":
        bg_params, param_id = parse_poly_bg_params_tof(lines, param_id)
    else:
        bg_params, param_id = parse_manual_bg_params_tof(lines, param_id)
    params.extend(bg_params)

    # phase分割
    phase_indices = []
    phase_numbers = []
    for idx, line in enumerate(lines):
        m = re.match(r'!\s*Data for PHASE number:\s*(\d+)', line)
        if m:
            phase_indices.append(idx)
            phase_numbers.append(int(m.group(1)))
    phase_indices.append(len(lines))

    for pidx in range(len(phase_indices)-1):
        phase_start = phase_indices[pidx]
        phase_end = phase_indices[pidx+1]
        phase_lines = lines[phase_start:phase_end]
        phase_no = phase_numbers[pidx]

        # 全局参数
        for idx, l in enumerate(phase_lines):
            if 'Scale' in l and 'Extinc' in l and 'Bov' in l:
                for i, n in enumerate(['Scale','Extinc','Bov','Str1','Str2','Str3']):
                    params.append({"id": param_id, "name": n, "line": phase_start+idx+3, "position": i, "phase": phase_no, "group": "全局参数"})
                    param_id += 1
                break
        # 峰型参数
        for idx, l in enumerate(phase_lines):
            if 'Sigma-2' in l and 'Sigma-1' in l and 'Sigma-0' in l:
                for i, n in enumerate(['Sigma-2','Sigma-1','Sigma-0','Sigma-Q','Iso-GStrain','Iso-GSize','Ani-LSize']):
                    params.append({"id": param_id, "name": n, "line": phase_start+idx+4, "position": i, "phase": phase_no, "group": "峰型参数"})
                    param_id += 1
                break
        for idx, l in enumerate(phase_lines):
            if 'Gamma-2' in l and 'Gamma-1' in l and 'Gamma-0' in l:
                for i, n in enumerate(['Gamma-2','Gamma-1','Gamma-0','Iso-LorStrain','Iso-LorSize']):
                    params.append({"id": param_id, "name": n, "line": phase_start+idx+4, "position": i, "phase": phase_no, "group": "峰型参数"})
                    param_id += 1
                break
        # 晶胞参数
        for idx, l in enumerate(phase_lines):
            if 'a' in l and 'b' in l and 'c' in l and 'alpha' in l:
                for i, n in enumerate(['a','b','c','alpha','beta','gamma']):
                    params.append({"id": param_id, "name": n, "line": phase_start+idx+3, "position": i, "phase": phase_no, "group": "晶胞参数"})
                    param_id += 1
                break
        # 择优与不对称参数
        for idx, l in enumerate(phase_lines):
            if 'Pref1' in l and 'Pref2' in l and 'alph0' in l:
                for i, n in enumerate(['Pref1','Pref2','alph0','beta0','alph1','beta1','alphQ','betaQ']):
                    params.append({"id": param_id, "name": n, "line": phase_start+idx+4, "position": i, "phase": phase_no, "group": "不对称与择优参数"})
                    param_id += 1
                break
        # 吸收矫正参数
        for idx, l in enumerate(phase_lines):
            if '!Absorption correction parameters' in l:
                vals = phase_lines[idx+1].split()
                params.append({
                    "id": param_id,
                    "name": "Abs1",
                    "line": phase_start + idx + 2,
                    "position": 1,
                    "phase": phase_no,
                    "group": "吸收矫正参数"
                }); param_id += 1
                params.append({
                    "id": param_id,
                    "name": "Abs2",
                    "line": phase_start + idx + 2,
                    "position": 3,
                    "phase": phase_no,
                    "group": "吸收矫正参数"
                }); param_id += 1
                break
        # 原子参数
        atom_start = -1
        for idx, l in enumerate(phase_lines):
            if "Atom" in l and "Typ" in l and "X" in l and "Y" in l and "Z" in l:
                atom_start = idx+1
                break
        if atom_start > 0:
            for atom in atom_names:
                for idx2 in range(atom_start, len(phase_lines)):
                    if phase_lines[idx2].strip().startswith(atom + " "):
                        nums = re.findall(r"[-+]?\d*\.\d+|\d+", phase_lines[idx2])
                        for i, pname in enumerate(["X", "Y", "Z", "Biso", "Occ"]):
                            params.append({
                                "id": param_id,
                                "name": f"{atom}_{pname}",
                                "line": phase_start+idx2+2,
                                "position": i,
                                "phase": phase_no,
                                "group": "原子参数"
                            })
                            param_id += 1
                        break
    return params

def parse_pcr_auto(filepath, n_bg, atom_names, bg_mode):
    # 自动判断pcr类型并调用对应解析函数
    ensure_chi2_line(filepath)  # 确保chi2行存在
    job_type = get_job_type(filepath)  # 获取job类型
    if job_type == 0:
        return parse_xrd_pcr(filepath, atom_names, bg_mode)  # XRD
    elif job_type == -1:
        return parse_tof_pcr(filepath, n_bg, atom_names, bg_mode)  # TOF
    else:
        raise RuntimeError("未知的job类型，无法解析pcr文件")  # 未知类型报错

class ParamLibGUI(QWidget):
    # 参数库生成主界面
    def __init__(self):
        super().__init__()  # 调用父类构造
        self.setWindowTitle("Magia_PCR_Reader_v1.0")  # 设置窗口标题
        self.resize(1100, 800)  # 设置窗口大小
        self.pcr_path = ""  # 当前pcr文件路径
        self.params = []  # 参数列表
        self.instrument_params = []  # 仪器参数
        self.bg_params = []  # 背底参数

        layout = QVBoxLayout()  # 主布局

        font_layout = QHBoxLayout()  # 字体设置布局
        font_layout.addWidget(QLabel("字体大小:"))  # 添加标签
        self.font_combo = QComboBox()  # 字体大小下拉框
        self.font_combo.addItems([str(i) for i in range(8, 25, 2)])  # 添加选项
        self.font_combo.setCurrentText("15")  # 默认字体大小
        self.font_combo.currentTextChanged.connect(self.on_font_size_changed)  # 绑定事件
        font_layout.addWidget(self.font_combo)
        font_layout.addStretch()
        layout.addLayout(font_layout)

        # 背底读取方式选择
        bg_mode_layout = QHBoxLayout()
        bg_mode_layout.addWidget(QLabel("背底读取方式:"))
        self.bg_mode_combo = QComboBox()
        self.bg_mode_combo.addItems(["多项式背底", "手动插值背底"])
        bg_mode_layout.addWidget(self.bg_mode_combo)
        bg_mode_layout.addStretch()
        layout.addLayout(bg_mode_layout)

        file_layout = QHBoxLayout()  # 文件选择布局
        self.file_label = QLabel("未选择pcr文件")  # 文件名标签
        self.file_btn = QPushButton("选择pcr文件")  # 选择按钮
        self.file_btn.clicked.connect(self.on_select_pcr)  # 绑定事件
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.file_btn)
        layout.addLayout(file_layout)

        input_layout = QHBoxLayout()  # 原子名输入布局
        input_layout.addWidget(QLabel("原子名称(英文逗号分隔):"))
        self.atom_edit = QLineEdit("输入所有原子名称（确保pcr中没有重名！）")  # 原子名输入框
        input_layout.addWidget(self.atom_edit)
        self.recog_btn = QPushButton("自动识别参数")  # 识别按钮
        self.recog_btn.clicked.connect(self.on_recognize)  # 绑定事件
        input_layout.addWidget(self.recog_btn)
        layout.addLayout(input_layout)

        self.inst_bg_text = QTextEdit()  # 仪器/背底参数展示区
        self.inst_bg_text.setReadOnly(True)
        self.inst_bg_text.setMaximumHeight(250)
        layout.addWidget(self.inst_bg_text)

        self.tab_widget = QTabWidget()  # 参数分相展示区
        layout.addWidget(self.tab_widget)

        export_layout = QHBoxLayout()  # 导出按钮布局
        self.export_btn = QPushButton("导出为JSON")  # 导出按钮
        self.export_btn.clicked.connect(self.on_export_json)  # 绑定事件
        export_layout.addStretch()
        export_layout.addWidget(self.export_btn)
        layout.addLayout(export_layout)

        self.setLayout(layout)  # 设置主布局

    def on_font_size_changed(self, size_str):
        # 字体大小变更事件
        size = int(size_str)  # 转为整数
        font = QFont()
        font.setPointSize(size)  # 设置字体大小
        self.setFont(font)  # 应用到窗口

    def on_select_pcr(self):
        # 选择pcr文件事件
        file_path, _ = QFileDialog.getOpenFileName(self, "选择pcr文件", "", "PCR Files (*.txt *.pcr);;All Files (*)")
        if file_path:
            try:
                utf8_path = detect_and_convert_to_utf8(file_path)  # 检测并转换编码
                self.pcr_path = utf8_path  # 保存路径
                self.file_label.setText(os.path.basename(utf8_path))  # 显示文件名
                if utf8_path != file_path:
                    QMessageBox.information(self, "编码转换", f"检测到pcr文件不是UTF-8编码，已自动转换为UTF-8：\n{utf8_path}，后续请使用转换后的pcr进行自动精修！！！")
            except Exception as e:
                QMessageBox.warning(self, "文件编码错误", str(e))  # 编码错误提示

    def on_recognize(self):
        # 自动识别参数事件
        if not self.pcr_path:
            QMessageBox.warning(self, "提示", "请先选择pcr文件")
            return
        atom_names = [x.strip() for x in self.atom_edit.text().replace('\n', ',').split(',') if x.strip()]  # 获取原子名
        bg_mode = "poly" if self.bg_mode_combo.currentText() == "多项式背底" else "manual"  # 背底模式
        try:
            self.params = parse_pcr_auto(self.pcr_path, 0, atom_names, bg_mode)  # 解析参数
            self.refresh_tabs()  # 刷新展示
        except Exception as e:
            QMessageBox.critical(self, "解析错误", str(e))
            return

    def refresh_tabs(self):
        # 刷新参数展示区
        self.tab_widget.clear()
        inst_names = {"Zero", "SyCos", "SySin", "Lambda", "Dtt1", "Dtt2", "Dtt_1overd"}  # 仪器参数名集合
        bg_names = {f"d_{i}" for i in range(6)} | {f"BG{i+1}" for i in range(100)}  # 背底参数名集合
        self.instrument_params = [p for p in self.params if p["name"] in inst_names]  # 筛选仪器参数
        self.bg_params = [p for p in self.params if p["name"] in bg_names]  # 筛选背底参数
        inst_text = "仪器参数：\n"
        for p in self.instrument_params:
            inst_text += f'{p["name"]} (行{p["line"]}, 列{p["position"]})\n'
        inst_text += "\n背底参数：\n"
        for p in self.bg_params:
            val_str = f' 值={p["value"]}' if "value" in p else ""
            inst_text += f'{p["name"]} (行{p["line"]}, 列{p["position"]}){val_str}\n'
        self.inst_bg_text.setText(inst_text)
    
        phase_params = [p for p in self.params if "phase" in p]  # 所有含相信息的参数
        phase_dict = {}
        for p in phase_params:
            phase = f'phase{p["phase"]}'
            phase_dict.setdefault(phase, []).append(p)
        for phase, plist in phase_dict.items():
            tab = QWidget()
            tab_layout = QVBoxLayout()
            group_order = ["全局参数", "峰型参数", "晶胞参数", "不对称与择优参数", "吸收矫正参数", "原子参数"]
            for group in group_order:
                group_box = QGroupBox(group)
                form = QFormLayout()
                for p in plist:
                    if p.get("group") == group:
                        form.addRow(QLabel(p["name"]), QLabel(f'行{p["line"]} 列{p["position"]}'))
                group_box.setLayout(form)
                tab_layout.addWidget(group_box)
            tab_layout.addStretch()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            tab_content = QWidget()
            tab_content.setLayout(tab_layout)
            scroll.setWidget(tab_content)
            self.tab_widget.addTab(scroll, phase)
        if not phase_dict:
            self.tab_widget.clear()

    def on_export_json(self):
        # 导出参数为JSON文件
        if not self.params:
            QMessageBox.warning(self, "提示", "请先识别参数")
            return
        save_path, _ = QFileDialog.getSaveFileName(self, "保存JSON文件", "", "JSON Files (*.json)")
        if save_path:
            out = {"parameters_library": self.params}
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "导出成功", f"已保存到 {save_path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)  # 创建应用
    win = ParamLibGUI()  # 创建主窗口
    win.show()  # 显示窗口
    sys.exit(app.exec_())  # 进入主事件循环