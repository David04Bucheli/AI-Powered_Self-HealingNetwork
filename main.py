
"""
Sistema de Auto-Reparación NetDevOps con IA
Combina detección de drift de configuracion + monitoreo de congestin con IA.
"""

import time
import os
from devices import all_devices
from network_driver import get_vyos_config, apply_repair
from drift_engine import detect_drift
from congestion_monitor import collect_congestion_metrics, format_metrics_for_ai
from ai_advisor import get_ai_recommendation, print_recommendation, apply_ai_recommendation


# configuracion
POLLING_TIME = 60       # segundos entre ciclos
CONGESTION_CHECK_INTERVAL = 1       # cada N ciclos, revisar congestion
AUTO_APPLY_AI_COMMANDS = False      # si True, aplica comandos de IA automaticamente

# conexiones de routers
PING_TARGETS = {
    '192.168.1.1': ['10.0.12.2', '10.0.13.3', '192.168.2.1', '192.168.3.1'],  # R1 -> R2, R3, VPC2, VPC3
    '10.0.12.2':   ['192.168.1.1', '10.0.23.3', '192.168.1.1', '192.168.3.1'],  # R2 -> R1, R3, VPC1, VPC3
    '10.0.13.3':   ['192.168.1.1', '10.0.23.2', '192.168.1.1', '192.168.2.1'],  # R3 -> R1, R2, VPC1, VPC2
}


def check_configuration_drift(device):
    """Verifica y repara drift de configuración."""
    ip = device['host']
    master_cfg = f"master_configs/{ip}_master.txt"
    
    if not os.path.exists(master_cfg):
        print(f"[!] Error: No se encontró archivo maestro para {ip}")
        return False

    try:
        print(f"\n[*] Verificando configuración de {ip}...")
        current_config = get_vyos_config(device)
        
        missing, extra = detect_drift(master_cfg, current_config)
        
        if missing or extra:
            print(f"[ALERT] Anomalía de configuración en {ip}:")
            
            # if extra:
            #     for e in extra:
            #         # print(f"  [+] Sobra/Cambio: {e}")
            if missing:
                for m in missing:
                    print(f"  [-] Falta: {m}")
            
            repair_commands = []
            for e in extra:
                repair_commands.append(e.replace("set", "delete"))
            for m in missing:
                repair_commands.append(m)

            print("[*] Restaurando configuración original...")
            apply_repair(device, repair_commands)
            print(f"[OK] {ip} restaurado a configuración maestra.")
            return True
        else:
            print(f"[OK] {ip} - Configuración en cumplimiento.")
            return True

    except Exception as e:
        print(f"[ERROR] Fallo de conexión con {ip}: {e}")
        return False


def check_congestion_with_ai(device):
    """
    Monitorea congestión y consulta IA para mitigación.
    """
    ip = device['host']
    ping_targets = PING_TARGETS.get(ip, [])
    
    if not ping_targets:
        print(f"[!] No hay targets de ping definidos para {ip}")
        return
    
    print(f"\n[*] Analizando congestión en {ip}...")
    
    try:
        # recolectar métricas
        metrics = collect_congestion_metrics(device, ping_targets)
        
        # indicadores de congestión
        has_issues, issues = metrics.has_congestion_indicators()
        
        if has_issues:
            print(f"[ALERT] Indicadores de congestión detectados en {ip}:")
            for issue in issues:
                print(f"\t- {issue}")
            
            # Consultar a la IA
            print(f"\n[*] Consultando IA para recomendaciones...")
            
            try:
                recommendation = get_ai_recommendation(metrics)
                print_recommendation(recommendation, ip)
                
                # Aplicar si hay comandos y está habilitado o es de baja severidad
                if recommendation.commands:
                    apply_ai_recommendation(
                        device, 
                        recommendation, 
                        auto_apply=AUTO_APPLY_AI_COMMANDS
                    )
            
            except Exception as ai_error:
                print(f"[ERROR] Fallo al consultar IA: {ai_error}")
                print("[INFO] Continando sin recomendaciones de IA...")
        
        else:
            print(f"[OK] {ip} - Sin indicadores de congestión")
            # Opcional: mostrar métricas resumidas
            for ping in metrics.ping_results:
                print(f"\t{ping.destination}: RTT={ping.rtt_avg:.1f}ms, Loss={ping.packet_loss_percent}%")
    
    except Exception as e:
        print(f"[ERROR] Fallo al monitorear congestión en {ip}: {e}")


def start_self_healing_with_ai():
    """
    Loop principal que combina:
    1. Detección de drift de configuración (cada ciclo)
    2. Monitoreo de congestión con IA (cada N ciclos)
    """
    print("="*60)
    print("   SISTEMA DE AUTO-REPARACIÓN NETDEVOPS CON IA (VyOS)   ")
    print("="*60)
    
    # Verificar API key de OpenAI
    api_key = "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"
    if not api_key:
        print("\n[!] ADVERTENCIA: API_KEY no configurada")
        print("[!] El análisis de congestión con IA no estará disponible")
        print("[!] Configura la variable de entorno: export OPENAI_API_KEY='tu-api-key'")
        ai_enabled = False
    else:
        print("\n[OK] API key detectada - IA habilitada")
        ai_enabled = True
    
    print(f"\n[CONFIG] Polling cada {POLLING_TIME} segundos")
    print(f"[CONFIG] Análisis de congestión cada {CONGESTION_CHECK_INTERVAL} ciclos")
    print(f"[CONFIG] Auto-aplicar comandos de IA: {'SÍ ' if AUTO_APPLY_AI_COMMANDS else 'NO (manual)'}")
    
    cycle_count = 0
    
    while True:
        cycle_count += 1
        print(f"\n{'='*60}")
        print(f"   CICLO #{cycle_count}")
        print(f"{'='*60}")
        
        # 1. Verificar drift de configuración en todos los routers
        print("\n" + "-"*40)
        print("\tFASE 1: Verificación de Configuración")
        print("-"*40)
        
        for device in all_devices:
            check_configuration_drift(device)
        
        # 2. Monitoreo de congestión (cada N ciclos)
        if ai_enabled and (cycle_count % CONGESTION_CHECK_INTERVAL == 0):
            print("\n" + "-"*40)
            print("\tFASE 2: Análisis de Congestión con IA")
            print("-"*40)
            
            for device in all_devices:
                check_congestion_with_ai(device)
        
        # Esperar siguiente ciclo
        print(f"\n" + "-"*40)
        print(f"Ciclo #{cycle_count} completado.")
        if ai_enabled:
            next_ai = CONGESTION_CHECK_INTERVAL - (cycle_count % CONGESTION_CHECK_INTERVAL)
            print(f"Próximo análisis de congestión en {next_ai} ciclo(s).")
        print(f"Siguiente polling en {POLLING_TIME} segundos...")
        print("-"*40 + "\n")
        
        time.sleep(POLLING_TIME)


# Modo de prueba rápida de congestión
def test_congestion_analysis():
    """
    Modo de prueba: analiza congestión una sola vez sin loop.
    Útil para testing y demos.
    """
    print("="*60)
    print("\tMODO DE PRUEBA - Análisis de Congestión")
    print("="*60)

    api_key = "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"
    if not api_key:
        print("\n[ERROR] OPENAI_API_KEY no configurada")
        print("Configura: export OPENAI_API_KEY='tu-api-key'")
        return
    
    for device in all_devices:
        print(f"\n{'='*40}")
        print(f"Router: {device['host']}")
        print(f"{'='*40}")
        check_congestion_with_ai(device)
    
    print("\n[FIN] Prueba completada")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_congestion_analysis()
    else:
        start_self_healing_with_ai()
