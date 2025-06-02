#2025.5.17  实现对单相TOF所有参数的监控与抓取
'''
改进点：
1.实现对多相的监控
2.将手动精修的每个步骤pcr文件保存至临时文件夹
3.支持手动删去抓取记录
4.检测XYZ，OCC以及B值，出现负数时警告。
5.将抓取记录导入自动精修脚本中，复现手动精修过程

'''


from GUI_interface import MonitorGUI

if __name__ == "__main__":
    app = MonitorGUI()
    app.mainloop()