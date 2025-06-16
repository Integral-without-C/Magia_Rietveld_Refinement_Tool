"""
Magia_FP_Refinement 项目结构大纲
--------------------------------
本文件以大纲形式梳理了 Magia_FP_Refinement 项目的四个主要 Python 源码文件的类与函数分级结构、主要功能说明，以及关键复杂逻辑的伪代码/流程说明，便于全局理解项目架构和运行逻辑。

包含文件：
1. Magia_PCR_Reader.py      —— 参数库生成与PCR文件解析
2. Magia_FP_Toolbar.py      —— 主界面与功能入口
3. Magia_Step_Genertor.py   —— 步骤生成与管理
4. Magia_FP_Refinement.py   —— 精修主控与自动化流程

--------------------------------
1. Magia_PCR_Reader.py
--------------------------------
【主要功能】  
- 解析 FullProf 的 PCR 文件，自动识别编码、提取参数、生成参数库（JSON），支持 XRD/TOF、手动/多项式背底等多种情况。
- 提供参数库生成的 GUI 界面。

【结构大纲】
- detect_and_convert_to_utf8(filepath, encodings)
    - 自动检测文件编码并转换为 UTF-8，返回内容
- ensure_chi2_line(filepath)
    - 检查并补全 PCR 文件中的 Chi2 行
- get_job_type(filepath)
    - 判断 PCR 文件类型（XRD/TOF）
- parse_poly_bg_params_xrd(lines, param_id)
    - 解析 XRD 多项式背底参数
- parse_manual_bg_params_xrd(lines, param_id)
    - 解析 XRD 手动背底参数
- parse_poly_bg_params_tof(lines, param_id)
    - 解析 TOF 多项式背底参数（预留）
- parse_manual_bg_params_tof(lines, param_id)
    - 解析 TOF 手动背底参数
- parse_xrd_pcr(filepath, atom_names, bg_mode)
    - 解析 XRD 类型 PCR 文件，提取参数
- parse_tof_pcr(filepath, n_bg, atom_names, bg_mode)
    - 解析 TOF 类型 PCR 文件，提取参数
- parse_pcr_auto(filepath, n_bg, atom_names, bg_mode)
    - 自动判断类型并调用对应解析函数

- class ParamLibGUI(QWidget)
    - 参数库生成主界面
    - __init__()                # 初始化界面
    - on_font_size_changed()     # 字体大小调整
    - on_select_pcr()            # 选择 PCR 文件
    - on_recognize()             # 识别并解析参数
    - refresh_tabs()             # 刷新参数展示
    - on_export_json()           # 导出参数库 JSON

- 主程序入口
    - if __name__ == "__main__": 创建 QApplication，显示 ParamLibGUI

【复杂逻辑说明】
- PCR 文件解析流程：
    1. 自动检测编码并转换为 UTF-8
    2. 检查并补全 Chi2 行
    3. 判断类型（XRD/TOF）
    4. 解析仪器参数、背底参数、相参数
    5. 生成参数库数据结构
    6. 导出为 JSON

--------------------------------
2. Magia_FP_Toolbar.py
--------------------------------
【主要功能】  
- 提供主界面，作为参数库生成、步骤生成、精修主控的入口。
- 展示操作说明。

【结构大纲】
- INSTRUCTION_TEXT
    - 操作说明文本

- class InstructionDialog(QDialog)
    - 操作说明弹窗
    - __init__()

- class MainGUI(QWidget)
    - 主界面
    - __init__()             # 初始化主界面
    - open_param_lib()        # 打开参数库生成界面
    - open_step_gen()         # 打开步骤生成界面
    - open_refine()           # 打开精修主控界面
    - show_instruction()      # 显示操作说明

- 主程序入口
    - if __name__ == "__main__": 创建 QApplication，显示 MainGUI

【复杂逻辑说明】
- 主界面按钮点击后分别弹出对应功能窗口，采用多窗口协作。

--------------------------------
3. Magia_Step_Genertor.py
--------------------------------
【主要功能】  
- 加载参数库，生成精修步骤（Step），支持批量操作、步长设置、导入导出等。
- 提供步骤生成与管理的 GUI。

【结构大纲】
- class StepConfigGUI(QWidget)
    - 步骤生成主界面
    - __init__()                         # 初始化界面与数据结构
    - init_ui()                          # 构建界面
    - export_step_table_to_txt()          # 导出步骤表格
    - load_param_json()                   # 加载参数库
    - refresh_inst_bg_checkboxes()        # 刷新仪器/背底参数勾选框
    - refresh_param_tabs()                # 刷新参数分组标签页
    - select_group_checkboxes()           # 全选某组参数
    - reset_group_checkboxes()            # 取消全选某组参数
    - select_phase_group_checkboxes()     # 全选某相某组参数
    - reset_phase_group_checkboxes()      # 取消全选某相某组参数
    - reset_all_params()                  # 重置所有参数
    - get_checked_param_ids()             # 获取所有勾选参数ID
    - add_step()                         # 添加步骤
    - generate_value()                    # 生成参数值
    - on_step_length_changed()            # 步长变更响应
    - batch_apply_step_length()           # 批量应用步长
    - refresh_step_table()                # 刷新步骤表格
    - on_step_checkbox_changed()          # 步骤勾选变更
    - get_selected_step_rows()            # 获取选中步骤
    - batch_delete_steps()                # 批量删除步骤
    - batch_copy_steps()                  # 批量复制步骤
    - on_step_table_cell_changed()        # 步骤表格单元格变更
    - delete_step()                       # 删除单步
    - copy_step()                         # 复制单步
    - get_param_name()                    # 获取参数名
    - import_steps()                      # 导入步骤
    - export_steps()                      # 导出步骤

- 主程序入口
    - if __name__ == "__main__": 创建 QApplication，显示 StepConfigGUI

【复杂逻辑说明】
- 步骤生成流程：
    1. 加载参数库，解析参数分组
    2. 用户勾选参数、设置步长
    3. 添加/批量添加步骤，生成参数变化序列
    4. 支持批量复制、删除、导入导出
    5. 步骤表格实时刷新

--------------------------------
4. Magia_FP_Refinement.py
--------------------------------
【主要功能】  
- 自动调用 FullProf 进行批量精修，支持参数模板替换、日志管理、进度控制、错误检测等。
- 提供精修主控 GUI。

【结构大纲】
- CONFIG_FILE
    - 配置文件名

- read_text_autoenc(filepath, encodings)
    - 自动检测编码读取文本
- read_text_autoenc_content(filepath, encodings)
    - 自动检测编码读取文本内容
- save_config(data)
    - 保存配置
- load_config()
    - 加载配置
- search_fp2k()
    - 自动搜索 fp2k.exe 路径

- class RefinementWorker(QThread)
    - 精修线程，负责自动化精修流程
    - __init__(config, steps, run_indices)
    - run()                          # 主精修流程
    - modify_pcr_template()          # 替换参数生成新 PCR
    - run_fullprof_process()         # 调用 FullProf 进程
    - extract_chi_value()            # 提取 Chi2 值
    - log_error()                    # 记录错误日志
    - pause()/resume()/stop()        # 控制线程暂停/恢复/停止

- class LogTabWidget(QTabWidget)
    - 日志展示与管理
    - __init__()
    - append_log()                   # 添加日志
    - _flush_logs()                  # 刷新日志
    - refresh_tab()                  # 刷新标签页
    - on_search()/on_clear()         # 搜索/清空日志
    - export_log()                   # 导出日志

- class RefinementGUI(QWidget)
    - 精修主控界面
    - __init__()
    - init_ui()                      # 构建界面
    - auto_search_fp2k()             # 自动搜索 fp2k.exe
    - on_fp2k_found()                # 搜索结果处理
    - fp2k_combo_selected()          # 选择 fp2k 路径
    - select_fp2k()/select_dir()     # 手动选择路径
    - refresh_pcr_dat_files()        # 刷新文件列表
    - select_param()/select_step()   # 选择参数/步骤文件
    - load_last_settings()/save_current_settings()
    - start_refinement()/pause_refinement()/resume_refinement()/stop_refinement()
    - export_log()/export_report()
    - on_finished()                  # 精修完成处理

- 主程序入口
    - if __name__ == "__main__": 创建 QApplication，显示 RefinementGUI

【复杂逻辑说明】
- 自动精修主流程（伪代码）：
    1. 读取参数库与步骤文件
    2. 对每一步骤：
        a. 替换 PCR 文件参数，生成新 PCR
        b. 调用 FullProf 进行精修
        c. 解析输出，提取 Chi2、检测错误
        d. 日志记录与进度更新
    3. 支持暂停、恢复、终止
    4. 日志窗口实时刷新，最多保留100行

--------------------------------
【整体运行逻辑】
1. 启动主界面（Magia_FP_Toolbar.py），用户选择功能入口
2. 生成参数库（Magia_PCR_Reader.py），导出 JSON
3. 步骤生成（Magia_Step_Genertor.py），导出步骤 JSON
4. 精修主控（Magia_FP_Refinement.py），加载参数与步骤，自动批量精修
5. 日志、报错、进度等信息实时展示

--------------------------------
【复杂逻辑流程图示例】
（以精修主控自动批量精修为例）

+-------------------+
| 读取参数库与步骤  |
+-------------------+
           |
           v
+-------------------+
|  遍历每个步骤     |
+-------------------+
           |
           v
+-------------------+
| 替换PCR参数生成新PCR|
+-------------------+
           |
           v
+-------------------+
| 调用FullProf精修  |
+-------------------+
           |
           v
+-------------------+
| 解析输出/提取Chi2 |
+-------------------+
           |
           v
+-------------------+
| 日志与进度更新    |
+-------------------+
           |
           v
+-------------------+
| 检查是否暂停/终止 |
+-------------------+
           |
           v
+-------------------+
|   下一步/结束     |
+-------------------+

--------------------------------
【备注】
- 详细代码注释请见各源代码文件。
- 如需进一步了解某一模块的详细流程，可结合注释与本大纲查阅。
"""