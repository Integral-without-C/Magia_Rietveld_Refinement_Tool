import sys
import re
import json

# 默认阈值，可用 json 文件覆盖
OCC_LIMITS = {
    "Li6h": (0, 0.5),
    "Li6g": (0, 0.5),
    "Y2d_1": (0, 0.16667),
    "Y2d_2": (0, 0.16667),
    # 其他原子可继续添加
}

def load_limits(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            limits = json.load(f)
        # 转换为 float
        for k, v in limits.items():
            OCC_LIMITS[k] = (float(v[0]), float(v[1]))
    except Exception:
        pass

def check_pcr(pcr_path, limits_path=None):
    if limits_path:
        load_limits(limits_path)
    with open(pcr_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    errors = []
    atom_section = False
    for idx, line in enumerate(lines):
        if re.match(r'!Atom\s+Typ\s+X\s+Y\s+Z\s+Biso\s+Occ', line):
            atom_section = True
            continue
        if atom_section:
            if line.strip() == "" or line.strip().startswith("!"):
                atom_section = False
                continue
            parts = line.strip().split()
            if len(parts) >= 7:
                atom_name = parts[0]
                try:
                    Biso = float(parts[5])
                    Occ = float(parts[6])
                    if Biso < 0:
                        errors.append(f"{atom_name} Biso={Biso} 热振动因子小于 0 ！")
                    # OCC 检查
                    occ_min, occ_max = OCC_LIMITS.get(atom_name, (0, 1))
                    if not (occ_min < Occ <= occ_max):
                        errors.append(f"{atom_name} Occ={Occ} 占有率不在合理范围 {occ_min}~{occ_max}！")
                except Exception:
                    continue
    return errors

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: PCR_check.py <pcr_file> [limits_json]")
        sys.exit(1)
    pcr_file = sys.argv[1]
    limits_file = sys.argv[2] if len(sys.argv) > 2 else None
    errs = check_pcr(pcr_file, limits_file)
    if errs:
        print("ERROR")
        for e in errs:
            print(e)
        sys.exit(2)
    else:
        print("OK")
        sys.exit(0)