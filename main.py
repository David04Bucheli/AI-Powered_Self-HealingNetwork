import time
import os
from devices import all_devices
from network_driver import get_vyos_config, apply_repair
from drift_engine import detect_drift

POLLING_TIME = 60       # espera entre ciclos 

def start_self_healing():
    print("="*50)
    print("   SISTEMA DE AUTO-REPARACIÓN NETDEVOPS (VyOS)   ")
    print("="*50)
    
    while True:
        for device in all_devices:
            ip = device['host']
            master_cfg = f"master_configs/{ip}_master.txt"
            
            # existencia de router
            if not os.path.exists(master_cfg):
                print(f"[!] Error: No se encontró archivo maestro para {ip}")
                continue

            try:
                print(f"\n[*] Analizando {ip}...")
                current_config = get_vyos_config(device)
                
                # comandos faltantes y sobrantes
                missing, extra = detect_drift(master_cfg, current_config)
                
                if missing or extra:
                    print(f"[ALERT] Anomalía detectada en el router {ip}:")
                    
                    if extra:       # hay comandos de mas
                        for e in extra:
                            print(f"  [+] Sobra/Cambio: {e}")
                    if missing:     # faltan comandos
                        for m in missing:
                            print(f"  [-] Falta: {m}")
                    
                    # reparar - eliminar extra y agregar faltantes
                    repair_commands = []
                    for e in extra:
                        repair_commands.append(e.replace("set", "delete"))      # eliminamos comandos
                    
                    for m in missing:
                        repair_commands.append(m)

                    print("[*] Iniciando proceso de restauración automática...")
                    apply_repair(device, repair_commands)
                    print(f"[OK] {ip} ha vuelto a su estado original.")
                
                else:
                    print(f"[OK] {ip} se encuentra en cumplimiento (Sin drift).")

            except Exception as e:      # reportamos errores
                print(f"[ERROR] Fallo de conexión con {ip}: {e}")

        print(f"\n" + "-"*30)
        print(f"Ciclo completado. Próximo polling en {POLLING_TIME} segundos.")
        print("-"*30 + "\n")
        time.sleep(POLLING_TIME)

if __name__ == "__main__":
    start_self_healing()
