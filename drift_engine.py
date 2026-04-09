def find_drift(master_config_path, current_config):
    """Compara el archivo maestro con la config actual."""
    with open(master_config_path, 'r') as f:
        master = f.read()
    
    if master != current_config:
        return True # Se detectó un cambio
    return False
