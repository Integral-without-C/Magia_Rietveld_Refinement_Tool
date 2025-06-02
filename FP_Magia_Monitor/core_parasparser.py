#精修参数解析与定位
import re
from collections import defaultdict
from config_parameters import PARAM_MAP

def parse_atom_block(block):
    """解析并过滤无效参数"""
    results = {}
    has_valid = False  # 标记是否有有效参数
    
    for param, positions in PARAM_MAP.items():
        values = []
        for idx, (row, col) in enumerate(positions):
            try:
                val = block[row][col]
                values.append(val)
                # 检查第二个数值是否非零
                if idx == 1 and float(val) != 0:
                    has_valid = True
            except (IndexError, KeyError, ValueError):
                continue
        results[param] = ' '.join(values) if values else 'N/A'
    
    return results if has_valid else None  # 返回None表示无效数据

def extract_atom_parameters(pcr_content, atom_names):
    lines = [line.strip() for line in pcr_content.split('\n') if line.strip()]
    atom_patterns = {name: re.compile(rf"^{re.escape(name)}\s+") for name in atom_names}
    
    results = defaultdict(list)
    current_line = 0
    
    while current_line < len(lines):
        matched = False
        for atom, pattern in atom_patterns.items():
            if pattern.match(lines[current_line]):
                block = []
                for offset in range(4):
                    idx = current_line + offset
                    block.append(re.split(r'\s+', lines[idx]) if idx < len(lines) else [])
                
                parsed = parse_atom_block(block)
                if parsed:  # 只保留有效数据
                    results[atom].append(parsed)
                current_line += 4
                matched = True
                break
        if not matched:
            current_line += 1
    
    return dict(results)