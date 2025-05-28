import sys
import os
import re
import json
import threading
import time
from datetime import datetime
from collections import deque
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QComboBox, QTabWidget, QTextEdit, QProgressBar, QMessageBox,
    QSpinBox, QGroupBox, QSplitter, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal,QTimer

CONFIG_FILE = "refine_gui_config.json"

def read_text_autoenc(filepath, encodings=('utf-8', 'gbk', 'gb2312', 'latin1')):
    last_exc = None
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.readlines()
        except Exception as e:
            last_exc = e
    raise UnicodeDecodeError(
        "auto", b"", 0, 1,
        f"无法识别pcr文件编码，请尝试另存为UTF-8或GBK编码\n详细信息: {last_exc}"
    )

def read_text_autoenc_content(filepath, encodings=('utf-8', 'gbk', 'gb2312', 'latin1')):
    last_exc = None
    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except Exception as e:
            last_exc = e
    raise UnicodeDecodeError(
        "auto", b"", 0, 1,
        f"无法识别pcr文件编码，请尝试另存为UTF-8或GBK编码\n详细信息: {last_exc}"
    )

def save_config(data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def search_fp2k():
    # 常见路径
    candidates = []
    for root in [r"C:\FullProf_Suite", r"C:\Program Files", r"C:\Program Files (x86)", r"C:\\"]:
        for dirpath, dirnames, filenames in os.walk(root):
            for fname in filenames:
                if fname.lower() == "fp2k.exe":
                    candidates.append(os.path.join(dirpath, fname))
            if len(candidates) > 10:
                return candidates
    # C盘全盘搜索（慢）
    for dirpath, dirnames, filenames in os.walk("C:\\"):
        for fname in filenames:
            if fname.lower() == "fp2k.exe":
                candidates.append(os.path.join(dirpath, fname))
        if len(candidates) > 10:
            break
    return candidates

class RefinementWorker(QThread):
    log_signal = pyqtSignal(str, str)  # (log_type, message)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str)

    def __init__(self, config, steps, run_indices):
        super().__init__()
        self.config = config
        self.steps = steps
        self.run_indices = run_indices
        self._pause = False
        self._stop = False

    def run(self):
        TEMP_DIR = os.path.join(os.path.dirname(self.config['pcr_path']), "temporary_files")
        MAX_KEEP_STEPS = self.config.get("maxfiles", 5)
        ERROR_LOG_PATH = os.path.join(TEMP_DIR, "error_history.txt")
        WARNING_FILE = os.path.join(TEMP_DIR, "convergence_warnings.txt")
        paramlib_path = self.config['paramlib_path']
        with open(paramlib_path, "r", encoding="utf-8") as f:
            param_lib_list = json.load(f)["parameters_library"]
        param_lib = {i+1: p for i, p in enumerate(param_lib_list)}
        if os.path.exists(TEMP_DIR):
            import shutil
            shutil.rmtree(TEMP_DIR)
        os.makedirs(TEMP_DIR, exist_ok=True)
        file_history = deque(maxlen=MAX_KEEP_STEPS)
        current_template = self.config['pcr_path']
        if os.path.exists(ERROR_LOG_PATH):
            os.remove(ERROR_LOG_PATH)
        total = len(self.run_indices)
        for idx, step_idx in enumerate(self.run_indices):
            if self._stop:
                self.log_signal.emit("main", f"[主日志] 已终止于步骤 {step_idx+1}")
                break
            while self._pause:
                time.sleep(0.2)
            step = self.steps[step_idx]
            try:
                step_number = idx + 1
                safe_step_name = re.sub(r'[^a-zA-Z0-9_]', '_', step['name'])
                base_name = f"step_{step_number:03d}_{safe_step_name}"
                template_path = current_template
                new_pcr_path = os.path.join(TEMP_DIR, f"{base_name}.pcr")
                active_param_ids = [ap['id'] for ap in step['active_params']]
                self.modify_pcr_template(
                    template_path=template_path,
                    output_path=new_pcr_path,
                    active_param_ids=active_param_ids,
                    param_lib=param_lib,
                    active_params=step['active_params']
                )
                param_names = [param_lib[pid].get('name', str(pid)) for pid in active_param_ids]
                new_dat_path = os.path.join(TEMP_DIR, f"{base_name}.dat")
                import shutil
                shutil.copyfile(self.config['data_path'], new_dat_path)
                current_template = new_pcr_path
                step_files = [os.path.join(TEMP_DIR, f"{base_name}{ext}") for ext in ['.out', '.prf', '.pcr', '.mic', '.dat', '.fst', '.log', '.sum']]
                file_history.append(step_files)
                while len(file_history) > MAX_KEEP_STEPS:
                    old_files = file_history.popleft()
                    for f in old_files:
                        if os.path.exists(f):
                            try:
                                os.remove(f)
                            except Exception:
                                pass
                self.log_signal.emit("main", f"\n🚀 步骤 {idx+1}/{total}: {step['name']}")
                self.log_signal.emit("main", f"🛠️ 正在精修: {', '.join(param_names)}")
                success, error_info = self.run_fullprof_process(
                    fullprof_path=self.config['fullprof_path'],
                    pcr_path=new_pcr_path,
                    timeout=self.config.get('timeout', 3600),
                    show_window=False,
                    temp_dir=TEMP_DIR
                )
                if not success:
                    self.log_signal.emit("err", f"⏩ 自动跳过出错步骤: {step['name']}\n{error_info}")
                    self.log_error(ERROR_LOG_PATH, step['name'], error_info)
                    continue
                chi = self.extract_chi_value(new_pcr_path)
                if chi is not None:
                    self.log_signal.emit("chi", f"Step {step['name']} Chi²: {chi:.2f}")
                else:
                    self.log_signal.emit("warn", f"⚠️ 未检测到Chi²值")
                self.progress_signal.emit(int((idx+1)/total*100))
            except Exception as e:
                error_info = f"非预期错误: {str(e)}"
                self.log_signal.emit("err", f"❌ 步骤失败: {step['name']}\n📝 错误信息: {error_info}")
                self.log_error(ERROR_LOG_PATH, step['name'], error_info)
                continue
        self.progress_signal.emit(100)
        self.finished_signal.emit("精修已完成！报告已生成。")

    def modify_pcr_template(self, template_path, output_path, active_param_ids, param_lib, active_params=None):
        try:
            lines = read_text_autoenc(template_path)
        except Exception as e:
            QMessageBox.critical(None, "编码错误", str(e))
            raise
        param_positions = {}
        for pid, param in param_lib.items():
            param_positions[pid] = (param['line']-1, param['position'])
        id2value = {}
        if active_params is not None:
            for ap in active_params:
                id2value[ap['id']] = ap['value']
        active_ids = set(active_param_ids)
        for pid, (line_idx, pos_idx) in param_positions.items():
            parts = lines[line_idx].strip().split()
            if pos_idx >= len(parts):
                continue
            if pid in active_ids and pid in id2value:
                parts[pos_idx] = f"{id2value[pid]:.2f}"
            else:
                parts[pos_idx] = "0.00"
            lines[line_idx] = '    '.join(parts) + '\n'
        target_dat = os.path.basename(output_path).replace('.pcr', '.dat')
        for idx, line in enumerate(lines):
            if re.search(r"!\s*Files => DAT-file:\s*([^,\s]+\.dat)\s*", line, re.IGNORECASE):
                lines[idx] = re.sub(
                    r"(DAT-file:\s*)([^,\s]+\.dat)",
                    f"\\1{target_dat}",
                    line
                )
                break
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    def run_fullprof_process(self, fullprof_path, pcr_path, timeout, show_window, temp_dir):
        log_path = pcr_path.replace('.pcr', '.log')
        WARNING_FILE = os.path.join(temp_dir, "convergence_warnings.txt")
        buffer = deque(maxlen=2)
        startupinfo = None
        creationflags = 0
        if os.name == 'nt':
            startupinfo = None
            creationflags = 0
        try:
            with open(log_path, 'w', encoding='utf-8') as log_file:
                process = None
                try:
                    process = __import__('subprocess').Popen(
                        [fullprof_path, os.path.basename(pcr_path)],
                        cwd=os.path.dirname(pcr_path),
                        stdout=__import__('subprocess').PIPE,
                        stderr=__import__('subprocess').STDOUT,
                        text=True,
                        startupinfo=startupinfo,
                        creationflags=creationflags,
                        bufsize=1
                    )
                except Exception as e:
                    self.log_signal.emit("err", f"FullProf启动失败: {e}")
                    return False, f"FullProf启动失败: {e}"
                error_flag = False
                error_message = ""
                with process.stdout as pipe:
                    for line in iter(pipe.readline, ''):
                        log_file.write(line)
                        self.log_signal.emit("main", line.rstrip())
                        buffer.append(line.strip())
                        # === 新增：检测未收敛警告 ===
                        warning_message = ""
                        if len(buffer) >= 2:
                            prev_line = buffer[-2]
                            current_line = buffer[-1]
                            if "Conv. not yet reached" in prev_line and "Normal end, final calculations and writing..." in current_line:
                                value_match = re.search(r'=\s*([\d.]+)', prev_line)
                                if value_match:
                                    unconverged_value = value_match.group(1)
                                    step_name = os.path.splitext(os.path.basename(pcr_path))[0]
                                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    with open(WARNING_FILE, 'a', encoding='utf-8') as f_warn:
                                        f_warn.write(
                                            f"[{timestamp}] 步骤: {step_name}\n"
                                            f"未收敛的值: {unconverged_value}\n"
                                            f"{'-'*40}\n"
                                        )
                                    warning_message = f"⚠️ 检测到 {step_name} 未收敛，已记录至: {os.path.basename(WARNING_FILE)}"
                                    self.log_signal.emit("warn", warning_message)
                        # === 原有错误检测 ===
                        if "Lorentzian-FWHM < 0" in line:
                            error_flag = True
                            error_message = "FWHM值异常：检测到负峰宽"
                        elif "W A R N I N G: negative GAUSSIAN FWHM somewhere" in line:
                            error_flag = True
                            error_message = "高斯半峰宽异常：检测到负值"
                        elif "Singular matrix" in line:
                            error_flag = True
                            error_message = "奇异矩阵出现！"
                        elif "Negative intensity" in line:
                            error_flag = True
                            error_message = "负强度：可能是原子位置或占位率异常"
                        elif "NO REFLECTIONS FOUND" in line:
                            error_flag = True
                            error_message = "NO REFLECTIONS FOUND -> Check your INS parameter for input data and/or ZERO point"
                        if error_flag:
                            process.kill()
                            break
                try:
                    exit_code = process.wait(timeout=timeout)
                except Exception:
                    process.kill()
                    return False, "进程超时"
                return exit_code == 0 and not error_flag, error_message if error_flag else "正常完成"
        except Exception as e:
            return False, f"运行时错误: {str(e)}"

    def extract_chi_value(self, pcr_path):
        out_path = pcr_path.replace('.pcr', '.out')
        if not os.path.exists(out_path):
            return None
        try:
            content = read_text_autoenc_content(out_path)
        except Exception as e:
            QMessageBox.critical(None, "编码错误", str(e))
            return None
        match = re.search(
            r"Global user-weigthed Chi2 \(Bragg contrib\.\):\s*(\d+\.?\d*)",
            content
        )
        return float(match.group(1)) if match else None

    def log_error(self, error_log_path, step_name, error_info):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] Step: {step_name}\nError: {error_info}\n{'='*60}\n"
        try:
            with open(error_log_path, 'a', encoding='utf-8') as f:
                f.write(log_entry)
            self.log_signal.emit("err", f"📝 错误已记录至: {error_log_path}")
        except Exception as e:
            self.log_signal.emit("err", f"⚠️ 无法写入错误日志: {str(e)}")

    def pause(self):
        self._pause = True

    def resume(self):
        self._pause = False

    def stop(self):
        self._stop = True

class LogTabWidget(QTabWidget):
    MAX_DISPLAY_LINES = 100  # 新增：每个日志窗口最多显示100行

    def __init__(self):
        super().__init__()
        self.log_edits = {
            "main": QTextEdit(),
            "warn": QTextEdit(),
            "err": QTextEdit(),
            "chi": QTextEdit()
        }
        for key, edit in self.log_edits.items():
            edit.setReadOnly(True)
            self.addTab(edit, {"main":"主日志","warn":"警告","err":"错误","chi":"Chi²变化"}[key])
        # 搜索和清空
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("日志搜索（支持关键词）")
        self.clear_btn = QPushButton("清空当前日志")
        self.search_box.textChanged.connect(self.on_search)
        self.clear_btn.clicked.connect(self.on_clear)
        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_box)
        search_layout.addWidget(self.clear_btn)
        self.setCornerWidget(QWidget())
        self.cornerWidget().setLayout(search_layout)
        self.log_buffer = {"main": [], "warn": [], "err": [], "chi": []}
        self._pending_update = set()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._flush_logs)
        self._timer.start(100)  # 每100ms刷新一次 ,防止卡死

    def append_log(self, log_type, msg):
        if log_type not in self.log_buffer:
            log_type = "main"
        self.log_buffer[log_type].append(msg)
        # 新增：只保留最新MAX_DISPLAY_LINES行
        if len(self.log_buffer[log_type]) > self.MAX_DISPLAY_LINES:
            self.log_buffer[log_type] = self.log_buffer[log_type][-self.MAX_DISPLAY_LINES:]
        self._pending_update.add(log_type)

    def _flush_logs(self):
        for log_type in list(self._pending_update):
            self.refresh_tab(log_type)
        self._pending_update.clear()

    def refresh_tab(self, log_type):
        edit = self.log_edits[log_type]
        keyword = self.search_box.text().strip()
        # 只显示最新MAX_DISPLAY_LINES行
        lines = self.log_buffer[log_type][-self.MAX_DISPLAY_LINES:]
        if keyword:
            filtered = [line for line in lines if keyword in line]
            edit.setPlainText('\n'.join(filtered))
        else:
            edit.setPlainText('\n'.join(lines))
        edit.moveCursor(edit.textCursor().End)
        
    def on_search(self):
        for key in self.log_edits:
            self.refresh_tab(key)

    def on_clear(self):
        idx = self.currentIndex()
        key = ["main","warn","err","chi"][idx]
        self.log_buffer[key] = []
        self.refresh_tab(key)

    def export_log(self, fname):
        with open(fname, "w", encoding="utf-8") as f:
            for k, logs in self.log_buffer.items():
                f.write(f"==== {k.upper()} ====\n")
                for line in logs:
                    f.write(line + "\n")

class RefinementGUI(QWidget):
    fp2k_found = pyqtSignal(list)  # 新增信号
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Magia_FP_Refinement_v1.0")
        self.setMinimumSize(1100, 700)
        self.resize(1200, 800)
        self.config = load_config()
        self.worker = None
        self.steps = []
        self.param_lib = []
        self.init_ui()
        self.load_last_settings()
        self.fp2k_search_thread = None
        self.fp2k_candidates = []
        self.fp2k_found.connect(self.on_fp2k_found)
        self.auto_search_fp2k()
        

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        # 文件选择区
        file_group = QGroupBox("文件与目录设置")
        file_layout = QVBoxLayout()
        # fp2k
        fp2k_layout = QHBoxLayout()
        self.fp2k_edit = QLineEdit()
        self.fp2k_edit.setReadOnly(True)
        self.fp2k_btn = QPushButton("手动指定fp2k.exe")
        self.fp2k_btn.clicked.connect(self.select_fp2k)
        self.fp2k_combo = QComboBox()
        self.fp2k_combo.setVisible(False)
        self.fp2k_combo.currentIndexChanged.connect(self.fp2k_combo_selected)
        fp2k_layout.addWidget(QLabel("FullProf执行文件(fp2k.exe)："))
        fp2k_layout.addWidget(self.fp2k_edit, 2)
        fp2k_layout.addWidget(self.fp2k_btn)
        fp2k_layout.addWidget(self.fp2k_combo)
        file_layout.addLayout(fp2k_layout)
        # 精修目录
        dir_layout = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setReadOnly(True)
        self.dir_btn = QPushButton("选择精修文件目录")
        self.dir_btn.clicked.connect(self.select_dir)
        dir_layout.addWidget(QLabel("精修文件目录："))
        dir_layout.addWidget(self.dir_edit, 2)
        dir_layout.addWidget(self.dir_btn)
        file_layout.addLayout(dir_layout)
        # pcr/dat选择
        pcrdat_layout = QHBoxLayout()
        self.pcr_combo = QComboBox()
        self.dat_combo = QComboBox()
        pcrdat_layout.addWidget(QLabel("pcr文件："))
        pcrdat_layout.addWidget(self.pcr_combo)
        pcrdat_layout.addWidget(QLabel("dat文件："))
        pcrdat_layout.addWidget(self.dat_combo)
        file_layout.addLayout(pcrdat_layout)
        # 参数库、步骤配置
        param_layout = QHBoxLayout()
        self.param_edit = QLineEdit()
        self.param_edit.setReadOnly(True)
        self.param_btn = QPushButton("选择参数库JSON")
        self.param_btn.clicked.connect(self.select_param)
        self.step_edit = QLineEdit()
        self.step_edit.setReadOnly(True)
        self.step_btn = QPushButton("选择步骤配置JSON")
        self.step_btn.clicked.connect(self.select_step)
        param_layout.addWidget(QLabel("参数库："))
        param_layout.addWidget(self.param_edit, 2)
        param_layout.addWidget(self.param_btn)
        param_layout.addWidget(QLabel("步骤配置："))
        param_layout.addWidget(self.step_edit, 2)
        param_layout.addWidget(self.step_btn)
        file_layout.addLayout(param_layout)
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        # 参数设置区
        param_group = QGroupBox("运行参数")
        paramset_layout = QHBoxLayout()
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 99999)
        self.timeout_spin.setValue(3600)
        self.maxfile_spin = QSpinBox()
        self.maxfile_spin.setRange(1, 9999)
        self.maxfile_spin.setValue(999)
        paramset_layout.addWidget(QLabel("超时时间(秒)："))
        paramset_layout.addWidget(self.timeout_spin)
        paramset_layout.addWidget(QLabel("最大保留文件数："))
        paramset_layout.addWidget(self.maxfile_spin)
        param_group.setLayout(paramset_layout)
        main_layout.addWidget(param_group)
        # 日志与进度区
        splitter = QSplitter(Qt.Vertical)
        self.log_tabs = LogTabWidget()
        splitter.addWidget(self.log_tabs)
        # 进度条
        progress_layout = QHBoxLayout()
        self.progress = QProgressBar()
        progress_layout.addWidget(QLabel("进度："))
        progress_layout.addWidget(self.progress)
        progress_widget = QWidget()
        progress_widget.setLayout(progress_layout)
        splitter.addWidget(progress_widget)
        splitter.setSizes([600, 40])
        main_layout.addWidget(splitter, 5)
        # 控制按钮区
        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("开始精修")
        self.pause_btn = QPushButton("暂停")
        self.resume_btn = QPushButton("继续")
        self.stop_btn = QPushButton("终止")
        self.export_log_btn = QPushButton("导出日志")
        self.export_report_btn = QPushButton("导出报告")
        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.resume_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.export_log_btn)
        btn_layout.addWidget(self.export_report_btn)
        main_layout.addLayout(btn_layout)
        # 事件绑定
        self.run_btn.clicked.connect(self.start_refinement)
        self.pause_btn.clicked.connect(self.pause_refinement)
        self.resume_btn.clicked.connect(self.resume_refinement)
        self.stop_btn.clicked.connect(self.stop_refinement)
        self.export_log_btn.clicked.connect(self.export_log)
        self.export_report_btn.clicked.connect(self.export_report)

    def auto_search_fp2k(self):
        self.fp2k_edit.setText("正在自动搜索fp2k.exe，请稍候...")
        def search():
            candidates = search_fp2k()
            self.fp2k_found.emit(candidates)  # 用信号通知主线程
        t = threading.Thread(target=search, daemon=True)
        t.start()

    def on_fp2k_found(self, candidates):
        self.fp2k_candidates = candidates
        if candidates:
            self.fp2k_combo.clear()
            self.fp2k_combo.addItems(candidates)
            self.fp2k_combo.setVisible(True)
            self.fp2k_edit.setText(candidates[0])
            self.fp2k_combo.setCurrentIndex(0)
        else:
            self.fp2k_edit.setText("")
            self.fp2k_combo.setVisible(False)

    def fp2k_combo_selected(self, idx):
        if 0 <= idx < len(self.fp2k_candidates):
            self.fp2k_edit.setText(self.fp2k_candidates[idx])

    def select_fp2k(self):
        fname, _ = QFileDialog.getOpenFileName(self, "选择fp2k.exe", "", "fp2k.exe (fp2k.exe);;所有文件 (*)")
        if fname:
            self.fp2k_edit.setText(fname)
            self.fp2k_combo.setVisible(False)

    def select_dir(self):
        dname = QFileDialog.getExistingDirectory(self, "选择精修文件目录")
        if dname:
            self.dir_edit.setText(dname)
            self.refresh_pcr_dat_files(dname)

    def refresh_pcr_dat_files(self, dname):
        pcrs = [f for f in os.listdir(dname) if f.lower().endswith('.pcr')]
        dats = [f for f in os.listdir(dname) if f.lower().endswith('.dat')]
        self.pcr_combo.clear()
        self.dat_combo.clear()
        self.pcr_combo.addItems(pcrs)
        self.dat_combo.addItems(dats)
        if pcrs:
            self.pcr_combo.setCurrentIndex(0)
        if dats:
            self.dat_combo.setCurrentIndex(0)

    def select_param(self):
        fname, _ = QFileDialog.getOpenFileName(self, "选择参数库JSON", "", "JSON Files (*.json)")
        if fname:
            self.param_edit.setText(fname)

    def select_step(self):
        fname, _ = QFileDialog.getOpenFileName(self, "选择步骤配置JSON", "", "JSON Files (*.json)")
        if fname:
            self.step_edit.setText(fname)
            # 预加载步骤
            try:
                with open(fname, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.steps = data.get("steps", [])
            except Exception:
                self.steps = []

    def load_last_settings(self):
        cfg = self.config
        if cfg.get("fp2k_path"):
            self.fp2k_edit.setText(cfg["fp2k_path"])
        if cfg.get("refine_dir"):
            self.dir_edit.setText(cfg["refine_dir"])
            self.refresh_pcr_dat_files(cfg["refine_dir"])
        if cfg.get("pcr_file"):
            idx = self.pcr_combo.findText(cfg["pcr_file"])
            if idx >= 0:
                self.pcr_combo.setCurrentIndex(idx)
        if cfg.get("dat_file"):
            idx = self.dat_combo.findText(cfg["dat_file"])
            if idx >= 0:
                self.dat_combo.setCurrentIndex(idx)
        if cfg.get("paramlib_path"):
            self.param_edit.setText(cfg["paramlib_path"])
        if cfg.get("stepcfg_path"):
            self.step_edit.setText(cfg["stepcfg_path"])
        if cfg.get("timeout"):
            self.timeout_spin.setValue(cfg["timeout"])
        if cfg.get("maxfiles"):
            self.maxfile_spin.setValue(cfg["maxfiles"])

    def save_current_settings(self):
        cfg = {
            "fp2k_path": self.fp2k_edit.text(),
            "refine_dir": self.dir_edit.text(),
            "pcr_file": self.pcr_combo.currentText(),
            "dat_file": self.dat_combo.currentText(),
            "paramlib_path": self.param_edit.text(),
            "stepcfg_path": self.step_edit.text(),
            "timeout": self.timeout_spin.value(),
            "maxfiles": self.maxfile_spin.value()
        }
        save_config(cfg)

    def start_refinement(self):
        # 检查参数
        fp2k_path = self.fp2k_edit.text()
        refine_dir = self.dir_edit.text()
        pcr_file = self.pcr_combo.currentText()
        dat_file = self.dat_combo.currentText()
        paramlib_path = self.param_edit.text()
        stepcfg_path = self.step_edit.text()
        timeout = self.timeout_spin.value()
        maxfiles = self.maxfile_spin.value()
        if not (os.path.isfile(fp2k_path) and fp2k_path.lower().endswith("fp2k.exe")):
            QMessageBox.warning(self, "错误", "请正确指定fp2k.exe路径")
            return
        if not (os.path.isdir(refine_dir) and pcr_file and dat_file):
            QMessageBox.warning(self, "错误", "请正确指定精修文件目录和pcr/dat文件")
            return
        if not (os.path.isfile(paramlib_path) and os.path.isfile(stepcfg_path)):
            QMessageBox.warning(self, "错误", "请正确指定参数库和步骤配置文件")
            return
        # 加载步骤
        try:
            with open(stepcfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.steps = data.get("steps", [])
        except Exception:
            QMessageBox.warning(self, "错误", "步骤配置文件格式错误")
            return
        # 保存设置
        self.save_current_settings()
        # 清空日志
        self.log_tabs.log_buffer = {"main": [], "warn": [], "err": [], "chi": []}
        for key in self.log_tabs.log_edits:
            self.log_tabs.log_edits[key].clear()
        self.progress.setValue(0)
        # 配置
        config = {
            "fullprof_path": fp2k_path,
            "pcr_path": os.path.join(refine_dir, pcr_file),
            "data_path": os.path.join(refine_dir, dat_file),
            "paramlib_path": paramlib_path,
            "timeout": timeout,
            "maxfiles": maxfiles
        }
        run_indices = list(range(len(self.steps)))
        self.worker = RefinementWorker(config, self.steps, run_indices)
        self.worker.log_signal.connect(self.log_tabs.append_log)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def pause_refinement(self):
        if self.worker:
            self.worker.pause()

    def resume_refinement(self):
        if self.worker:
            self.worker.resume()

    def stop_refinement(self):
        if self.worker:
            self.worker.stop()

    def export_log(self):
        fname, _ = QFileDialog.getSaveFileName(self, "保存日志", "refine_log.txt", "Text Files (*.txt)")
        if fname:
            self.log_tabs.export_log(fname)
            QMessageBox.information(self, "保存成功", f"日志已保存到：{fname}")

    def export_report(self):
        fname, _ = QFileDialog.getSaveFileName(self, "保存报告", "refine_report.txt", "Text Files (*.txt)")
        if fname:
            with open(fname, "w", encoding="utf-8") as f:
                f.write("FullProf 精修报告\n")
                f.write("="*40 + "\n")
                for k, logs in self.log_tabs.log_buffer.items():
                    f.write(f"==== {k.upper()} ====\n")
                    for line in logs:
                        f.write(line + "\n")
            QMessageBox.information(self, "保存成功", f"报告已保存到：{fname}")

    def on_finished(self, msg):
        self.progress.setValue(100)
        QMessageBox.information(self, "完成", msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = RefinementGUI()
    win.show()
    sys.exit(app.exec_())