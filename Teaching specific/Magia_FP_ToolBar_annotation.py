import sys  # 导入sys模块，用于系统相关操作
import os  # 导入os模块，用于文件路径操作
from PyQt5.QtWidgets import (  # 导入PyQt5相关控件
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog, QTextEdit, QScrollArea, QFrame
)
from PyQt5.QtGui import QPixmap, QFont  # 导入QPixmap用于图片显示，QFont用于字体设置
from PyQt5.QtCore import Qt  # 导入Qt常量
from Magia_FP_Refinement import RefinementGUI  # 导入精修主控界面
from Magia_PCR_Reader import ParamLibGUI  # 导入参数库生成界面
from Magia_Step_Genertor import StepConfigGUI  # 导入步骤生成界面

INSTRUCTION_TEXT = """
========Magia_FP_Toolbar_v1.0 使用说明===========

1.请先使用Fullprof_suite制作正确的pcr。

2.保证pcr位于全英文路径下，且pcr中的各项路径（dat路径、仪器路径）不含中文字符。

3.确保pcr中各个原子的名称不重名。（例如，有多个Cl6i时，需重名为Cl6i_1,Cl6i_2等）

4.如需采用该程序精修择优与不对称型参数，请先手动修改pcr中相关代码（AsyLim，Pr1 Pr2 Pr3等）。

5.先使用参数库生成，生成参数库文件（.JSON），然后使用步骤生成，生成步骤文件（.JSON），最后使用精修主控进行精修。

6.精修主控会自动搜索fp2k.exe文件，若未找到则需要手动指定。


===========参数库生成===============

可自动读取XRD与TOF，自动识别手动插入背底数目，自动识别编码格式并自动转换为UTF-8编码，自动检测是否存在“! Current global Chi2 (Bragg contrib.) = ”，不存在则自动生成。可更改字体大小。

###无法读取各向异性B值###


========步骤生成============

友好的GUI界面，允许用户批量设置步长，以及手动修改value值，允许Step步骤批量选中，进行复制与删除操作，允许外部导入参数库，具有一键全选/一键取消功能。

###新步骤仅能添加在末尾，不能在中间加入新的步骤，且不同Step之间无法互换位置###


==========精修主控============

自动搜索fp2k.exe执行文件，且允许用户手动指定。自动识别精修目录下.pcr与.dat文件（多个文件则需要手动滚轮选择）。主日志界面每100ms刷新，且仅保留最新100行数据，以提升性能。可暂停，但需等待当前Step结束后生效。自动检测精修中各类报错以及未收敛现象，记录并输出。


===================================

!!!注意：该程序完全免费，仅供学习交流使用，禁止用于任何商业用途!!!

若有任何问题或建议，请联系开发者。

Yujun Wan, PKUSZ Xiao Lab. 邮箱：wan_yujun@stu.pku.edu.cn

如果觉得好用，请给个Star支持一下哦！ https://github.com/Integral-without-C/Magia_Fullprof_Tool.git
"""

class InstructionDialog(QDialog):  # 操作说明弹窗类
    def __init__(self, parent=None):
        super().__init__(parent)  # 调用父类构造
        self.setWindowTitle("操作说明")  # 设置窗口标题
        self.resize(2000, 900)  # 设置窗口大小
        layout = QVBoxLayout(self)  # 主垂直布局
        text_edit = QTextEdit()  # 文本编辑器控件
        text_edit.setReadOnly(True)  # 只读
        text_edit.setPlainText(INSTRUCTION_TEXT)  # 设置说明文本
        text_edit.setFont(QFont("Consolas", 11))  # 设置字体
        layout.addWidget(text_edit)  # 添加到布局

class MainGUI(QWidget):  # 主界面类
    def __init__(self):
        super().__init__()  # 调用父类构造
        self.setWindowTitle("Magia_FP_Toolbar_v1.0")  # 设置窗口标题
        self.resize(900, 500)  # 设置窗口大小
        main_layout = QVBoxLayout(self)  # 主垂直布局
        main_layout.setSpacing(10)  # 设置控件间距

        # 顶部LOGO区域
        logo_layout = QHBoxLayout()  # 水平布局
        logo_label = QLabel()  # 图片标签
        logo_path = os.path.join(os.path.dirname(__file__), "PKU.png")  # LOGO图片路径
        if os.path.exists(logo_path):  # 如果图片存在
            pixmap = QPixmap(logo_path)  # 加载图片
            logo_label.setPixmap(pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))  # 缩放显示
        else:
            logo_label.setText("LOGO\n(PKU.png未找到)")  # 未找到图片时显示文字
            logo_label.setAlignment(Qt.AlignCenter)  # 居中
        logo_layout.addStretch()  # 左侧弹性
        logo_layout.addWidget(logo_label)  # 添加LOGO
        logo_layout.addStretch()  # 右侧弹性
        main_layout.addLayout(logo_layout)  # 添加到主布局

        # 中部按钮区
        btn_layout = QHBoxLayout()  # 水平布局
        btn_layout.setSpacing(40)  # 按钮间距

        # 参数库生成按钮
        self.param_btn = QPushButton("参数库生成")  # 创建按钮
        self.param_btn.setMinimumSize(160, 80)  # 设置最小尺寸
        self.param_btn.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))  # 设置字体
        self.param_btn.clicked.connect(self.open_param_lib)  # 绑定点击事件
        btn_layout.addWidget(self.param_btn)  # 添加到布局

        # 步骤生成按钮
        self.step_btn = QPushButton("步骤生成")
        self.step_btn.setMinimumSize(160, 80)
        self.step_btn.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        self.step_btn.clicked.connect(self.open_step_gen)
        btn_layout.addWidget(self.step_btn)

        # 精修主控按钮
        self.refine_btn = QPushButton("精修主控")
        self.refine_btn.setMinimumSize(160, 80)
        self.refine_btn.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        self.refine_btn.clicked.connect(self.open_refine)
        btn_layout.addWidget(self.refine_btn)

        main_layout.addLayout(btn_layout)  # 添加按钮区到主布局

        # 操作说明按钮区
        instr_layout = QHBoxLayout()  # 水平布局
        instr_layout.addStretch()  # 左侧弹性
        self.instr_btn = QPushButton("操作说明")  # 操作说明按钮
        self.instr_btn.setMinimumSize(120, 40)
        self.instr_btn.setFont(QFont("Microsoft YaHei", 11))
        self.instr_btn.clicked.connect(self.show_instruction)  # 绑定点击事件
        instr_layout.addWidget(self.instr_btn)
        instr_layout.addStretch()  # 右侧弹性
        main_layout.addLayout(instr_layout)  # 添加到主布局

        # 分隔线
        line = QFrame()  # 水平线控件
        line.setFrameShape(QFrame.HLine)  # 设置为水平线
        line.setFrameShadow(QFrame.Sunken)  # 设置阴影
        main_layout.addWidget(line)  # 添加到主布局

        # 底部开发者信息
        dev_info = (
            "This program is developed by Yujun Wan, PKUSZ Xiao Lab\n"
            "Thanks to all members in Xiao Lab for their support and contributions\n"
            "Provide suggestions or report bugs, please contact: wan_yujun@stu.pku.edu.cn"
        )
        dev_label = QLabel(dev_info)  # 开发者信息标签
        dev_label.setAlignment(Qt.AlignCenter)  # 居中
        dev_label.setFont(QFont("Arial", 10, QFont.StyleItalic))  # 设置字体
        dev_label.setWordWrap(True)  # 自动换行
        main_layout.addWidget(dev_label)  # 添加到主布局

        # 子窗口引用，防止被垃圾回收
        self.child_windows = []  # 用于保存子窗口引用

    def open_param_lib(self):
        # 打开参数库生成界面
        win = ParamLibGUI()  # 创建窗口
        win.show()  # 显示窗口
        self.child_windows.append(win)  # 保存引用

    def open_step_gen(self):
        # 打开步骤生成界面
        win = StepConfigGUI()
        win.show()
        self.child_windows.append(win)

    def open_refine(self):
        # 打开精修主控界面
        win = RefinementGUI()
        win.show()
        self.child_windows.append(win)

    def show_instruction(self):
        # 显示操作说明弹窗
        dlg = InstructionDialog(self)
        dlg.exec_()

if __name__ == "__main__":  # 主程序入口
    app = QApplication(sys.argv)  # 创建应用
    main_win = MainGUI()  # 创建主窗口
    main_win.show()  # 显示窗口
    sys.exit(app.exec_())  # 进入主事件循环