# main.py  —  Sistema de Auto-Reparación NetDevOps con IA (VyOS)
# Combina detección de drift de configuración + detección de congestión con IA

import time
import os
import json
from datetime import datetime

from devices import all_devices
from network_driver import get_vyos_config, apply_repair
from drift_engine import detect_drift
from congestion_monitor import collect_metrics
from ai_advisor import query_ai

# ── Configuración global ──────────────────────────────────────────────────────
POLLING_TIME = 60      # segundos entre ciclos completos
CONGESTION_CYCLES = 2       # cada cuántos ciclos se corre el análisis de congestión
APPLY_AI_COMMANDS = False   # True = aplica comandos de la IA automáticamente (¡cuidado!)
LOG_FILE = "selfhealing.log"

_cycle_count = 0


def log(msg: str):
    """Imprime con timestamp y escribe en log."""
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = f"[{ts}] {msg}"
    print(out)
    with open(LOG_FILE, "a") as f:
        f.write(out + "\n")


def handle_drift(device: dict):
    """Detecta y repara drift de configuración (lógica original)."""
    ip         = device['host']
    master_cfg = f"master_configs/{ip}_master.txt"

    if not os.path.exists(master_cfg):
        log(f"[!] No se encontró archivo maestro para {ip}")
        return

    current_config = get_vyos_config(device)
    missing, extra = detect_drift(master_cfg, current_config)

    if missing or extra:
        log(f"[ALERT] Drift detectado en {ip}:")
        for e in extra:
            log(f"  [+] Sobra: {e}")
        for m in missing:
            log(f"  [-] Falta: {m}")

        repair_commands = []
        for e in extra:
            repair_commands.append(e.replace("set", "delete", 1))
        for m in missing:
            repair_commands.append(m)

        log(f"[*] Reparando configuración de {ip}...")
        apply_repair(device, repair_commands)
        log(f"[OK] {ip} restaurado.")
    else:
        log(f"[OK] {ip} sin drift de configuración.")


def handle_congestion(device: dict):
    """
    Recolecta métricas de congestión, consulta a la IA y
    opcionalmente aplica los comandos sugeridos.
    """
    ip = device['host']
    log(f"[AI] Recolectando métricas de congestión en {ip}...")

    metrics = collect_metrics(device)

    if not metrics['anomalies']:
        log(f"[AI] {ip} — Sin anomalías de congestión detectadas.")
        return

    # Hay anomalías: consultar a la IA
    log(f"[AI] {ip} — {len(metrics['anomalies'])} anomalía(s) detectada(s). Consultando IA...")
    for a in metrics['anomalies']:
        log(f"      ↳ [{a['type']}] {a['detail']}")

    ai_response = query_ai(metrics)

    # Mostrar razonamiento de la IA
    severity    = ai_response.get('severity', 'unknown')
    reasoning   = ai_response.get('reasoning', '')
    commands    = ai_response.get('commands', [])
    explanation = ai_response.get('explanation', '')

    log(f"[AI] Severidad evaluada: {severity.upper()}")
    log(f"[AI] Razonamiento: {reasoning}")
    log(f"[AI] Explicación de comandos: {explanation}")

    if commands:
        log(f"[AI] Comandos de mitigación sugeridos ({len(commands)}):")
        for cmd in commands:
            log(f"      → {cmd}")

        if APPLY_AI_COMMANDS:
            log(f"[AI] Aplicando comandos de mitigación en {ip}...")
            apply_repair(device, commands)
            log(f"[AI] Comandos aplicados en {ip}.")
        else:
            log(f"[AI] APPLY_AI_COMMANDS=False — comandos NO aplicados (modo auditoría).")
    else:
        log(f"[AI] La IA no sugirió comandos adicionales.")

    # Guardar reporte JSON para el dashboard
    report = {
        "timestamp": datetime.now().isoformat(),
        "host":      ip,
        "metrics":   metrics,
        "ai":        ai_response,
    }
    report_path = f"reports/{ip.replace('.', '_')}_latest.json"
    os.makedirs("reports", exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    log(f"[AI] Reporte guardado en {report_path}")


def start_self_healing():
    global _cycle_count

    log("=" * 55)
    log("   SISTEMA AUTO-REPARACIÓN NetDevOps + IA  (VyOS)   ")
    log("=" * 55)
    log(f"Dispositivos: {[d['host'] for d in all_devices]}")
    log(f"Polling: cada {POLLING_TIME}s | Análisis IA: cada {CONGESTION_CYCLES} ciclos")
    log(f"Aplicar comandos IA: {'SÍ' if APPLY_AI_COMMANDS else 'NO (modo auditoría)'}")
    log("")

    while True:
        _cycle_count += 1
        log(f"{'─'*20} Ciclo #{_cycle_count} {'─'*20}")

        run_congestion = (_cycle_count % CONGESTION_CYCLES == 0)

        for device in all_devices:
            ip = device['host']
            try:
                # Siempre: detección de drift
                log(f"[DRIFT] Analizando {ip}...")
                handle_drift(device)

                # Cada N ciclos: análisis de congestión con IA
                if run_congestion:
                    handle_congestion(device)

            except Exception as e:
                log(f"[ERROR] Fallo con {ip}: {e}")

        log(f"\nCiclo #{_cycle_count} completado. Próximo en {POLLING_TIME}s.")
        log("─" * 55 + "\n")
        time.sleep(POLLING_TIME)


if __name__ == "__main__":
    start_self_healing()
