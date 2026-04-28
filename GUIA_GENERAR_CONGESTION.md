# Guía: Cómo Generar Congestión en GNS3 para Testing

## Métricas que el Sistema Monitorea

| Métrica | Umbral Normal | Congestión Moderada | Congestión Severa |
|---------|---------------|---------------------|-------------------|
| Packet Loss | < 5% | 5-20% | > 20% |
| RTT (latencia) | < 50ms | 50-100ms | > 100ms |
| Jitter (mdev) | < 20ms | 20-50ms | > 50ms |
| Dropped packets | < 100 | 100-500 | > 500 |

---

## Método 1: Traffic Control en VyOS (Recomendado)

### Simular Latencia Alta (RTT elevado)

Desde la consola de VyOS (no SSH), ejecuta:

```bash
# Entrar como root
sudo su

# Agregar 200ms de latencia a eth1 (enlace R1-R2)
tc qdisc add dev eth1 root netem delay 200ms

# Verificar
tc qdisc show dev eth1
```

**Para quitar:**
```bash
tc qdisc del dev eth1 root
```

### Simular Packet Loss

```bash
# Agregar 15% de packet loss a eth1
tc qdisc add dev eth1 root netem loss 15%

# Combinar latencia + loss
tc qdisc add dev eth1 root netem delay 100ms loss 10%
```

### Simular Jitter (Variación de latencia)

```bash
# Latencia de 50ms con variación de ±40ms (genera alto jitter)
tc qdisc add dev eth1 root netem delay 50ms 40ms
```

### Simular Congestión con Cola Limitada

```bash
# Limitar cola a solo 10 paquetes (causa drops rápidamente)
tc qdisc add dev eth1 root netem limit 10
```

---

## Método 2: Flood de Paquetes desde VPC (VPCS en GNS3)

Desde una VPC de GNS3, puedes generar tráfico:

```bash
# Ping flood (envía muchos paquetes ICMP)
# Desde VPC1 hacia VPC2
ping 192.168.2.100 -c 1000 -i 0.01

# -c 1000 = 1000 paquetes
# -i 0.01 = intervalo de 10ms entre paquetes
```

**Nota:** Las VPCs de GNS3 son limitadas. Para flood real, necesitarías Linux VMs.

---

## Método 3: Limitar Ancho de Banda con tc

```bash
# Limitar eth1 a solo 100kbit/s (muy lento)
tc qdisc add dev eth1 root tbf rate 100kbit burst 10kb latency 50ms
```

---

## Método 4: Generar Tráfico con hping3 (si está disponible)

Desde una VM Linux conectada a la red:

```bash
# Flood de SYN (genera mucho tráfico)
hping3 -S --flood -p 80 192.168.2.1

# Flood ICMP
hping3 --icmp --flood 192.168.2.1
```

---

## Método 5: Iperf para Saturar Enlaces

Si tienes iperf instalado en los routers o VMs:

**En el servidor (destino):**
```bash
iperf -s
```

**En el cliente (origen):**
```bash
# Genera tráfico UDP a 10Mbit/s por 60 segundos
iperf -c 192.168.2.1 -u -b 10M -t 60
```

---

## Escenario de Testing Recomendado

### Paso 1: Configurar congestión en R2

```bash
# Conectar a R2 via consola GNS3 (no SSH)
sudo su
tc qdisc add dev eth1 root netem delay 150ms loss 10%
```

### Paso 2: Ejecutar el sistema de monitoreo

```bash
# En tu máquina con Python
export OPENAI_API_KEY="tu-api-key"
python main_with_ai.py --test
```

### Paso 3: Observar las métricas

Deberías ver:
- RTT elevado (~150ms + latencia base)
- Packet loss ~10%
- La IA debería recomendar ajustar costos OSPF o aplicar traffic shaping

### Paso 4: Quitar la congestión simulada

```bash
tc qdisc del dev eth1 root
```

---

## Comandos Útiles para Diagnóstico

### En VyOS:
```bash
# Ver estadísticas de interfaces
show interfaces ethernet

# Ver tabla OSPF
show ip ospf neighbor

# Ver rutas
show ip route

# Ping con estadísticas
ping 10.0.12.2 count 20
```

### En Linux/tu máquina:
```bash
# Ver qdisc activos
tc qdisc show

# Monitorear interfaces en tiempo real
watch -n 1 'cat /proc/net/dev'
```

---

## Troubleshooting

### "tc: command not found"
VyOS debería tener tc instalado. Si no:
```bash
sudo apt-get update && sudo apt-get install iproute2
```

### El router deja de responder
- Reduce la severidad: usa `delay 50ms loss 5%` en lugar de valores extremos
- Asegúrate de NO aplicar tc a la interfaz de gestión (la que usas para SSH)

### Las métricas no cambian
- Verifica que tc está aplicado a la interfaz correcta
- Espera un ciclo completo (60 segundos default)
- Revisa con `tc qdisc show`

---

## Ejemplo de Output Esperado

Cuando hay congestión, deberías ver algo como:

```
[ALERT] ⚠️  Indicadores de congestión detectados en 10.0.12.2:
    • Alto packet loss (12.5%) hacia 192.168.1.1
    • RTT elevado (156.32ms) hacia 192.168.1.1
    • Alto jitter (45.67ms) hacia 192.168.1.1

[*] 🤖 Consultando IA para recomendaciones...

============================================================
🤖 ANÁLISIS DE IA - Router 10.0.12.2
============================================================

🟠 Severidad: HIGH

📊 Análisis:
   Se detecta congestión significativa en el enlace eth1...

💡 Razonamiento:
   Dado el alto RTT y packet loss, se recomienda redistribuir
   tráfico aumentando el costo OSPF del enlace afectado...

🔧 Comandos de mitigación:
   • set interfaces ethernet eth1 ip ospf cost 100
   • set traffic-policy shaper LIMIT_ETH1 bandwidth 5mbit
   • set interfaces ethernet eth1 traffic-policy out LIMIT_ETH1
```
