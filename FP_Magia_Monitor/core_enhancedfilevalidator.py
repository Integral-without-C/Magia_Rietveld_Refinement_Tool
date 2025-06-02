#文件解析与验证
import os
import time
import hashlib
import threading

class EnhancedFileValidator:
    def __init__(self, check_interval=1.5):
        self.file_versions = {}
        self.lock = threading.Lock()
        self.check_interval = check_interval

    def is_valid_modification(self, file_path):
        try:
            time.sleep(self.check_interval)
            with self.lock:
                if not os.path.exists(file_path):
                    return False

                stat = os.stat(file_path)
                if stat.st_size == 0:
                    return False

                hashes = []
                with open(file_path, 'rb') as f:
                    for _ in range(5):
                        f.seek(0)
                        hashes.append(hashlib.md5(f.read()).hexdigest())
                        time.sleep(1)
                
                if len(set(hashes)) != 1:
                    return False

                current_hash = hashes[0]
                
                if file_path not in self.file_versions:
                    self.file_versions[file_path] = (current_hash, time.time())
                    return True
                
                last_hash, last_time = self.file_versions[file_path]
                if (time.time() - last_time) < 5:
                    return False
                
                if current_hash != last_hash:
                    self.file_versions[file_path] = (current_hash, time.time())
                    return True
                
                return False
        except Exception as e:
            print(f"[校验器错误] {str(e)}")
            return False