import time
from devices import all_devices
from network_driver import get_running_config, apply_remediation
from drift_engine import find_drift

POLLING_INTERVAL = 60  # Segundos entre cada revisión

def run_monitor():
    print("--- Iniciando Sistema de Auto-reparación ---")
    while True:
        for device in all_devices:
            print(f"Revisando estado de: {device['host']}...")
            
            try:
                # 1. Obtener config actual (Polling SSH)
                current_cfg = get_running_config(device)
                
                # 2. Detectar Drift (Deriva de configuración)
                master_path = f"master_configs/{device['host']}_master.txt"
                if find_drift(master_path, current_cfg):
                    print(f"¡ALERTA! Se detectó un cambio no autorizado en {device['host']}.")
                    
                    # 3. Reparación
                    print("Restaurando configuración maestra...")
                    with open(master_path, 'r') as f:
                        master_content = f.read()
                    
                    # Convertimos el archivo maestro en una lista de comandos para Netmiko
                    commands = master_content.splitlines()
                    apply_remediation(device, commands)
                    print("Reparación exitosa.")
                else:
                    print(f"Estado de {device['host']}: OK (Sin cambios).")
                    
            except Exception as e:
                print(f"Error al conectar con {device['host']}: {e}")
        
        print(f"Esperando {POLLING_INTERVAL} segundos para la próxima revisión...")
        time.sleep(POLLING_INTERVAL)

if __name__ == "__main__":
    run_monitor()
