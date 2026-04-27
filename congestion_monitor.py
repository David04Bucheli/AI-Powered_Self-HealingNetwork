# congestion_monitor.py
# Recolecta métricas de congestión de routers VyOS vía Netmiko
# Métricas elegidas por visibilidad en GNS3: interface counters, OSPF neighbors, queue drops

import re
from netmiko import ConnectHandler

# ── Umbrales configurables ──────────────────────────────────────────────────
THRESHOLDS = {
    'rx_errors_pct':   1.0,   # % de errores sobre paquetes totales
    'tx_drops_pct':    1.0,   # % de drops sobre paquetes totales
    'ospf_retx':       5,     # retransmisiones OSPF acumuladas (señal de saturación L3)
    'load_pct':        70.0,  # % de utilización de interfaz (si hay rate disponible)
}

# ── Parsers VyOS ─────────────────────────────────────────────────────────────

def _parse_interface_stats(raw: str) -> list[dict]:
    """
    Parsea la salida de 'show interfaces' de VyOS.
    Extrae: interfaz, estado, rx_packets, tx_packets, rx_errors, tx_drops.
    """
    results = []
    # Bloque por interfaz: línea con nombre + líneas de estadísticas
    iface_blocks = re.split(r'\n(?=\S)', raw)

    for block in iface_blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue

        # Primera línea: nombre de interfaz y estado
        header = lines[0]
        m_name = re.match(r'^(\S+)', header)
        if not m_name:
            continue
        iface = m_name.group(1)

        state = 'unknown'
        if 'state UP' in header or 'up' in header.lower():
            state = 'up'
        elif 'state DOWN' in header or 'down' in header.lower():
            state = 'down'

        # Buscar contadores dentro del bloque
        rx_packets = tx_packets = rx_errors = tx_drops = 0

        for line in lines:
            m = re.search(r'RX\s+packets[:\s]+(\d+)', line, re.IGNORECASE)
            if m: rx_packets = int(m.group(1))

            m = re.search(r'TX\s+packets[:\s]+(\d+)', line, re.IGNORECASE)
            if m: tx_packets = int(m.group(1))

            m = re.search(r'RX.*?errors[:\s]+(\d+)', line, re.IGNORECASE)
            if m: rx_errors = int(m.group(1))

            m = re.search(r'TX.*?dropped[:\s]+(\d+)', line, re.IGNORECASE)
            if m: tx_drops = int(m.group(1))

        results.append({
            'interface': iface,
            'state':     state,
            'rx_packets': rx_packets,
            'tx_packets': tx_packets,
            'rx_errors':  rx_errors,
            'tx_drops':   tx_drops,
        })

    return results


def _parse_ospf_stats(raw: str) -> dict:
    """
    Parsea 'show ip ospf neighbor' para contar vecinos y detectar
    estados problemáticos (Init, Exstart, Exchange — señal de inestabilidad).
    """
    neighbors = []
    retx_total = 0

    for line in raw.splitlines():
        # Línea típica: 10.0.12.1  1  Full/DR  00:00:35  10.0.12.1  eth1
        m = re.match(
            r'(\d+\.\d+\.\d+\.\d+)\s+\d+\s+(\S+)\s+\S+\s+\S+\s+(\S+)',
            line.strip()
        )
        if m:
            ip, state, iface = m.group(1), m.group(2), m.group(3)
            neighbors.append({'neighbor': ip, 'state': state, 'iface': iface})
            if state.lower() not in ('full', 'full/dr', 'full/bdr'):
                retx_total += 1     # estado no-Full = inestabilidad / retransmisiones

    return {
        'neighbor_count': len(neighbors),
        'neighbors':      neighbors,
        'unstable_count': retx_total,
    }


def _parse_queue_stats(raw: str) -> dict:
    """
    Parsea 'show queueing' si está disponible.
    En VyOS básico extrae dropped packets como proxy de congestión de cola.
    """
    total_drops = 0
    m = re.findall(r'dropped\s+(\d+)', raw, re.IGNORECASE)
    for val in m:
        total_drops += int(val)
    return {'queue_drops': total_drops}


# ── Función principal ─────────────────────────────────────────────────────────

def collect_metrics(device_params: dict) -> dict:
    """
    Conecta al router y recolecta métricas de congestión.
    Retorna un dict con todas las métricas y una lista de anomalías detectadas.
    """
    params = dict(device_params)
    params['global_delay_factor'] = 2

    ip = params['host']
    metrics = {'host': ip, 'interfaces': [], 'ospf': {}, 'queue': {}, 'anomalies': []}

    with ConnectHandler(**params) as ssh:
        ssh.find_prompt()

        # 1. Estadísticas de interfaces
        raw_ifaces = ssh.send_command('show interfaces', expect_string=r'[\$#]')
        metrics['interfaces'] = _parse_interface_stats(raw_ifaces)

        # 2. Estado OSPF
        raw_ospf = ssh.send_command('show ip ospf neighbor', expect_string=r'[\$#]')
        metrics['ospf'] = _parse_ospf_stats(raw_ospf)

        # 3. Colas (best-effort en VyOS básico)
        try:
            raw_q = ssh.send_command('show queueing', expect_string=r'[\$#]')
            metrics['queue'] = _parse_queue_stats(raw_q)
        except Exception:
            metrics['queue'] = {'queue_drops': 0}

    # ── Detección de anomalías ────────────────────────────────────────────────
    anomalies = []

    for iface in metrics['interfaces']:
        name = iface['interface']

        # Saltar loopback y interfaces down
        if 'lo' in name or iface['state'] == 'down':
            continue

        total_rx = iface['rx_packets'] or 1
        total_tx = iface['tx_packets'] or 1

        rx_err_pct = (iface['rx_errors'] / total_rx) * 100
        tx_drop_pct = (iface['tx_drops'] / total_tx) * 100

        if rx_err_pct >= THRESHOLDS['rx_errors_pct']:
            anomalies.append({
                'type':      'RX_ERRORS',
                'interface': name,
                'value':     round(rx_err_pct, 2),
                'threshold': THRESHOLDS['rx_errors_pct'],
                'unit':      '%',
                'detail':    f"{iface['rx_errors']} errores sobre {total_rx} paquetes RX"
            })

        if tx_drop_pct >= THRESHOLDS['tx_drops_pct']:
            anomalies.append({
                'type':      'TX_DROPS',
                'interface': name,
                'value':     round(tx_drop_pct, 2),
                'threshold': THRESHOLDS['tx_drops_pct'],
                'unit':      '%',
                'detail':    f"{iface['tx_drops']} drops sobre {total_tx} paquetes TX"
            })

    if metrics['ospf'].get('unstable_count', 0) >= THRESHOLDS['ospf_retx']:
        anomalies.append({
            'type':      'OSPF_INSTABILITY',
            'interface': 'N/A',
            'value':     metrics['ospf']['unstable_count'],
            'threshold': THRESHOLDS['ospf_retx'],
            'unit':      'vecinos no-Full',
            'detail':    f"Vecinos OSPF en estado no-Full: {metrics['ospf']['unstable_count']}"
        })

    if metrics['queue'].get('queue_drops', 0) > 0:
        anomalies.append({
            'type':      'QUEUE_DROPS',
            'interface': 'N/A',
            'value':     metrics['queue']['queue_drops'],
            'threshold': 0,
            'unit':      'paquetes',
            'detail':    f"Drops acumulados en colas: {metrics['queue']['queue_drops']}"
        })

    metrics['anomalies'] = anomalies
    return metrics
