# ai_advisor.py
# Envía métricas de congestión a la API de Claude y recibe comandos VyOS de mitigación.
# Usa la API de Anthropic (claude-haiku — rápido y gratuito con créditos de prueba).

import json
import re
import urllib.request
import urllib.error

# ── Configuración ─────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = "TU_API_KEY_AQUI"          # <-- reemplaza con tu key
CLAUDE_MODEL      = "claude-haiku-4-5-20251001" # modelo rápido y económico
MAX_TOKENS        = 1024

SYSTEM_PROMPT = """Eres un experto en redes de computadores especializado en VyOS.
Tu tarea es analizar métricas de congestión de un router VyOS y devolver ÚNICAMENTE
un objeto JSON con el siguiente formato (sin texto adicional, sin markdown):

{
  "severity": "low|medium|high|critical",
  "reasoning": "Explicación técnica breve del problema detectado",
  "commands": ["set ...", "set ...", "delete ..."],
  "explanation": "Qué hace cada comando y por qué mitiga la congestión"
}

Reglas para los comandos VyOS:
- Usa sintaxis VyOS (set / delete), no Cisco IOS
- Prioriza: traffic shaping, rate-limiting, ajuste de timers OSPF, redistribución de carga
- Si no hay congestión real, devuelve commands: [] y severity: "low"
- Los comandos deben ser ejecutables directamente en 'configure' mode de VyOS
- Ejemplos de comandos válidos:
    set traffic-policy shaper WAN bandwidth '10mbit'
    set traffic-policy shaper WAN default bandwidth '20%'
    set interfaces ethernet eth1 traffic-policy out WAN
    set protocols ospf parameters router-id '10.0.0.1'
    set protocols ospf timers throttle spf 200 1000 10000
"""


def _build_user_prompt(metrics: dict) -> str:
    """Construye el prompt de usuario con las métricas del router."""
    ip = metrics.get('host', 'desconocido')
    anomalies = metrics.get('anomalies', [])
    interfaces = metrics.get('interfaces', [])
    ospf = metrics.get('ospf', {})

    lines = [f"Router analizado: {ip}", ""]

    # Resumen de interfaces
    lines.append("=== INTERFACES ===")
    for iface in interfaces:
        if 'lo' in iface.get('interface', ''):
            continue
        lines.append(
            f"  {iface['interface']}: estado={iface['state']}, "
            f"rx_pkts={iface['rx_packets']}, tx_pkts={iface['tx_packets']}, "
            f"rx_errors={iface['rx_errors']}, tx_drops={iface['tx_drops']}"
        )

    # Estado OSPF
    lines.append("")
    lines.append("=== OSPF ===")
    lines.append(f"  Vecinos totales: {ospf.get('neighbor_count', 0)}")
    lines.append(f"  Vecinos inestables (no-Full): {ospf.get('unstable_count', 0)}")
    for n in ospf.get('neighbors', []):
        lines.append(f"    {n['neighbor']} via {n['iface']} — {n['state']}")

    # Queue drops
    queue_drops = metrics.get('queue', {}).get('queue_drops', 0)
    lines.append("")
    lines.append(f"=== COLAS === drops_totales={queue_drops}")

    # Anomalías detectadas
    lines.append("")
    if anomalies:
        lines.append("=== ANOMALÍAS DETECTADAS ===")
        for a in anomalies:
            lines.append(
                f"  [{a['type']}] interfaz={a['interface']} "
                f"valor={a['value']}{a['unit']} (umbral={a['threshold']}{a['unit']}): {a['detail']}"
            )
    else:
        lines.append("=== ANOMALÍAS: Ninguna detectada ===")

    lines.append("")
    lines.append("Basándote en estas métricas, proporciona comandos VyOS para mitigar cualquier problema.")

    return "\n".join(lines)


def query_ai(metrics: dict) -> dict:
    """
    Envía las métricas a Claude y retorna el JSON de mitigación.
    Retorna un dict con severity, reasoning, commands, explanation.
    """
    prompt = _build_user_prompt(metrics)

    payload = json.dumps({
        "model":      CLAUDE_MODEL,
        "max_tokens": MAX_TOKENS,
        "system":     SYSTEM_PROMPT,
        "messages":   [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type":      "application/json",
            "x-api-key":         ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        # Extraer texto de la respuesta
        raw_text = ""
        for block in body.get("content", []):
            if block.get("type") == "text":
                raw_text += block["text"]

        # Limpiar posibles fences de markdown
        clean = re.sub(r'```(?:json)?|```', '', raw_text).strip()

        result = json.loads(clean)
        return result

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        return {
            "severity":    "unknown",
            "reasoning":   f"Error HTTP {e.code} al consultar la IA: {error_body[:200]}",
            "commands":    [],
            "explanation": "No se pudo obtener respuesta de la IA."
        }
    except json.JSONDecodeError as e:
        return {
            "severity":    "unknown",
            "reasoning":   f"La IA devolvió una respuesta no parseable: {raw_text[:300]}",
            "commands":    [],
            "explanation": "Error de parseo JSON."
        }
    except Exception as e:
        return {
            "severity":    "unknown",
            "reasoning":   f"Error inesperado: {str(e)}",
            "commands":    [],
            "explanation": "No se pudo completar la consulta."
        }
