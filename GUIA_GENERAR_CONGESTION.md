# Guía: Cómo Generar Congestión en GNS3 para Testing

## Métricas que el Sistema Monitorea

| Métrica | Umbral Normal | Congestión Moderada | Congestión Severa |
|---------|---------------|---------------------|-------------------|
| Packet Loss | < 5% | 5-20% | > 20% |
| RTT (latencia) | < 50ms | 50-100ms | > 55ms |
| Jitter (mdev) | < 20ms | 20-50ms | > 25ms |
| Dropped packets | < 100 | 100-500 | > 500 |

---

**Para quitar:**
```bash
# Entrar como root
sudo su

# Eliminar
tc qdisc del dev eth1 root

# Verificar
tc qdisc show dev eth1

```

## Traffic Control en VyOS

### Simular Latencia Alta (RTT elevado)

Desde la consola de VyOS (no SSH), ejecuta:

```bash
# Agregar 200ms de latencia a eth1 (enlace R1-R2)
tc qdisc add dev eth1 root netem delay 200ms

### Simular Packet Loss
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