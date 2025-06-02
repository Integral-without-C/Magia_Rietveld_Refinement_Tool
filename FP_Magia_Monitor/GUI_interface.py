import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from threading import Thread
from watchdog.observers import Observer
from core_EnhancedHandler import EnhancedHandler
from config_parameters import OPTIMIZED_RULES
import os
import time

class MonitorGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FP_Magia_Monitor_精修监控系统 v1.2")
        self.geometry("850x700")
        self.atom_names = []
        self.current_dir = os.getcwd()
        self.check_interval = 8  # 默认检查间隔
        self._create_widgets()
        self.observer = None
        self.handler = None
        self.monitor_thread = None
        self.running = False

    def _create_widgets(self):
        # 新增时间间隔设置
        config_frame = ttk.LabelFrame(self, text="监控配置")
        config_frame.pack(pady=10, padx=10, fill=tk.X)

        ttk.Label(config_frame, text="抓取间隔(s):").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.interval_entry = ttk.Entry(config_frame, width=10)
        self.interval_entry.insert(0, "（默认8s）")
        self.interval_entry.grid(row=0, column=1, padx=5, sticky=tk.W)
        ttk.Button(config_frame, text="设置间隔", command=self.set_interval).grid(row=0, column=2, padx=5)

        """创建界面组件"""
        # 输入区域
        input_frame = ttk.LabelFrame(self, text="参数设置")
        input_frame.pack(pady=10, padx=10, fill=tk.X)

        # 说明信息框
        self.info_frame = ttk.LabelFrame(self, text="操作说明")
        self.info_text = tk.Text(self.info_frame, wrap=tk.WORD, height=10)
        instructions = """
        使用说明：（上下滚动以完整阅读~~）

        1. 在【监控原子名称】输入框中输入要监控的原子名称（英文逗号分隔）。
        2. 点击【选择目录】按钮指定监控文件夹（默认当前目录）。
        3. 点击【开始监控】启动精修数据抓取。
        4. 执行FullProf精修操作，结果将自动记录。
        5. 点击【停止监控】结束程序，可能有些卡顿，强制结束也行....
        6. 日志文件保存在监控目录下的refinement_log.txt
        
        注意事项：

        - 原始pcr文件中的原子名称必须唯一！！！（例如Cl6i_1,Cl6i_2）。

        - 请确保.sum和.pcr文件同名且同目录（精修进行中不要修改两者的名称就好）。

        - 根据运行Fullprof的实际情况设置抓取时间间隔（5-15s）太短会重复抓取，太长等待时间较久。

        - 监控目录下原有的的refinement_log.txt文件会被覆盖！运行前务必先保存数据！

        - 目前功能只能监控单相TOF文件。
        """
        self.info_text.insert(tk.END, instructions)
        self.info_text.config(state=tk.DISABLED)

        # 原子名称输入
        ttk.Label(input_frame, text="监控原子名称:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.atom_entry = ttk.Entry(input_frame, width=60)
        self.atom_entry.grid(row=0, column=1, padx=5)
        self.atom_entry.insert( 0,"把pcr中原子名称改为唯一值后，在此输入所有原子名称，英文逗号分隔")
        ttk.Button(input_frame, text="确认", command=self.set_atoms).grid(row=0, column=2, padx=5)

        # 目录选择
        ttk.Label(input_frame, text="监控目录:").grid(row=1, column=0, padx=5, sticky=tk.W)
        self.dir_label = ttk.Label(input_frame, text=self.current_dir)
        self.dir_label.grid(row=1, column=1, padx=5, sticky=tk.W)
        ttk.Button(input_frame, text="选择目录", command=self.select_directory).grid(row=1, column=2, padx=5)

        # 状态显示和控制面板
        self.status_frame = ttk.LabelFrame(self, text="监控状态")
        self.status_text = tk.Text(self.status_frame, wrap=tk.WORD, height=10)
        self.scrollbar = ttk.Scrollbar(self.status_frame)
        
        # 控制按钮
        control_frame = ttk.Frame(self)
        self.start_btn = ttk.Button(control_frame, text="开始监控", command=self.start_monitoring)
        self.stop_btn = ttk.Button(control_frame, text="停止监控", command=self.stop_monitoring)

        # 布局
        self.info_frame.pack(pady=10, padx=10, fill=tk.X)
        self.info_text.pack(padx=5, pady=5, fill=tk.BOTH)
        
        self.status_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        control_frame.pack(pady=10)
        self.start_btn.pack(side=tk.LEFT, padx=10)
        self.stop_btn.pack(side=tk.LEFT, padx=10)
        
        # 组件配置
        self.status_text.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.status_text.yview)
        self.stop_btn.config(state=tk.DISABLED)

    def set_interval(self):
        """设置检查时间间隔"""
        try:
            interval = float(self.interval_entry.get())
            if 5 <= interval <= 15:
                self.check_interval = interval
                self.log(f"抓取间隔已设置为：{interval}秒")
            else:
                messagebox.showwarning("警告", "间隔时间需在5-15秒之间！")
        except ValueError:
            messagebox.showwarning("警告", "请输入有效的数字！")
    
    def set_atoms(self):
        """设置监控原子"""
        input_str = self.atom_entry.get().strip()
        if not input_str:
            messagebox.showwarning("警告", "请输入至少一个原子名称！")
            return
        
        self.atom_names = [name.strip() for name in input_str.split(',') if name.strip()]
        self.log(f"已设置监控原子：{', '.join(self.atom_names)}")

    def select_directory(self):
        """选择监控目录"""
        path = filedialog.askdirectory()
        if path:
            self.current_dir = path
            self.dir_label.config(text=path)
            self.log(f"已选择监控目录：{path}")

    def start_monitoring(self):
        """启动监控（修改后）"""
        if not self.atom_names:
            messagebox.showwarning("警告", "请先输入要监控的原子名称！")
            return
        if not os.path.exists(self.current_dir):
            messagebox.showwarning("警告", "请选择有效的监控目录！")
            return

        try:
            output_path = os.path.join(self.current_dir, "refinement_log.txt")
            self.handler = EnhancedHandler(
                output_path=output_path,
                param_rules=OPTIMIZED_RULES,
                atom_names=self.atom_names,
                log_callback=self.log,  # 新增日志回调
                check_interval=self.check_interval
            )
            
            self.observer = Observer()
            self.observer.schedule(self.handler, self.current_dir, recursive=False)
            
            self.monitor_thread = Thread(target=self._start_observer)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
            self.running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.log("监控已启动！")
        except Exception as e:
            self.log(f"启动失败：{str(e)}")
            messagebox.showerror("错误", f"监控启动失败：{str(e)}")

    def _start_observer(self):
        """启动观察者线程"""
        try:
            self.observer.start()
            while self.running:
                time.sleep(1)
        except Exception as e:
            self.log(f"监控异常：{str(e)}")
        finally:
            self.observer.join()

    def stop_monitoring(self):
        """停止监控"""
        if self.observer:
            self.observer.stop()
        self.running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.log("监控已停止")


    def log(self, message):
        """记录日志信息"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
