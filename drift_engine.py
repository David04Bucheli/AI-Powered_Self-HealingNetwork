# drift_engine.py

def detect_drift(master_file_path, current_config):
    """
    Compara la configuración actual con el archivo maestro línea por línea.
    Retorna una lista de comandos que faltan en el equipo.
    """
    with open(master_file_path, 'r') as f:
        master_lines = set(line.strip() for line in f if line.strip())
    
    current_lines = set(line.strip() for line in current_config.splitlines() if line.strip())
    
    # Identificar líneas que están en el maestro pero NO en el router actual
    missing_commands = list(master_lines - current_lines)
    
    return missing_commands
