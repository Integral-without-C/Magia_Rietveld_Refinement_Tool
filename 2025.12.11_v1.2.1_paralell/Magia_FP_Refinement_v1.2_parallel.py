'''
！！！！！！！不要随便修改这个！！！！！！！！
！！！！！！！不要随便修改这个！！！！！！！！
！！！！！！！不要随便修改这个！！！！！！！！
！！！！！！！不要随便修改这个！！！！！！！！
！！！！！！！不要随便修改这个！！！！！！！！

'''
import sys
import os
import re
import json
import threading
import subprocess
import time
from datetime import datetime
from collections import deque
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QComboBox, QTabWidget, QTextEdit, QProgressBar, QMessageBox,
    QSpinBox, QGroupBox, QSplitter, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal,QTimer
from PyQt5.QtGui import QFont, QPalette, QColor
import concurrent.futures
from PyQt5.QtWidgets import QDialog

'''2025.10.30
新增PCR_check调用，自动跳过B值或占位率异常的步骤
注意需要根据不同的需求调用不同的PCR_check文件  

2025.11.01
新增步骤超时自动跳过功能（超过500秒未完成的步骤会被自动跳过）
新增立即跳过当前步骤按钮，允许用户手动跳过当前正在运行的步骤
新增步骤概览标签页，实时显示每个步骤的状态、耗时和原因

2025.11.14
新增批量处理功能，可以批量采用一个pcr对目录下多个dat文件进行精修

2025.12.10
优化了出错的判定逻辑
新增反问错误的判断
检测到[Max] Shift多次升高或多次相等时自动跳过当前步骤
新增阻塞检测功能，超过60秒未检测到新的[Max] Shift时自动跳过当前步骤
新增批量精修时为dat文件生成精修步骤概览报告AAA_step_overview.txt，包括精修耗时
！！！可以并行精修了！！！建议不超过3个线程，否则可能会因为磁盘IO过高导致阻塞，已优化效率

#######并行精修经过测试，无法较稳定运行，但保留此功能，建议使用单线程模式进行精修########

'''


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

# def search_fp2k():
#     # 常见路径
#     candidates = []
#     for root in [r"C:\FullProf_Suite"]:
#         for dirpath, dirnames, filenames in os.walk(root):
#             for fname in filenames:
#                 if fname.lower() == "fp2k.exe":
#                     candidates.append(os.path.join(dirpath, fname))
#             if len(candidates) > 10:
#                 return candidates
#     # C盘全盘搜索（慢）
#     for dirpath, dirnames, filenames in os.walk("C:\\"):
#         for fname in filenames:
#             if fname.lower() == "fp2k.exe":
#                 candidates.append(os.path.join(dirpath, fname))
#         if len(candidates) > 10:
#             break
#     return candidates

class RefinementWorker(QThread):
    log_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str)
    step_overview_signal = pyqtSignal(list)  # 新增：步骤概览信号

    def __init__(self, config, steps, run_indices):
        super().__init__()
        self.config = config
        self.steps = steps
        self.run_indices = run_indices
        self._pause = False
        self._stop = False
        self._skip = False
        self._current_process = None
        self._overview_list = []  # 新增：步骤状态列表
        self._current_step_start = None
        self.pcrcheck_path = self.config.get("pcrcheck_path")  # 新增：保存PCRcheck路径

    def run(self):
        TEMP_DIR = self.config['temp_dir']  # 修改为使用传入的temp_dir
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
        self._overview_list = []
        for idx, step_idx in enumerate(self.run_indices):
            step = self.steps[step_idx]
            active_param_ids = [ap['id'] for ap in step.get('active_params', [])]
            param_names = []
            for pid in active_param_ids:
                param_names.append(param_lib.get(pid, {}).get('name', str(pid)))
            overview_entry = {
                "index": idx + 1,
                "name": step['name'],
                "params": param_names,  # 新增参数名
                "status": "等待",
                "duration": 0,
                "reason": ""
            }
            self._overview_list.append(overview_entry)
        self.step_overview_signal.emit(self._overview_list)
        for idx, step_idx in enumerate(self.run_indices):
            if self._stop:
                self.log_signal.emit("main", f"[主日志] 已终止于步骤 {step_idx+1}")
                break
            while self._pause:
                time.sleep(0.2)
            step = self.steps[step_idx]
            self._current_step_start = time.time()
            self._overview_list[idx]["status"] = "运行中"
            self._overview_list[idx]["duration"] = 0
            self._overview_list[idx]["reason"] = ""
            self.step_overview_signal.emit(self._overview_list)

            # 新增：实时刷新耗时线程
            running = True
            def update_duration_and_timeout():
                while running and self._overview_list[idx]["status"] == "运行中":
                    now = time.time()
                    self._overview_list[idx]["duration"] = int(now - self._current_step_start)
                    # 步骤超时自动跳过
                    if self._overview_list[idx]["duration"] > 10000 and not self._skip:
                        self._skip = True
                        self._overview_list[idx]["status"] = "跳过"
                        self._overview_list[idx]["reason"] = "精修超时"
                        self.step_overview_signal.emit(self._overview_list)
                        self.log_signal.emit("warn", f"⏩ 步骤 {step['name']} 超时自动跳过（>10000s）")
                        break
                    self.step_overview_signal.emit(self._overview_list)
                    time.sleep(1)
            t = threading.Thread(target=update_duration_and_timeout, daemon=True)
            t.start()

            # 检查是否需要跳过
            if self._skip:
                self.log_signal.emit("warn", f"⏩ 用户操作：立即跳过步骤: {step['name']}")
                self.log_error(ERROR_LOG_PATH, step['name'], "用户主动跳过")
                self._skip = False
                self._overview_list[idx]["status"] = "跳过"
                self._overview_list[idx]["duration"] = int(time.time() - self._current_step_start)
                self._overview_list[idx]["reason"] = "用户主动跳过"
                self.step_overview_signal.emit(self._overview_list)
                continue
            try:
                step_number = idx + 1
                safe_step_name = re.sub(r'[^a-zA-Z0-9_]', '_', step['name'])
                base_name = f"step_{step_number:03d}_{safe_step_name}"
                template_path = current_template  # <--- 这里是上一步的pcr
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
                # current_template = new_pcr_path  # <-- 移除这行，后面根据结果再更新
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
                # 计时开始
                step_start = time.time()
                success, error_info = self.run_fullprof_process(
                    fullprof_path=self.config['fullprof_path'],
                    pcr_path=new_pcr_path,
                    timeout=self.config.get('timeout', 3600),
                    show_window=False,
                    temp_dir=TEMP_DIR
                )
                # 检查是否被跳过
                if self._skip:
                    self.log_signal.emit("warn", f"⏩ 用户操作：立即跳过步骤: {step['name']}")
                    self.log_error(ERROR_LOG_PATH, step['name'], "用户主动跳过")
                    self._skip = False
                    self._overview_list[idx]["status"] = "跳过"
                    self._overview_list[idx]["duration"] = int(time.time() - step_start)
                    self._overview_list[idx]["reason"] = "用户主动跳过"
                    self.step_overview_signal.emit(self._overview_list)
                    continue
                if success:
                    check_result = self.check_pcr_values(new_pcr_path)
                    if check_result is not None:
                        self._overview_list[idx]["status"] = "失败"
                        self._overview_list[idx]["duration"] = int(time.time() - step_start)
                        self._overview_list[idx]["reason"] = f"OCC/B值异常: {check_result}"
                        self.step_overview_signal.emit(self._overview_list)
                        continue
                    else:
                        self._overview_list[idx]["status"] = "成功"
                        self._overview_list[idx]["duration"] = int(time.time() - step_start)
                        self._overview_list[idx]["reason"] = "精修成功"
                        self.step_overview_signal.emit(self._overview_list)
                        current_template = new_pcr_path
                else:
                    self._overview_list[idx]["status"] = "失败"
                    self._overview_list[idx]["duration"] = int(time.time() - step_start)
                    self._overview_list[idx]["reason"] = error_info
                    self.step_overview_signal.emit(self._overview_list)
                    continue
                chi = self.extract_chi_value(new_pcr_path)
                if chi is not None:
                    self.log_signal.emit("chi", f"Step {step['name']} Chi²: {chi:.2f}")
                else:
                    self.log_signal.emit("warn", f"⚠️ 未检测到Chi²值")
                self.progress_signal.emit(int((idx+1)/total*100))
            except Exception as e:
                error_info = f"非预期错误: {str(e)}"
                self._overview_list[idx]["status"] = "失败"
                self._overview_list[idx]["duration"] = int(time.time() - self._current_step_start)
                self._overview_list[idx]["reason"] = error_info
                self.step_overview_signal.emit(self._overview_list)
                continue
        self.progress_signal.emit(100)
        self.finished_signal.emit("精修已完成！报告已生成。")

    def check_pcr_values(self, pcr_path):
        # 如果未导入PCRcheck，直接返回None（即不做限制）
        if not self.pcrcheck_path:
            return None
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("PCR_check_gui_export", self.pcrcheck_path)
            pcrcheck = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(pcrcheck)
            errs = pcrcheck.check_pcr_limits(pcr_path)
            if errs:
                return "\n".join(errs)
            return None
        except Exception as e:
            return f"PCR_check运行失败: {e}"
        
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
                    process = subprocess.Popen(
                        [fullprof_path, os.path.basename(pcr_path)],
                        cwd=os.path.dirname(pcr_path),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        startupinfo=startupinfo,
                        creationflags=creationflags,
                        bufsize=1
                    )
                    self._current_process = process  # 保存当前进程
                except Exception as e:
                    self.log_signal.emit("err", f"FullProf启动失败: {e}")
                    self._current_process = None
                    return False, f"FullProf启动失败: {e}"
                error_flag = False
                error_message = ""
                # 收敛检测和阻塞检测
                last_abs_shift = None
                not_decrease_count = 0  # abs_shift大于上一轮的计数
                equal_count = 0         # abs_shift等于上一轮的计数
                MAX_NOT_DECREASE = 50  # 未降低次数阈值
                MAX_EQUAL = 30          # 相等次数阈值
                BLOCK_TIMEOUT = 60      # 阻塞超时时间（秒）
                last_shift_time = None
                
                with process.stdout as pipe:
                    for line in iter(pipe.readline, ''):
                        log_file.write(line)
                        self.log_signal.emit("main", line.rstrip())
                        buffer.append(line.strip())
                        # 检查是否被跳过
                        if self._skip:
                            process.kill()
                            self._current_process = None
                            return False, "用户主动跳过"
                        # 检测 [Max] Shift 收敛和阻塞
                        shift_match = re.search(
                            r'Conv\. not yet reached\s*->\s*\[Max\] Shift.*?=\s*([-\d.]+)\s*abs>', line)
                        now_time = time.time()
                        if shift_match:
                            try:
                                shift_val = float(shift_match.group(1))
                                abs_shift = abs(shift_val)
                                # 阻塞检测
                                if last_shift_time is not None and now_time - last_shift_time > BLOCK_TIMEOUT:
                                    process.kill()
                                    self._current_process = None
                                    self.log_signal.emit("err", "当前步骤精修阻塞！请查看log文件")
                                    return False, "当前步骤精修阻塞！超过60s未检测到新的[Max] Shift！"
                                last_shift_time = now_time
                                # 收敛检测
                                if last_abs_shift is not None:
                                    if abs_shift > last_abs_shift:
                                        not_decrease_count += 1
                                        equal_count = 0  # 只要出现大于就清零相等计数
                                    elif abs_shift == last_abs_shift:
                                        equal_count += 1
                                    else:
                                        # not_decrease_count = 0  # 可选：目前降低时不重置递减计数
                                        equal_count = 0  # 降低时重置相等计数
                                last_abs_shift = abs_shift
                                # 达到阈值则判定未收敛
                                if not_decrease_count >= MAX_NOT_DECREASE or equal_count >= MAX_EQUAL:
                                    process.kill()
                                    self._current_process = None
                                    self.log_signal.emit("err", "当前步骤不收敛，[Max] Shift多次未降低或多次相等，自动跳过")
                                    return False, "当前步骤不收敛，[Max] Shift多次未降低或多次相等"
                            except Exception:
                                pass
                        else:
                            # 如果已检测到过shift行，且距离上次超过BLOCK_TIMEOUT，则判定阻塞
                            if last_shift_time is not None and now_time - last_shift_time > BLOCK_TIMEOUT:
                                process.kill()
                                self._current_process = None
                                self.log_signal.emit("err", "当前步骤精修阻塞！请查看log文件")
                                return False, "当前步骤精修阻塞！未检测到新的[Max] Shift，请查看log文件"
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
                        elif "have you really reflections?" in line:
                            error_flag = True
                            error_message = "出现反问错误，没有反射峰！"
                        elif "NO REFLECTIONS FOUND" in line:
                            error_flag = True
                            error_message = "NO REFLECTIONS FOUND -> Check your INS parameter for input data and/or ZERO point"
                        if error_flag:
                            process.kill()
                            self._current_process = None
                            break
                try:
                    exit_code = process.wait(timeout=timeout)
                except Exception:
                    process.kill()
                    self._current_process = None
                    return False, "进程超时"
                self._current_process = None
                return exit_code == 0 and not error_flag, error_message if error_flag else "正常完成"
        except Exception as e:
            self._current_process = None
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

    def skip_current_step(self):
        self._skip = True
        # 如果有正在运行的FullProf进程，立即kill
        if self._current_process is not None:
            try:
                self._current_process.kill()
            except Exception:
                pass

class LogTabWidget(QTabWidget):
    MAX_DISPLAY_LINES = 100
    def __init__(self):
        super().__init__()
        self.log_edits = {
            "main": QTextEdit(),
            "warn": QTextEdit(),
            "err": QTextEdit(),
            "chi": QTextEdit(),
            "overview": QTextEdit()  # 新增：步骤概览
        }
        for key, edit in self.log_edits.items():
            edit.setReadOnly(True)
            self.addTab(edit, {"main":"主日志","warn":"警告","err":"错误","chi":"Chi²变化","overview":"步骤概览"}[key])
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
        self._timer.start(1000)  # 每1000ms刷新一次 ,防止卡死
        self.overview_data = []  # 新增：保存步骤概览数据
        self._overview_timer = QTimer(self)
        self._overview_timer.timeout.connect(self._refresh_overview)
        self._overview_timer.start(1000)  # 每秒刷新一次

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

        # 只显示最新 MAX_DISPLAY_LINES 行
        lines = self.log_buffer[log_type][-self.MAX_DISPLAY_LINES:]

        # 如果有搜索关键字，则过滤
        if keyword:
            lines = [line for line in lines if keyword in line]

        # 清空一次（比 setPlainText 高效得多）
        edit.clear()

        # 使用 append 逐行写入（不会强制 QTextEdit 重绘整个缓冲）
        for line in lines:
            edit.append(line)

        # 滚动到末尾
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

    def set_overview(self, overview_list):
        self.overview_data = overview_list
        self._refresh_overview()

    def _refresh_overview(self):
        lines = []
        for entry in self.overview_data:
            status = entry["status"]
            if status not in ("运行中", "成功", "失败", "跳过"):
                continue  # 只显示正在运行和已完成的步骤
            name = entry["name"]
            params = entry.get("params", [])
            param_str = ", ".join(params) if params else ""
            duration = entry["duration"]
            reason = entry.get("reason", "")
            line = f"步骤 {entry['index']}: {name}"
            if param_str:
                line += f" | 参数: {param_str}"
            line += f" | 状态: {status} | 耗时: {duration}s"
            if status == "失败" or status == "跳过":
                line += f" | 原因: {reason}"
            elif status == "成功":
                line += " | 精修成功"
            lines.append(line)
        # 保持当前滚动位置，不自动下拉
        edit = self.log_edits["overview"]
        scroll_pos = edit.verticalScrollBar().value()
        edit.setPlainText('\n'.join(lines))
        edit.verticalScrollBar().setValue(scroll_pos)
# ...existing code...

class RefinementGUI(QWidget):
    # fp2k_found = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        # ...existing code...
        self.batch_btn = QPushButton("批量精修")  # 新增批量精修按钮
        # ...existing code...
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.batch_btn)  # 添加到按钮区
        # ...existing code...
        self.batch_btn.clicked.connect(self.batch_refinement)  # 绑定事件        
        self.setWindowTitle("Magia_FP_Refinement_v1.2")
        self.setMinimumSize(1100, 700)
        self.resize(1200, 800)
        self.config = load_config()
        self.worker = None
        self.steps = []
        self.param_lib = []
        self.init_ui()
        self.load_last_settings()
        # self.fp2k_search_thread = None
        # self.fp2k_candidates = []
        # self.fp2k_found.connect(self.on_fp2k_found)
        # self.auto_search_fp2k()
        self.pcrcheck_path = None  # 新增：PCRcheck文件路径
        self._batch_dat_start_time = None  # 记录当前dat开始时间
        
    def skip_current_step(self):
        if self.worker:
            self.worker.skip_current_step()

        # ...existing code...
    def batch_refinement(self):
        fp2k_path = self.fp2k_edit.text()
        refine_dir = self.dir_edit.text()
        pcr_file = self.pcr_combo.currentText()
        paramlib_path = self.param_edit.text()
        stepcfg_path = self.step_edit.text()
        timeout = self.timeout_spin.value()
        maxfiles = self.maxfile_spin.value()
        if not (os.path.isfile(fp2k_path) and fp2k_path.lower().endswith("fp2k.exe")):
            QMessageBox.warning(self, "错误", "请正确指定fp2k.exe路径")
            return
        if not (os.path.isdir(refine_dir) and pcr_file):
            QMessageBox.warning(self, "错误", "请正确指定精修文件目录和pcr文件")
            return
        if not (os.path.isfile(paramlib_path) and os.path.isfile(stepcfg_path)):
            QMessageBox.warning(self, "错误", "请正确指定参数库和步骤配置文件")
            return
        try:
            with open(stepcfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.steps = data.get("steps", [])
        except Exception:
            QMessageBox.warning(self, "错误", "步骤配置文件格式错误")
            return
        self.save_current_settings()
        # 清空主日志显示
        self.log_tabs.log_buffer = {"main": [], "warn": [], "err": [], "chi": []}
        for key in self.log_tabs.log_edits:
            self.log_tabs.log_edits[key].clear()
        self.progress.setValue(0)

        dat_files = [f for f in os.listdir(refine_dir) if f.lower().endswith('.dat')]
        if not dat_files:
            QMessageBox.warning(self, "错误", "当前目录下没有dat文件")
            return

        # 批量队列与执行器
        from collections import deque
        self._batch_queue = deque(dat_files)
        self._batch_refine_dir = refine_dir
        self._batch_total = len(dat_files)
        self._batch_completed = 0
        max_parallel = max(1, int(self.max_parallel_spin.value()))
        self._batch_executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel)

        # 启动最多 max_parallel 个任务
        for _ in range(min(max_parallel, len(self._batch_queue))):
            self._start_next_task()

        QMessageBox.information(self, "批量启动", f"已启动批量精修：总 {self._batch_total} 个 dat，最多并行 {max_parallel} 个。")
# ...existing code...
# ...existing code...
    def _start_next_task(self):
        # 从队列取下一个 dat 并提交执行，且只为正在并行执行的任务弹出窗口
        if not hasattr(self, "_batch_queue") or not self._batch_queue:
            return
        dat_file = self._batch_queue.popleft()
        subdir = os.path.join(self._batch_refine_dir, os.path.splitext(dat_file)[0])
        os.makedirs(subdir, exist_ok=True)
        config = {
            "pcrcheck_path": self.pcrcheck_path,
            "fullprof_path": self.fp2k_edit.text(),
            "pcr_path": os.path.join(self._batch_refine_dir, self.pcr_combo.currentText()),
            "data_path": os.path.join(self._batch_refine_dir, dat_file),
            "paramlib_path": self.param_edit.text(),
            "timeout": self.timeout_spin.value(),
            "maxfiles": self.maxfile_spin.value(),
            "temp_dir": subdir
        }
        run_indices = list(range(len(self.steps)))
        win = RealtimeRefineWindow(dat_file)
        worker = RefinementWorker(config, self.steps, run_indices)

        # 绑定信号到子窗口
        worker.log_signal.connect(win.log_tabs.append_log)
        worker.progress_signal.connect(win.progress.setValue)
        worker.step_overview_signal.connect(win.log_tabs.set_overview)

        # 允许窗口按钮控制 worker
        win.bind_worker_control(worker)
        win._confirm_on_close = True
        win.show()

        future = self._batch_executor.submit(worker.run)
        start_time = time.time()
        if not hasattr(self, "_batch_active"):
            self._batch_active = {}
        self._batch_active[future] = (worker, win, subdir, start_time)

        def _on_future_done(fut):
            QTimer.singleShot(0, lambda: self._on_task_done(fut))
        future.add_done_callback(_on_future_done)

    def _on_task_done(self, future):
        info = self._batch_active.pop(future, None)
        if info is None:
            return
        worker, win, subdir, start_time = info
        # 写入 AAA_step_overview.txt
        try:
            overview_lines = []
            for entry in getattr(win.log_tabs, "overview_data", []):
                status = entry.get("status", "")
                if status not in ("运行中", "成功", "失败", "跳过"):
                    continue
                name = entry.get("name", "")
                params = entry.get("params", []) or []
                param_str = ", ".join(params) if params else ""
                duration = entry.get("duration", 0)
                reason = entry.get("reason", "")
                line = f"步骤 {entry.get('index')}: {name}"
                if param_str:
                    line += f" | 参数: {param_str}"
                line += f" | 状态: {status} | 耗时: {duration}s"
                if status in ("失败", "跳过"):
                    line += f" | 原因: {reason}"
                elif status == "成功":
                    line += " | 精修成功"
                overview_lines.append(line)
            elapsed = time.time() - start_time if start_time else None
            if elapsed is not None:
                overview_lines.append(f"本dat文件总耗时: {elapsed:.1f} 秒")
            else:
                overview_lines.append("本dat文件总耗时: 未知")
            os.makedirs(subdir, exist_ok=True)
            with open(os.path.join(subdir, "AAA_step_overview.txt"), "w", encoding="utf-8") as f:
                for line in overview_lines:
                    f.write(line + "\n")
        except Exception:
            pass

        # 自动关闭子窗口（不弹确认）
        try:
            win._confirm_on_close = False
            win.close()
        except Exception:
            pass

        # 启动下一个待处理任务
        self._batch_completed = getattr(self, "_batch_completed", 0) + 1
        if self._batch_queue:
            self._start_next_task()
        else:
            if not getattr(self, "_batch_active", {}):
                QMessageBox.information(self, "批量完成", "所有dat文件批量精修已完成！")
# ...existing code...


    # 修改 _batch_run_next_dat 方法
    def _batch_run_next_dat(self):
        if self._batch_idx >= self._batch_total:
            QMessageBox.information(self, "批量完成", "所有dat文件批量精修已完成！")
            return
        dat_file = self._batch_dat_files[self._batch_idx]
        subdir = os.path.join(self._batch_refine_dir, os.path.splitext(dat_file)[0])
        os.makedirs(subdir, exist_ok=True)
        config = {
            "pcrcheck_path": self._batch_pcrcheck_path,
            "fullprof_path": self._batch_fp2k_path,
            "pcr_path": os.path.join(self._batch_refine_dir, self._batch_pcr_file),
            "data_path": os.path.join(self._batch_refine_dir, dat_file),
            "paramlib_path": self._batch_paramlib_path,
            "timeout": self._batch_timeout,
            "maxfiles": self._batch_maxfiles,
            "temp_dir": subdir
        }
        run_indices = list(range(len(self._batch_steps)))
        self.worker = RefinementWorker(config, self._batch_steps, run_indices)
        self.worker.log_signal.connect(self.log_tabs.append_log)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.finished_signal.connect(self._batch_on_finished)
        self.worker.step_overview_signal.connect(self.log_tabs.set_overview)
        self.log_tabs.append_log("main", f"\n开始精修 {dat_file} ({self._batch_idx+1}/{self._batch_total})")
        self._batch_dat_start_time = time.time()  # 记录开始时间
        self.worker.start()
        self._start_next_task()
    
    def _batch_on_finished(self, msg):
        # 记录结束时间
        dat_file = self._batch_dat_files[self._batch_idx]
        subdir = os.path.join(self._batch_refine_dir, os.path.splitext(dat_file)[0])
        elapsed = time.time() - self._batch_dat_start_time if self._batch_dat_start_time else None
    
        # 获取步骤预览内容
        overview_lines = []
        for entry in self.log_tabs.overview_data:
            status = entry["status"]
            if status not in ("运行中", "成功", "失败", "跳过"):
                continue
            name = entry["name"]
            params = entry.get("params", [])
            param_str = ", ".join(params) if params else ""
            duration = entry["duration"]
            reason = entry.get("reason", "")
            line = f"步骤 {entry['index']}: {name}"
            if param_str:
                line += f" | 参数: {param_str}"
            line += f" | 状态: {status} | 耗时: {duration}s"
            if status == "失败" or status == "跳过":
                line += f" | 原因: {reason}"
            elif status == "成功":
                line += " | 精修成功"
            overview_lines.append(line)
        if elapsed is not None:
            overview_lines.append(f"本dat文件总耗时: {elapsed:.1f} 秒")
        else:
            overview_lines.append("本dat文件总耗时: 未知")
        # 写入文件
        try:
            with open(os.path.join(subdir, "AAA_step_overview.txt"), "w", encoding="utf-8") as f:
                for line in overview_lines:
                    f.write(line + "\n")
        except Exception as e:
            self.log_tabs.append_log("err", f"无法写入AAA_step_overview.txt: {e}")
    
        self._batch_idx += 1
        self._batch_run_next_dat()
        pass

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # 文件选择区
        btn_layout = QHBoxLayout()
        file_group = QGroupBox("文件与目录设置")
        file_layout = QVBoxLayout()
        # 在文件选择区添加“导入PCRcheck”按钮
        self.pcrcheck_edit = QLineEdit()
        self.pcrcheck_edit.setReadOnly(True)
        self.pcrcheck_btn = QPushButton("导入PCRcheck")
        self.pcrcheck_btn.clicked.connect(self.select_pcrcheck)
        # 添加到file_layout
        pcrcheck_layout = QHBoxLayout()
        pcrcheck_layout.addWidget(QLabel("PCRcheck文件："))
        pcrcheck_layout.addWidget(self.pcrcheck_edit, 2)
        pcrcheck_layout.addWidget(self.pcrcheck_btn)
        file_layout.addLayout(pcrcheck_layout)

        # fp2k
        fp2k_layout = QHBoxLayout()
        self.fp2k_edit = QLineEdit()
        self.fp2k_edit.setReadOnly(True)
        self.fp2k_btn = QPushButton("手动指定fp2k.exe")
        self.fp2k_btn.clicked.connect(self.select_fp2k)
        # self.fp2k_combo = QComboBox()
        # self.fp2k_combo.setVisible(False)
        # self.fp2k_combo.currentIndexChanged.connect(self.fp2k_combo_selected)
        fp2k_layout.addWidget(QLabel("FullProf执行文件(fp2k.exe)："))
        fp2k_layout.addWidget(self.fp2k_edit, 2)
        fp2k_layout.addWidget(self.fp2k_btn)
        # fp2k_layout.addWidget(self.fp2k_combo)
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
        self.timeout_spin.setRange(100, 99999999)
        self.timeout_spin.setValue(360000)
        self.maxfile_spin = QSpinBox()
        self.maxfile_spin.setRange(100, 99999999)
        self.maxfile_spin.setValue(999000)
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
        self.skip_btn = QPushButton("立即跳过当前步骤")  # 新增按钮
        self.batch_btn = QPushButton("批量精修")  # 新增批量精修按钮
        self.export_log_btn = QPushButton("导出日志")
        self.export_report_btn = QPushButton("导出报告")
        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.resume_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.skip_btn)  # 添加到布局
        btn_layout.addWidget(self.batch_btn)  # 添加到布局
        btn_layout.addWidget(self.export_log_btn)
        btn_layout.addWidget(self.export_report_btn)
        main_layout.addLayout(btn_layout)
        # 事件绑定
        self.run_btn.clicked.connect(self.start_refinement)
        self.batch_btn.clicked.connect(self.batch_refinement)
        self.pause_btn.clicked.connect(self.pause_refinement)
        self.resume_btn.clicked.connect(self.resume_refinement)
        self.stop_btn.clicked.connect(self.stop_refinement)
        self.skip_btn.clicked.connect(self.skip_current_step)  # 新增绑定
        self.export_log_btn.clicked.connect(self.export_log)
        self.export_report_btn.clicked.connect(self.export_report)
        # 在参数设置区添加最大并行精修数设置
        self.max_parallel_spin = QSpinBox()
        self.max_parallel_spin.setRange(1, 32)
        self.max_parallel_spin.setValue(5)
        paramset_layout.addWidget(QLabel("最大并行精修数："))
        paramset_layout.addWidget(self.max_parallel_spin)
        # ...existing code...

    def select_pcrcheck(self):
        fname, _ = QFileDialog.getOpenFileName(self, "选择PCR_check_gui_export.py", "", "Python Files (*.py)")
        if fname:
            self.pcrcheck_edit.setText(fname)
            self.pcrcheck_path = fname

    # def auto_search_fp2k(self):
    #     self.fp2k_edit.setText("正在自动搜索fp2k.exe，请稍候...")
    #     def search():
    #         candidates = search_fp2k()
    #         self.fp2k_found.emit(candidates)  # 用信号通知主线程
    #     t = threading.Thread(target=search, daemon=True)
    #     t.start()

    def closeEvent(self, event):
        # # 判断精修是否正在进行
        # if self.worker and self.worker.isRunning():
        #     reply = QMessageBox.question(
        #         self,
        #         "确认关闭",
        #         "精修正在进行中，确认关闭？",
        #         QMessageBox.Yes | QMessageBox.No,
        #         QMessageBox.No
        #     )
        #     if reply == QMessageBox.Yes:
        #         self.worker.stop()
        #         event.accept()
        #     else:
        #         event.ignore()
        # else:
        #     event.accept()
        # 无论是否正在精修，关闭时都弹出确认，防止误操作关闭程序
        reply = QMessageBox.question(
            self,
            "确认关闭",
            "精修可能在进行中，确认关闭？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # 如果有正在运行的 worker/批量执行器，尝试优雅停止
            try:
                if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
                    self.worker.stop()
            except Exception:
                pass
            try:
                if hasattr(self, '_batch_executor') and self._batch_executor:
                    # 不等待正在进行的任务完成，尝试立即关闭线程池
                    self._batch_executor.shutdown(wait=False)
            except Exception:
                pass
            event.accept()
        else:
            event.ignore()        

    # def on_fp2k_found(self, candidates):
    #     self.fp2k_candidates = candidates
    #     if candidates:
    #         self.fp2k_combo.clear()
    #         self.fp2k_combo.addItems(candidates)
    #         self.fp2k_combo.setVisible(True)
    #         self.fp2k_edit.setText(candidates[0])
    #         self.fp2k_combo.setCurrentIndex(0)
    #     else:
    #         self.fp2k_edit.setText("")
    #         self.fp2k_combo.setVisible(False)

    # def fp2k_combo_selected(self, idx):
    #     if 0 <= idx < len(self.fp2k_candidates):
    #         self.fp2k_edit.setText(self.fp2k_candidates[idx])

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
            "pcrcheck_path": self.pcrcheck_path,
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
        self.worker.step_overview_signal.connect(self.log_tabs.set_overview)  # 新增：绑定步骤概览
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

from PyQt5.QtWidgets import QDialog

class RealtimeRefineWindow(QDialog):
    def __init__(self, dat_file):
        super().__init__()
        self.setWindowTitle(f"{dat_file} 精修实时窗口")
        self.resize(800, 600)
        layout = QVBoxLayout(self)
        self.log_tabs = LogTabWidget()
        layout.addWidget(self.log_tabs)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        # 按钮区：暂停 / 继续 / 立即跳过当前步骤
        btn_layout = QHBoxLayout()
        self.pause_btn = QPushButton("暂停")
        self.resume_btn = QPushButton("继续")
        self.skip_btn = QPushButton("立即跳过当前步骤")
        btn_layout.addWidget(self.pause_btn)
        btn_layout.addWidget(self.resume_btn)
        btn_layout.addWidget(self.skip_btn)
        layout.addLayout(btn_layout)

        # 状态
        self._worker = None
        self._confirm_on_close = True

    def bind_worker_control(self, worker):
        """将窗口按钮绑定到对应 worker（由主 GUI 调用）"""
        self._worker = worker
        try:
            self.pause_btn.clicked.disconnect()
        except Exception:
            pass
        try:
            self.resume_btn.clicked.disconnect()
        except Exception:
            pass
        try:
            self.skip_btn.clicked.disconnect()
        except Exception:
            pass
        self.pause_btn.clicked.connect(lambda: self._worker.pause() if self._worker else None)
        self.resume_btn.clicked.connect(lambda: self._worker.resume() if self._worker else None)
        self.skip_btn.clicked.connect(lambda: self._worker.skip_current_step() if self._worker else None)

    def closeEvent(self, event):
        # 自动关闭（由批量管理触发）时不弹窗
        if not getattr(self, "_confirm_on_close", True):
            event.accept()
            return
        reply = QMessageBox.question(
            self,
            "确认关闭",
            "精修可能在进行中，确认关闭此窗口？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                if hasattr(self, "_worker") and self._worker:
                    self._worker.stop()
            except Exception:
                pass
            event.accept()
        else:
            event.ignore()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("微软雅黑"))
    win = RefinementGUI()
    win.show()
    sys.exit(app.exec_())