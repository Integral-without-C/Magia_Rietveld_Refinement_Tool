import re
from core_enhancedfilevalidator import EnhancedFileValidator
from core_parasparser import extract_atom_parameters
from config_parameters import PARAM_MAP, OPTIMIZED_RULES
from background_extract import BackgroundExtractor

class RefinementProcessor:
    def __init__(self, param_rules, atom_names, check_interval):
        self.step_counter = 1
        self.param_rules = param_rules
        self.atom_names = atom_names
        self.validator = EnhancedFileValidator(check_interval)
    
    def process_sum_file(self, sum_path):
        if not self.validator.is_valid_modification(sum_path):
            return None
        
        try:
            with open(sum_path, 'r', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"[错误] 文件读取失败: {str(e)}")
            return None
        
        chi2_match = re.search(r"Global user-weigthed Chi2 \(Bragg contrib\.\):\s+(\d+\.?\d*)", content)
        rwp_match = re.search(r"Rwp:\s+(\d+\.\d+)", content)
        if not chi2_match or not rwp_match:
            return None
        
        pcr_path = sum_path.replace(".sum", ".pcr")
        atom_params = {}
        try:
            with open(pcr_path, 'r', encoding='utf-8', errors='ignore') as f:
                pcr_content = f.read()
                atom_params = extract_atom_parameters(pcr_content, self.atom_names)
                background = BackgroundExtractor.extract_background(pcr_content)  # 提取背底点
        except Exception as e:
            print(f"[警告] 原子参数提取失败: {str(e)}")
        
        # 生成结果后递增step计数器
        result = {
            "step": self.step_counter,
            "chi2": chi2_match.group(1),
            "rwp": rwp_match.group(1),
            "params": self._extract_parameters(pcr_content),
            "atoms": atom_params,
            "background": background  # 新增背底数据
        }
        self.step_counter += 1  # 正确递增计数器
        return result

    def _extract_parameters(self, pcr_content):
        params = {}
        lines = pcr_content.split('\n')
        
        for line_num, line in enumerate(lines):
            for param, rules in self.param_rules.items():
                if param in line:
                    values = []
                    for rule in rules:
                        try:
                            target_line = line_num + rule['row_offset']
                            cols = re.split(r'\s+', lines[target_line].strip())
                            value = cols[rule['col_offset']]
                            if self._is_valid_value(value):
                                values.append(float(value))
                        except (IndexError, ValueError):
                            continue
                    
                    if len(values) >= rule.get('min_values', 2):
                        params[param] = values
        return params

    @staticmethod
    def _is_valid_value(value):
        try:
            return float(value) != 0
        except ValueError:
            return False