import os
import sys
import re
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QTabWidget, QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem, QMessageBox, QTextEdit, QScrollArea, QComboBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

'''
可以自动读取原子参数了！
'''

def detect_and_convert_to_utf8(filepath, encodings=('utf-8', 'gbk', 'gb2312', 'latin1')):
    last_exc = None
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
            if enc != 'utf-8':
                utf8_path = os.path.splitext(filepath)[0] + "_UTF_8.pcr"
                with open(utf8_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return utf8_path
            else:
                return filepath
        except Exception as e:
            last_exc = e
    raise RuntimeError(f"无法识别pcr文件编码，请尝试另存为UTF-8或GBK编码\n详细信息: {last_exc}")

def ensure_chi2_line(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    chi2_line = [i for i, l in enumerate(lines) if l.strip().startswith('! Current global Chi2')]
    if not chi2_line:
        lines.insert(1, '! Current global Chi2 (Bragg contrib.) =      \n')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    return filepath

def get_job_type(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for idx, line in enumerate(lines):
        if line.strip().lower().startswith('!job'):
            job_value = int(lines[idx+1].split()[0])
            return job_value
    return 0  # 默认XRD

def parse_poly_bg_params_xrd(lines, param_id):
    params = []
    for idx, line in enumerate(lines):
        if 'Background coefficients/codes' in line and 'Polynomial' in line:
            for i in range(6):
                params.append({"id": param_id, "name": f"d_{i}", "line": idx+3, "position": i})
                param_id += 1
            break
    return params, param_id

def parse_manual_bg_params_xrd(lines, param_id):
    params = []
    for idx, line in enumerate(lines):
        if "Background" in line and "Pattern#" in line:
            bg_idx = idx + 1
            while bg_idx < len(lines):
                l = lines[bg_idx]
                if l.strip().startswith('!'):
                    break
                vals = l.strip().split()
                if len(vals) >= 3:
                    params.append({
                        "id": param_id,
                        "name": f"BG{len(params)+1}",
                        "line": bg_idx+1,
                        "position": 2,
                        "value": vals[2]
                    })
                    param_id += 1
                bg_idx += 1
            break
    return params, param_id

def parse_poly_bg_params_tof(lines, param_id):
    params = []
    for idx, line in enumerate(lines):
        if 'Background coefficients/codes' in line and 'Polynomial' in line:
            for i in range(6):
                params.append({"id": param_id, "name": f"d_{i}", "line": idx+3, "position": i})
                param_id += 1
            break
    return params, param_id

def parse_manual_bg_params_tof(lines, param_id):
    params = []
    for idx, line in enumerate(lines):
        if "Background" in line and "Pattern#" in line:
            bg_idx = idx + 1
            while bg_idx < len(lines):
                l = lines[bg_idx]
                if l.strip().startswith('!'):
                    break
                vals = l.strip().split()
                if len(vals) >= 3:
                    params.append({
                        "id": param_id,
                        "name": f"BG{len(params)+1}",
                        "line": bg_idx+1,
                        "position": 2,
                        "value": vals[2]
                    })
                    param_id += 1
                bg_idx += 1
            break
    return params, param_id

def parse_xrd_pcr(filepath, atom_names, bg_mode):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    params = []
    param_id = 1

    # 仪器参数
    for idx, line in enumerate(lines):
        if 'Zero' in line and 'SyCos' in line and 'SySin' in line and 'Lambda' in line:
            vals = lines[idx+1].split()
            params.append({"id": param_id, "name": "Zero", "line": idx+2, "position": 1}); param_id += 1
            params.append({"id": param_id, "name": "SyCos", "line": idx+2, "position": 3}); param_id += 1
            params.append({"id": param_id, "name": "SySin", "line": idx+2, "position": 5}); param_id += 1
            params.append({"id": param_id, "name": "Lambda", "line": idx+2, "position": 7}); param_id += 1
            break

    # 背底参数
    if bg_mode == "poly":
        bg_params, param_id = parse_poly_bg_params_xrd(lines, param_id)
    else:
        bg_params, param_id = parse_manual_bg_params_xrd(lines, param_id)
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

def parse_tof_pcr(filepath, n_bg, atom_names, bg_mode):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    params = []
    param_id = 1

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
                    params.append({"id": param_id, "name": n, "line": phase_start+idx+3, "position": i, "phase": phase_no, "group": "峰型参数"})
                    param_id += 1
                break
        for idx, l in enumerate(phase_lines):
            if 'Gamma-2' in l and 'Gamma-1' in l and 'Gamma-0' in l:
                for i, n in enumerate(['Gamma-2','Gamma-1','Gamma-0','Iso-LorStrain','Iso-LorSize']):
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
        # 择优与不对称参数
        for idx, l in enumerate(phase_lines):
            if 'Pref1' in l and 'Pref2' in l and 'alph0' in l:
                for i, n in enumerate(['Pref1','Pref2','alph0','beta0','alph1','beta1','alphQ','betaQ']):
                    params.append({"id": param_id, "name": n, "line": phase_start+idx+3, "position": i, "phase": phase_no, "group": "不对称与择优参数"})
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
                atom_start = idx + 1
                break
        if atom_start > 0:
            idx2 = atom_start
            while idx2 < len(phase_lines):
                line = phase_lines[idx2].strip()
                if not line or line.startswith("!"):
                    idx2 += 1
                    continue
                parts = line.split()
                atom_name = parts[0] if len(parts) > 0 else ""
                if atom_name in atom_names:
                    # 判断是否为各向异性（该原子参数后有4行，第3行为6个浮点数）
                    is_aniso = False
                    if idx2 + 3 < len(phase_lines):
                        aniso_line = phase_lines[idx2 + 2].strip()
                        aniso_parts = aniso_line.split()
                        if len(aniso_parts) == 6 and all(re.match(r"[-+]?\d*\.\d+|\d+", x) for x in aniso_parts):
                            is_aniso = True
                    # 读取坐标
                    for i, pname in enumerate(["X", "Y", "Z"]):
                        params.append({
                            "id": param_id,
                            "name": f"{atom_name}_{pname}",
                            "line": phase_start + idx2 + 2,
                            "position": i,
                            "phase": phase_no,
                            "group": "原子参数"
                        })
                        param_id += 1
                    if is_aniso:
                        # 各向异性B值（第3行）
                        for j, bname in enumerate(["B11", "B22", "B33", "B12", "B13", "B23"]):
                            params.append({
                                "id": param_id,
                                "name": f"{atom_name}_{bname}",
                                "line": phase_start + idx2 + 4,
                                "position": j,
                                "phase": phase_no,
                                "group": "原子参数"
                            })
                            param_id += 1
                        # Occ 仍然在第1行
                        params.append({
                            "id": param_id,
                            "name": f"{atom_name}_Occ",
                            "line": phase_start + idx2 + 2,
                            "position": 4,
                            "phase": phase_no,
                            "group": "原子参数"
                        })
                        param_id += 1
                        idx2 += 4  # 跳过4行
                    else:
                        # 各向同性B值（第1行）
                        params.append({
                            "id": param_id,
                            "name": f"{atom_name}_Biso",
                            "line": phase_start + idx2 + 2,
                            "position": 3,
                            "phase": phase_no,
                            "group": "原子参数"
                        })
                        param_id += 1
                        # Occ
                        params.append({
                            "id": param_id,
                            "name": f"{atom_name}_Occ",
                            "line": phase_start + idx2 + 2,
                            "position": 4,
                            "phase": phase_no,
                            "group": "原子参数"
                        })
                        param_id += 1
                        idx2 += 2  # 跳过2行
                else:
                    idx2 += 1
    return params

def parse_pcr_auto(filepath, n_bg, atom_names, bg_mode):
    ensure_chi2_line(filepath)
    job_type = get_job_type(filepath)
    if job_type == 0:
        return parse_xrd_pcr(filepath, atom_names, bg_mode)
    elif job_type == -1:
        return parse_tof_pcr(filepath, n_bg, atom_names, bg_mode)
    else:
        raise RuntimeError("未知的job类型，无法解析pcr文件")

def extract_atom_names_from_pcr(pcr_path):
    atom_names = []
    with open(pcr_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    atom_section = False
    for idx, line in enumerate(lines):
        if re.match(r'!Atom\s+Typ\s+X\s+Y\s+Z\s+Biso\s+Occ', line):
            atom_section = True
            continue
        if atom_section:
            # 跳过注释和空行
            if line.strip() == "" or line.strip().startswith("!"):
                # 如果遇到下一个参数块或空行，结束
                if line.strip() == "" or (line.strip().startswith("!") and not line.strip().startswith("!    beta")):
                    atom_section = False
                continue
            parts = line.strip().split()
            # 只提取首列为字母开头且长度大于1的原子名
            if len(parts) >= 2 and re.match(r'^[A-Za-z]', parts[0]) and parts[0] not in atom_names:
                atom_names.append(parts[0])
    return atom_names

class ParamLibGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Magia_PCR_Reader_v1.0")
        self.resize(1100, 800)
        self.pcr_path = ""
        self.params = []
        self.instrument_params = []
        self.bg_params = []

        layout = QVBoxLayout()

        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("字体大小:"))
        self.font_combo = QComboBox()
        self.font_combo.addItems([str(i) for i in range(8, 25, 2)])
        self.font_combo.setCurrentText("15")
        self.font_combo.currentTextChanged.connect(self.on_font_size_changed)
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

        file_layout = QHBoxLayout()
        self.file_label = QLabel("未选择pcr文件")
        self.file_btn = QPushButton("选择pcr文件")
        self.file_btn.clicked.connect(self.on_select_pcr)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.file_btn)
        layout.addLayout(file_layout)

        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("请检查识别后的原子名称(英文逗号分隔):"))
        self.atom_edit = QLineEdit("（请确保pcr中没有原子重名！直接点击“自动识别参数”）")
        input_layout.addWidget(self.atom_edit)
        self.recog_btn = QPushButton("自动识别参数")
        self.recog_btn.clicked.connect(self.on_recognize)
        input_layout.addWidget(self.recog_btn)
        layout.addLayout(input_layout)

        self.inst_bg_text = QTextEdit()
        self.inst_bg_text.setReadOnly(True)
        self.inst_bg_text.setMaximumHeight(250)
        layout.addWidget(self.inst_bg_text)

        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        export_layout = QHBoxLayout()
        self.export_btn = QPushButton("导出为JSON")
        self.export_btn.clicked.connect(self.on_export_json)
        export_layout.addStretch()
        export_layout.addWidget(self.export_btn)
        layout.addLayout(export_layout)

        self.setLayout(layout)

    def on_font_size_changed(self, size_str):
        size = int(size_str)
        font = QFont()
        font.setPointSize(size)
        self.setFont(font)

    def on_select_pcr(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择pcr文件", "", "PCR Files (*.txt *.pcr);;All Files (*)")
        if file_path:
            try:
                utf8_path = detect_and_convert_to_utf8(file_path)
                self.pcr_path = utf8_path
                self.file_label.setText(os.path.basename(utf8_path))
                if utf8_path != file_path:
                    QMessageBox.information(self, "编码转换", f"检测到pcr文件不是UTF-8编码，已自动转换为UTF-8：\n{utf8_path}，后续请使用转换后的pcr进行自动精修！！！")
            except Exception as e:
                QMessageBox.warning(self, "文件编码错误", str(e))

    def on_recognize(self):
        if not self.pcr_path:
            QMessageBox.warning(self, "提示", "请先选择pcr文件")
            return
        # 自动提取原子名称
        atom_names = extract_atom_names_from_pcr(self.pcr_path)
        self.atom_edit.setText(",".join(atom_names))  # 自动填充到输入框
        bg_mode = "poly" if self.bg_mode_combo.currentText() == "多项式背底" else "manual"
        try:
            self.params = parse_pcr_auto(self.pcr_path, 0, atom_names, bg_mode)
            self.refresh_tabs()
        except Exception as e:
            QMessageBox.critical(self, "解析错误", str(e))
            return

    def refresh_tabs(self):
        self.tab_widget.clear()
        inst_names = {"Zero", "SyCos", "SySin", "Lambda", "Dtt1", "Dtt2", "Dtt_1overd"}
        bg_names = {f"d_{i}" for i in range(6)} | {f"BG{i+1}" for i in range(100)}
        self.instrument_params = [p for p in self.params if p["name"] in inst_names]
        self.bg_params = [p for p in self.params if p["name"] in bg_names]
        inst_text = "仪器参数：\n"
        for p in self.instrument_params:
            inst_text += f'{p["name"]} (行{p["line"]}, 列{p["position"]})\n'
        inst_text += "\n背底参数：\n"
        for p in self.bg_params:
            val_str = f' 值={p["value"]}' if "value" in p else ""
            inst_text += f'{p["name"]} (行{p["line"]}, 列{p["position"]}){val_str}\n'
        self.inst_bg_text.setText(inst_text)
    
        phase_params = [p for p in self.params if "phase" in p]
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
    app = QApplication(sys.argv)
    app.setFont(QFont("微软雅黑"))
    win = ParamLibGUI()
    win.show()
    sys.exit(app.exec_())