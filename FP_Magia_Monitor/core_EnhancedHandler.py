import os
from watchdog.events import FileSystemEventHandler
from core_RefinementProcessor import RefinementProcessor
from background_extract import BackgroundExtractor

class EnhancedHandler(FileSystemEventHandler):
    def __init__(self, output_path, param_rules, atom_names, log_callback, check_interval):
        self.output_path = output_path
        if os.path.exists(output_path):
            os.remove(output_path)
        self.processor = RefinementProcessor(param_rules, atom_names, check_interval)
        self.log_callback = log_callback

    def on_modified(self, event):
        if event.src_path.endswith(".sum"):
            if result := self.processor.process_sum_file(event.src_path):
                self._write_log(result)
                self.log_callback(f"✅ Step {result['step']} 抓取成功 (含{len(result['atoms'])}种原子参数)")

    def _write_log(self, data):
        try:
            with open(self.output_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\nStep: {data['step']}\n")
                f.write(f"Chi² = {data['chi2']}, Rwp = {data['rwp']}%\n\n")
                
                f.write("【常规参数】\n")
                for param, values in data['params'].items():
                    f.write(f"{param:<10}  {', '.join(map(str, values))}\n")
                
                f.write("\n【原子参数】\n")
                for atom, instances in data['atoms'].items():
                    if not instances:
                        continue
                    f.write(f"● {atom}\n")
                    for idx, values in enumerate(instances, 1):
                        f.write(f"")
                        for k, v in values.items():
                            parts = v.split()
                            if len(parts) > 1 and float(parts[1]) != 0:
                                f.write(f"  {k:<8}  {v}\n")
                            else:
                                f.write(f"")
                    f.write("\n")
                # 新增背底数据写入
                if data.get('background'):
                    f.write("\n【背底参数】\n")
                    #f.write("手动插值背底点个数：{number_of_background}，修正个数：{refinement_background}\n")
                    for row in data['background']:
                        f.write(f"{row[0]:>12}  {row[1]:>12}  {row[2]:>12}\n")
                
                f.write(f"{'='*50}\n")
        
        except Exception as e:
            print(f"[日志错误] {str(e)}")