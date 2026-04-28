# ai_advisor.py
"""
Módulo de asesoría de IA para mitigación de congestión en redes VyOS.
Usa la API de OpenAI para analizar métricas y generar comandos de mitigación.
"""

import os
import json
from dataclasses import dataclass
from openai import OpenAI
from congestion_monitor import CongestionMetrics, format_metrics_for_ai


@dataclass
class AIRecommendation:
    """Recomendación de la IA para mitigar congestión."""
    analysis: str               # Análisis del problema
    severity: str               # "low", "medium", "high", "critical"
    commands: list[str]         # Comandos VyOS a ejecutar
    reasoning: str              # Explicación de por qué estos comandos
    rollback_commands: list[str]  # Comandos para revertir si algo sale mal
    requires_human_approval: bool  # Si es muy crítico, pedir aprobación


# Prompt del sistema que define el comportamiento de la IA
SYSTEM_PROMPT = """Eres un experto en redes especializado en routers VyOS y mitigación de congestión.
Tu trabajo es analizar métricas de red y proporcionar comandos específicos de VyOS para mitigar problemas.

CONTEXTO DE LA RED:
- Topología: 3 routers VyOS en triángulo (R1, R2, R3)
- Protocolo de enrutamiento: OSPF (area 0)
- Cada router tiene una VPC conectada a eth0
- Enlaces entre routers en eth1 y eth2

MÉTRICAS QUE RECIBIRÁS:
- Estadísticas de interfaces (packets, bytes, dropped, errors)
- Resultados de ping (RTT, packet loss, jitter/mdev)
- Cantidad de vecinos OSPF

INDICADORES DE CONGESTIÓN:
- Packet loss > 5% = congestión moderada
- Packet loss > 20% = congestión severa
- RTT > 100ms = latencia alta
- RTT mdev (jitter) > 50ms = inestabilidad
- Dropped packets > 100 = cola de interfaz saturada
- Errores de interfaz = posible problema de capa física

COMANDOS DE MITIGACIÓN DISPONIBLES EN VYOS:
1. Traffic Shaping (limitar ancho de banda):
   set traffic-policy shaper <name> bandwidth <rate>
   set traffic-policy shaper <name> default bandwidth <rate>
   set interfaces ethernet <ethX> traffic-policy out <name>

2. Modificar costos OSPF (cambiar rutas):
   set interfaces ethernet <ethX> ip ospf cost <valor>
   (mayor costo = menos preferida, default=10, máximo=65535)

3. Rate Limiting con traffic-policy:
   set traffic-policy limiter <name> default bandwidth <rate>
   set interfaces ethernet <ethX> traffic-policy in <name>

4. QoS con colas de prioridad:
   set traffic-policy priority-queue <name> class <n> match <match-name> ...
   set traffic-policy priority-queue <name> class <n> queue-limit <pkts>

REGLAS IMPORTANTES:
- SIEMPRE devuelve JSON válido con la estructura especificada
- Los comandos deben ser comandos VyOS en modo configuración (sin "configure")
- Incluye comandos de rollback para revertir cambios
- Si la congestión es severa (>50% loss), marca requires_human_approval=true
- Prioriza soluciones que NO rompan la conectividad
- Para congestión leve, prefiere ajustar costos OSPF para redistribuir tráfico
- Para congestión severa, usa traffic shaping

FORMATO DE RESPUESTA (JSON):
{
    "analysis": "Descripción del problema detectado",
    "severity": "low|medium|high|critical",
    "commands": ["comando1", "comando2", ...],
    "reasoning": "Explicación técnica de por qué estos comandos ayudarán",
    "rollback_commands": ["delete comando1", "delete comando2", ...],
    "requires_human_approval": false
}
"""


def get_ai_recommendation(
    metrics: CongestionMetrics,
    api_key: str = None,
    model: str = "gpt-4o-mini"
) -> AIRecommendation:
    """
    Envía métricas de congestión a OpenAI y obtiene recomendaciones.
    
    Args:
        metrics: Métricas de congestión del router
        api_key: API key de OpenAI (o usa OPENAI_API_KEY del entorno)
        model: Modelo de OpenAI a usar
    
    Returns:
        AIRecommendation con análisis y comandos
    """
    # Usar API key del parámetro o del entorno
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Se requiere OPENAI_API_KEY en el entorno o como parámetro")
    
    client = OpenAI(api_key=api_key)
    
    # Formatear métricas para la IA
    metrics_text = format_metrics_for_ai(metrics)
    
    # Agregar contexto adicional sobre problemas detectados
    has_issues, issues = metrics.has_congestion_indicators()
    
    user_message = f"""Analiza las siguientes métricas de red y proporciona comandos de mitigación si es necesario.

{metrics_text}

{'PROBLEMAS DETECTADOS: ' + ', '.join(issues) if has_issues else 'No se detectaron problemas obvios, pero revisa las métricas por cualquier anomalía.'}

Por favor responde ÚNICAMENTE con JSON válido siguiendo el formato especificado."""

    # Llamar a la API de OpenAI
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        temperature=0.3,  # Baja temperatura para respuestas más consistentes
        response_format={"type": "json_object"}  # Forzar respuesta JSON
    )
    
    # Parsear respuesta JSON
    response_text = response.choices[0].message.content
    data = json.loads(response_text)
    
    return AIRecommendation(
        analysis=data.get("analysis", "No se pudo analizar"),
        severity=data.get("severity", "low"),
        commands=data.get("commands", []),
        reasoning=data.get("reasoning", "Sin razonamiento proporcionado"),
        rollback_commands=data.get("rollback_commands", []),
        requires_human_approval=data.get("requires_human_approval", False),
    )


def print_recommendation(rec: AIRecommendation, router_ip: str):
    """Imprime la recomendación de forma legible."""
    severity_colors = {
        "low": "🟢",
        "medium": "🟡", 
        "high": "🟠",
        "critical": "🔴"
    }
    
    icon = severity_colors.get(rec.severity, "⚪")
    
    print("\n" + "="*60)
    print(f"🤖 ANÁLISIS DE IA - Router {router_ip}")
    print("="*60)
    print(f"\n{icon} Severidad: {rec.severity.upper()}")
    print(f"\n📊 Análisis:")
    print(f"   {rec.analysis}")
    print(f"\n💡 Razonamiento:")
    print(f"   {rec.reasoning}")
    
    if rec.commands:
        print(f"\n🔧 Comandos de mitigación:")
        for cmd in rec.commands:
            print(f"   • {cmd}")
    else:
        print(f"\n✅ No se requieren comandos de mitigación")
    
    if rec.rollback_commands:
        print(f"\n↩️  Comandos de rollback (si hay problemas):")
        for cmd in rec.rollback_commands:
            print(f"   • {cmd}")
    
    if rec.requires_human_approval:
        print(f"\n⚠️  REQUIERE APROBACIÓN HUMANA antes de ejecutar")
    
    print("="*60 + "\n")


def apply_ai_recommendation(device_params: dict, rec: AIRecommendation, auto_apply: bool = False) -> bool:
    """
    Aplica los comandos recomendados por la IA al router.
    
    Args:
        device_params: Parámetros de conexión Netmiko
        rec: Recomendación de la IA
        auto_apply: Si True, aplica sin pedir confirmación (excepto si requires_human_approval)
    
    Returns:
        True si se aplicaron los comandos, False si no
    """
    from network_driver import apply_repair
    
    if not rec.commands:
        print("[INFO] No hay comandos que aplicar")
        return False
    
    # Si requiere aprobación humana, siempre preguntar
    if rec.requires_human_approval:
        print("\n⚠️  La IA recomienda aprobación humana para estos cambios.")
        print("Comandos propuestos:")
        for cmd in rec.commands:
            print(f"  • {cmd}")
        
        response = input("\n¿Desea aplicar estos comandos? (s/n): ").strip().lower()
        if response != 's':
            print("[INFO] Comandos NO aplicados por decisión del usuario")
            return False
    
    # Si no es auto_apply, preguntar
    elif not auto_apply:
        print("\nComandos propuestos:")
        for cmd in rec.commands:
            print(f"  • {cmd}")
        
        response = input("\n¿Desea aplicar estos comandos? (s/n): ").strip().lower()
        if response != 's':
            print("[INFO] Comandos NO aplicados por decisión del usuario")
            return False
    
    # Aplicar comandos
    try:
        print(f"\n[*] Aplicando {len(rec.commands)} comandos de mitigación...")
        apply_repair(device_params, rec.commands)
        print("[OK] Comandos aplicados exitosamente")
        return True
    except Exception as e:
        print(f"[ERROR] Fallo al aplicar comandos: {e}")
        
        # Intentar rollback si hay comandos de rollback
        if rec.rollback_commands:
            print("[*] Intentando rollback...")
            try:
                apply_repair(device_params, rec.rollback_commands)
                print("[OK] Rollback exitoso")
            except Exception as e2:
                print(f"[ERROR] Rollback falló: {e2}")
        
        return False
