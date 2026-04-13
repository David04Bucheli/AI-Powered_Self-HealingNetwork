# main.py
import time
import os
from devices import all_devices
from network_driver import get_vyos_config, apply_repair
from drift_engine import detect_drift

POLLING_TIME = 60 # Tiempo de espera entre revisiones

def start_self_healing():
    print("--- INICIANDO SISTEMA DE AUTO-REPARACIÓN VYOS ---")
    while True:
        for device in all_devices:
            ip = device['host']
            master_cfg = f"master_configs/{ip}_master.txt"
            
            if not os.path.exists(master_cfg):
                print(f"[!] Error: No existe archivo maestro para {ip}. Saltando...")
                continue

            try:
                print(f"[*] Monitoreando {ip}...")
                current_config = get_vyos_config(device)
                
                # Detectar si hay cambios (Drift)
                diff = detect_drift(master_cfg, current_config)
                
                if diff:
                    print(f"[ALERT] Se detectó anomalía en {ip}. Reparando...")
                    apply_repair(device, diff)
                    print(f"[OK] {ip} ha sido restaurado exitosamente.")
                else:
                    print(f"[OK] {ip} sin cambios detectados.")

            except Exception as e:
                print(f"[ERROR] No se pudo conectar con {ip}: {e}")

        print(f"\nPróximo polling en {POLLING_TIME} segundos...\n")
        time.sleep(POLLING_TIME)

if __name__ == "__main__":
    start_self_healing()
