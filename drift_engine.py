# drift_engine.py

def detect_drift(master_file_path, current_config):
    with open(master_file_path, 'r') as f:
        master_lines = set(line.strip() for line in f if line.strip())
    
    current_lines = set(line.strip() for line in current_config.splitlines() if line.strip())
    
    # Comandos que están en el maestro pero NO en el router (Lo que falta)
    missing = list(master_lines - current_lines)
    
    # Comandos que están en el router pero NO en el maestro (Lo que sobra/cambió)
    extra = list(current_lines - master_lines)
    
    return missing, extra
