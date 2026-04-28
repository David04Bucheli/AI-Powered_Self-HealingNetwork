# congestion_monitor.py
"""
Módulo de monitoreo de congestión para routers VyOS.
Recolecta métricas: RTT, packet loss, estadísticas de interfaces.
"""

import re
from dataclasses import dataclass
from typing import Optional
from netmiko import ConnectHandler


@dataclass
class InterfaceStats:
    """Estadísticas de una interfaz de red."""
    name: str
    rx_packets: int
    tx_packets: int
    rx_bytes: int
    tx_bytes: int
    rx_dropped: int
    tx_dropped: int
    rx_errors: int
    tx_errors: int


@dataclass
class PingResult:
    """Resultado de un ping a un destino."""
    destination: str
    packets_sent: int
    packets_received: int
    packet_loss_percent: float
    rtt_min: float      # ms
    rtt_avg: float      # ms
    rtt_max: float      # ms
    rtt_mdev: float     # ms (desviación estándar - indica jitter)


@dataclass 
class CongestionMetrics:
    """Métricas completas de congestión para un router."""
    router_ip: str
    interfaces: list[InterfaceStats]
    ping_results: list[PingResult]
    ospf_neighbors: int
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    
    def has_congestion_indicators(self) -> tuple[bool, list[str]]:
        """
        Analiza las métricas y determina si hay indicadores de congestión.
        Retorna (tiene_congestión, lista_de_razones).
        """
        issues = []
        
        # Verificar packet loss en pings
        for ping in self.ping_results:
            if ping.packet_loss_percent > 5:
                issues.append(
                    f"Alto packet loss ({ping.packet_loss_percent}%) hacia {ping.destination}"
                )
            # RTT alto (> 100ms indica posible congestión)
            if ping.rtt_avg > 100:
                issues.append(
                    f"RTT elevado ({ping.rtt_avg:.2f}ms) hacia {ping.destination}"
                )
            # Jitter alto (mdev > 50ms)
            if ping.rtt_mdev > 50:
                issues.append(
                    f"Alto jitter ({ping.rtt_mdev:.2f}ms) hacia {ping.destination}"
                )
        
        # Verificar drops en interfaces
        for iface in self.interfaces:
            total_dropped = iface.rx_dropped + iface.tx_dropped
            total_errors = iface.rx_errors + iface.tx_errors
            
            if total_dropped > 100:
                issues.append(
                    f"Paquetes dropped en {iface.name}: RX={iface.rx_dropped}, TX={iface.tx_dropped}"
                )
            if total_errors > 50:
                issues.append(
                    f"Errores en {iface.name}: RX={iface.rx_errors}, TX={iface.tx_errors}"
                )
        
        return len(issues) > 0, issues


def get_interface_stats(ssh_conn) -> list[InterfaceStats]:
    """
    Obtiene estadísticas de todas las interfaces ethernet.
    Usa 'show interfaces ethernet' en VyOS.
    """
    output = ssh_conn.send_command("show interfaces detail", expect_string=r"[\$#]")
    interfaces = []
    
    # Parsear salida de VyOS - formato típico:
    # eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
    #     RX:  bytes    packets     errors    dropped    overrun      mcast
    #          123456   1234        0         0          0            0
    #     TX:  bytes    packets     errors    dropped    carrier collisions
    #          654321   4321        0         0          0       0
    
    current_iface = None
    rx_line_next = False
    tx_line_next = False
    rx_data = {}
    tx_data = {}
    
    for line in output.splitlines():
        # Detectar nombre de interfaz
        iface_match = re.match(r'^(eth\d+):', line)
        if iface_match:
            # Guardar interfaz anterior si existe
            if current_iface and rx_data and tx_data:
                interfaces.append(InterfaceStats(
                    name=current_iface,
                    rx_packets=rx_data.get('packets', 0),
                    tx_packets=tx_data.get('packets', 0),
                    rx_bytes=rx_data.get('bytes', 0),
                    tx_bytes=tx_data.get('bytes', 0),
                    rx_dropped=rx_data.get('dropped', 0),
                    tx_dropped=tx_data.get('dropped', 0),
                    rx_errors=rx_data.get('errors', 0),
                    tx_errors=tx_data.get('errors', 0),
                ))
            current_iface = iface_match.group(1)
            rx_data = {}
            tx_data = {}
            continue
        
        # Detectar línea de encabezado RX/TX
        if 'RX:' in line and 'bytes' in line:
            rx_line_next = True
            continue
        if 'TX:' in line and 'bytes' in line:
            tx_line_next = True
            continue
        
        # Parsear datos RX
        if rx_line_next:
            numbers = re.findall(r'\d+', line)
            if len(numbers) >= 5:
                rx_data = {
                    'bytes': int(numbers[0]),
                    'packets': int(numbers[1]),
                    'errors': int(numbers[2]),
                    'dropped': int(numbers[3]),
                }
            rx_line_next = False
            continue
        
        # Parsear datos TX
        if tx_line_next:
            numbers = re.findall(r'\d+', line)
            if len(numbers) >= 5:
                tx_data = {
                    'bytes': int(numbers[0]),
                    'packets': int(numbers[1]),
                    'errors': int(numbers[2]),
                    'dropped': int(numbers[3]),
                }
            tx_line_next = False
            continue
    
    # No olvidar la última interfaz
    if current_iface and rx_data and tx_data:
        interfaces.append(InterfaceStats(
            name=current_iface,
            rx_packets=rx_data.get('packets', 0),
            tx_packets=tx_data.get('packets', 0),
            rx_bytes=rx_data.get('bytes', 0),
            tx_bytes=tx_data.get('bytes', 0),
            rx_dropped=rx_data.get('dropped', 0),
            tx_dropped=tx_data.get('dropped', 0),
            rx_errors=rx_data.get('errors', 0),
            tx_errors=tx_data.get('errors', 0),
        ))
    
    return interfaces


def ping_from_router(ssh_conn, destination: str, count: int = 10) -> Optional[PingResult]:
    """
    Ejecuta ping desde el router hacia un destino.
    count=10 para tener estadísticas significativas.
    """
    output = ssh_conn.send_command(
        f"ping {destination} count {count}",
        expect_string=r"[\$#]",
        read_timeout=30  # pings pueden tomar tiempo
    )
    
    # Parsear salida de ping en VyOS/Linux:
    # --- 10.0.12.1 ping statistics ---
    # 10 packets transmitted, 10 received, 0% packet loss, time 9012ms
    # rtt min/avg/max/mdev = 0.123/0.456/0.789/0.111 ms
    
    result = PingResult(
        destination=destination,
        packets_sent=count,
        packets_received=0,
        packet_loss_percent=100.0,
        rtt_min=0.0,
        rtt_avg=0.0,
        rtt_max=0.0,
        rtt_mdev=0.0,
    )
    
    for line in output.splitlines():
        # Buscar línea de packet loss
        loss_match = re.search(
            r'(\d+) packets transmitted, (\d+) received.*?(\d+(?:\.\d+)?)% packet loss',
            line
        )
        if loss_match:
            result.packets_sent = int(loss_match.group(1))
            result.packets_received = int(loss_match.group(2))
            result.packet_loss_percent = float(loss_match.group(3))
            continue
        
        # Buscar línea de RTT
        rtt_match = re.search(
            r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)',
            line
        )
        if rtt_match:
            result.rtt_min = float(rtt_match.group(1))
            result.rtt_avg = float(rtt_match.group(2))
            result.rtt_max = float(rtt_match.group(3))
            result.rtt_mdev = float(rtt_match.group(4))
    
    return result


def get_ospf_neighbor_count(ssh_conn) -> int:
    """Cuenta el número de vecinos OSPF activos."""
    output = ssh_conn.send_command("show ip ospf neighbor", expect_string=r"[\$#]")
    
    # Contar líneas que contengan estado "Full" (vecino completamente establecido)
    full_neighbors = len(re.findall(r'\bFull\b', output, re.IGNORECASE))
    return full_neighbors


def collect_congestion_metrics(device_params: dict, ping_targets: list[str]) -> CongestionMetrics:
    """
    Recolecta todas las métricas de congestión para un router.
    
    Args:
        device_params: Parámetros de conexión Netmiko
        ping_targets: Lista de IPs a las que hacer ping desde el router
    
    Returns:
        CongestionMetrics con toda la información recolectada
    """
    device_params['global_delay_factor'] = 2
    
    with ConnectHandler(**device_params) as ssh:
        ssh.find_prompt()
        
        # Recolectar estadísticas de interfaces
        interfaces = get_interface_stats(ssh)
        
        # Hacer pings a los destinos especificados
        ping_results = []
        for target in ping_targets:
            result = ping_from_router(ssh, target, count=10)
            if result:
                ping_results.append(result)
        
        # Contar vecinos OSPF
        ospf_neighbors = get_ospf_neighbor_count(ssh)
        
        return CongestionMetrics(
            router_ip=device_params['host'],
            interfaces=interfaces,
            ping_results=ping_results,
            ospf_neighbors=ospf_neighbors,
        )


def format_metrics_for_ai(metrics: CongestionMetrics) -> str:
    """
    Formatea las métricas en un string legible para enviar a la IA.
    """
    lines = [
        f"=== MÉTRICAS DE CONGESTIÓN - Router {metrics.router_ip} ===",
        f"Vecinos OSPF activos: {metrics.ospf_neighbors}",
        "",
        "--- ESTADÍSTICAS DE INTERFACES ---",
    ]
    
    for iface in metrics.interfaces:
        lines.extend([
            f"  {iface.name}:",
            f"    RX: {iface.rx_packets} pkts, {iface.rx_bytes} bytes, "
            f"dropped={iface.rx_dropped}, errors={iface.rx_errors}",
            f"    TX: {iface.tx_packets} pkts, {iface.tx_bytes} bytes, "
            f"dropped={iface.tx_dropped}, errors={iface.tx_errors}",
        ])
    
    lines.extend(["", "--- RESULTADOS DE PING ---"])
    
    for ping in metrics.ping_results:
        lines.extend([
            f"  Destino: {ping.destination}",
            f"    Enviados: {ping.packets_sent}, Recibidos: {ping.packets_received}, "
            f"Pérdida: {ping.packet_loss_percent}%",
            f"    RTT (ms): min={ping.rtt_min:.2f}, avg={ping.rtt_avg:.2f}, "
            f"max={ping.rtt_max:.2f}, mdev(jitter)={ping.rtt_mdev:.2f}",
        ])
    
    # Agregar análisis de problemas
    has_issues, issues = metrics.has_congestion_indicators()
    if has_issues:
        lines.extend(["", "--- PROBLEMAS DETECTADOS ---"])
        for issue in issues:
            lines.append(f"  ⚠️  {issue}")
    else:
        lines.extend(["", "--- ESTADO: Sin indicadores de congestión ---"])
    
    return "\n".join(lines)
