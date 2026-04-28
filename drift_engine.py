# drift_engine.py

def detect_drift(master_file_path, current_config):
    with open(master_file_path, 'r') as f:
        master_lines = set(line.strip() for line in f if line.strip())
    
    current_lines = set(line.strip() for line in current_config.splitlines() if line.strip())
    
    missing = list(master_lines - current_lines)        # comandos que faltan
    
    extra = list(current_lines - master_lines)      # comandos que sobran
    
    return missing, extra
