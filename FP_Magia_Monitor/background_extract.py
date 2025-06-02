# 在core目录下新建background.py
import re

class BackgroundExtractor:
    @staticmethod
    def extract_background(pcr_content):
        """提取背底数据（第三列不为零时记录）"""
        pattern = re.compile(
            r'!2Theta/TOF/E\(Kev\)[\s\S]*?\n(.*?)\n\s*!',    #如果需要提取两相，则需要明确加入Pattern#  1
            re.DOTALL
        )
        match = pattern.search(pcr_content)
        
        if not match:
            return None
        
        valid_data = []
        lines = [
            line.strip() 
            for line in match.group(1).split('\n') 
            if line.strip()
        ]

        #number_of_background = len(lines)      #手动选择差值背底点数目
        
        for line in lines:
            numbers = re.findall(r'-?\d+\.\d+', line)
            if len(numbers) >= 3:
                try:
                    # 检查第三列数值是否非零
                    if float(numbers[2]) != 0:
                        valid_data.append([
                            f"{float(numbers[0]):.4f}",
                            f"{float(numbers[1]):.4f}",
                            f"{float(numbers[2]):.4f}"
                        ])
                except (IndexError, ValueError):
                    continue
        #refinement_background=len(valid_data)

        return valid_data if valid_data else None