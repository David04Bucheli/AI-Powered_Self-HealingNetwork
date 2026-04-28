# NetDevOps Self-Healing Network con IA

> Red auto-reparable sobre VyOS + GNS3 con monitoreo de congestión mediante inteligencia artificial.

---

## Descripción

Sistema de automatización de redes que combina:

- **Detección de drift de configuración**: compara la configuración actual de cada router contra un archivo maestro `.txt` y restaura cualquier cambio no autorizado.
- **Monitoreo de congestión**: recolecta métricas de RTT, jitter, packet loss y drops de interfaz vía SSH desde los routers VyOS.
- **IA para mitigación**: cuando se detectan anomalías, envía las métricas a un LLM (API NVIDIA, compatible con OpenAI SDK) que devuelve comandos VyOS de mitigación con razonamiento técnico y rollback.

Todo corre en un loop de polling configurable (por defecto 60 segundos).

---

## Topología de Red

```
           [VPC1]
             |
           [R1] — 192.168.1.1
          /     \
    eth1 /       \ eth2
        /         \
     [R2]    ---   [R3]
  10.0.12.2         10.0.13.3
      |                |
   [VPC2]           [VPC3]

Enlace R2-R3: 10.0.23.0/24 (dashed — vía eth2 de cada uno)
```

- **R1**: hub central, eth0 → VPC1, eth1 → R2 (10.0.12.0/24), eth2 → R3 (10.0.13.0/24)
- **R2**: eth0 → VPC2, eth1 → R1, eth2 → R3 (10.0.23.0/24)
- **R3**: eth0 → VPC3, eth1 → R2, eth2 → R1
- Protocolo de enrutamiento: **OSPF Area 0**
- Acceso externo: adaptador **KVM by Microsoft** (192.168.56.1)

---

## Estructura del proyecto

```
netdevops/
├── main.py                  # Loop principal (drift + congestión)
├── devices.py               # Credenciales de los 3 routers
├── network_driver.py        # SSH via Netmiko: get config / apply repair
├── drift_engine.py          # Comparación config actual vs. maestra
├── congestion_monitor.py    # Recolección de métricas de congestión
├── ai_advisor.py            # Consulta a IA y aplicación de comandos
└── master_configs/
    ├── 192.168.1.1_master.txt
    ├── 10.0.12.2_master.txt
    └── 10.0.13.3_master.txt
```

---

## Requisitos

```bash
pip install netmiko openai
```

Python 3.10+ recomendado (uso de `list[...]` como type hint).

---

## Configuración del entorno (Windows + GNS3)

Estos pasos son necesarios para que el host Windows pueda hacer SSH a los routers VyOS en GNS3.

### 1. Instalar adaptador de red KVM by Microsoft

Descarga e instala el adaptador de red virtual KVM desde Windows Update o desde el repositorio de Microsoft. Aparecerá como interfaz de red en el sistema.

### 2. Configurar IP del adaptador KVM

```
Win + R → ncpa.cpl
```

Selecciona el adaptador **KVM** → Propiedades → Protocolo TCP/IPv4 → Manual:

| Campo   | Valor           |
|---------|-----------------|
| IP      | 192.168.56.1    |
| Máscara | 255.255.255.0   |

Acepta y guarda.

### 3. Encender la topología en GNS3

Abre GNS3 y pon en marcha todos los nodos de la topología.

### 4. Agregar rutas estáticas desde CMD (modo Administrador)

```cmd
route add 10.0.12.0 mask 255.255.255.0 192.168.1.1
route add 10.0.13.0 mask 255.255.255.0 192.168.1.1
```

### 5. Verificar conectividad

```cmd
ping 192.168.1.1   # R1
ping 10.0.12.2     # R2
ping 10.0.13.3     # R3
```

---

## Configuración de la IA

En `ai_advisor.py`, reemplaza la API key de NVIDIA:

```python
api_key = "nvapi-TU_KEY_AQUI"
```

Obtén tu API key gratuita en [https://integrate.api.nvidia.com](https://integrate.api.nvidia.com).

El modelo por defecto es `moonshotai/kimi-k2-thinking`. Puedes cambiarlo a cualquier modelo disponible en la plataforma NVIDIA AI.

---

## Uso

### Modo normal (loop continuo)

```bash
python main.py
```

### Modo prueba (un solo análisis, sin loop)

```bash
python main.py --test
```

### Variables configurables en `main.py`

| Variable                  | Valor por defecto | Descripción                                      |
|---------------------------|-------------------|--------------------------------------------------|
| `POLLING_TIME`            | 60                | Segundos entre ciclos de polling                 |
| `CONGESTION_CHECK_INTERVAL` | 1               | Cada N ciclos se ejecuta el análisis con IA      |
| `AUTO_APPLY_AI_COMMANDS`  | False             | Si True, aplica comandos de IA automáticamente   |

---

## Métricas monitoreadas

| Métrica       | Umbral moderado | Umbral severo | Fuente                    |
|---------------|-----------------|---------------|---------------------------|
| Packet loss   | > 5%            | > 20%         | `ping count 10` por router|
| RTT promedio  | > 55 ms         | > 100 ms      | `ping` mdev               |
| Jitter (mdev) | > 20 ms         | > 50 ms       | `ping` mdev               |
| TX drops      | > 100 pkts      | > 500 pkts    | `show interfaces detail`  |
| RX errors     | > 50            | > 200         | `show interfaces detail`  |

---

## Simular congestión en GNS3

GNS3 no está diseñado para saturar la red a nivel de throughput real: los enlaces virtuales no se comportan como hardware, y herramientas como `iperf3` no producen drops o errores visibles en los contadores de interfaz.

**Solución**: usar `tc` (traffic control / netem) directamente en la consola del router VyOS:

```bash
# Simular latencia alta (RTT elevado)
tc qdisc add dev eth1 root netem delay 200ms

# Simular pérdida de paquetes
tc qdisc add dev eth1 root netem loss 15%

# Combinar latencia + jitter + packet loss
tc qdisc add dev eth1 root netem delay 100ms 40ms loss 10%

# Verificar que se aplicó
tc qdisc show dev eth1

# Eliminar (revertir al estado normal)
tc qdisc del dev eth1 root
```

> Estos comandos se ejecutan en la **consola GNS3** del router (no por SSH), con `sudo su` si es necesario.

---

## Respuesta de la IA

La IA devuelve un JSON estructurado con:

```json
{
  "analysis": "Descripción del problema detectado",
  "severity": "low | medium | high | critical",
  "commands": ["set traffic-policy shaper ..."],
  "reasoning": "Explicación técnica de los comandos",
  "rollback_commands": ["delete interfaces ethernet eth1 traffic-policy"],
  "requires_human_approval": false
}
```

Si `requires_human_approval` es `true` o `AUTO_APPLY_AI_COMMANDS` es `False`, el sistema pregunta al operador antes de aplicar.

---

## Desafíos encontrados

- **Congestión en GNS3**: el principal obstáculo fue replicar condiciones reales de saturación. GNS3 emula los routers con recursos compartidos del host y los contadores de interfaz no reflejan congestión generada por tráfico externo. La solución fue usar `tc/netem` dentro del kernel de cada router para inyectar directamente latencia, jitter y pérdida de paquetes.
- **Parsing de salida VyOS**: la salida de comandos como `show interfaces detail` varía según la versión de VyOS; se ajustaron los regex para los formatos de las versiones usadas en GNS3.
- **Timeouts SSH**: los routers VyOS en GNS3 pueden tardar en responder; se añadió `global_delay_factor = 2` y `read_timeout = 30` en los comandos de ping.

---

## Créditos

Proyecto Final — Redes de Computadores  
Pontificia Universidad Católica del Ecuador
