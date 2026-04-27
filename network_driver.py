from netmiko import ConnectHandler
import subprocess
import re

def get_vyos_config(device_params):
    """Obtiene la configuración con manejo de errores de terminal."""
    # parametros de los vyos
    device_params['global_delay_factor'] = 2        # esperar a que cargue vyos
    
    with ConnectHandler(**device_params) as ssh:
        ssh.find_prompt()       # prepara terminal
        return ssh.send_command("show configuration commands", expect_string=r"[\$#]")

def apply_repair(device_params, commands):
    """Aplica reparación con manejo de prompts de VyOS."""
    device_params['global_delay_factor'] = 2
    with ConnectHandler(**device_params) as ssh:
        ssh.find_prompt()

        # modo confgure
        ssh.send_config_set(commands)
        ssh.send_command("commit")
        return ssh.send_command("save")

def get_vyos_stats(device_params):
    """
    Extrae telemetría física de las interfaces (paquetes, errores, drops).
    """
    device_params['global_delay_factor'] = 5    # esperar a que cargue vyos
    with ConnectHandler(**device_params) as ssh:
        ssh.find_prompt()
        return ssh.send_command("show interfaces ethernet detail")      # errores y estadisticas de tráfico

def apply_ai_commands(device_params, commands):
    """
    Aplica comandos sugeridos por la IA.
    """
    device_params['global_delay_factor'] = 5        # esperar a que cargue vyos
    with ConnectHandler(**device_params) as ssh:
        ssh.find_prompt()
        ssh.send_config_set(commands)
        ssh.send_command("commit")
        return True
    
def get_network_latency(ip):
    """Mide el RTT promedio hacia un dispositivo."""
    try:
        # 3 pings para el promedio
        count_param = '-n' if subprocess.os.name == 'nt' else '-c'
        output = subprocess.check_output(['ping', count_param, '3', ip], 
                                         stderr=subprocess.STDOUT, 
                                         universal_newlines=True)
        
        # valor promedio del RTT
        search_rtt = re.search(r"Average = (\d+)ms" if subprocess.os.name == 'nt' 
                               else r"min/avg/max/mdev = [\d\.]+/([\d\.]+)/", output)
        
        if search_rtt:
            return float(search_rtt.group(1))
        return 0
    except Exception:
        return 999      # fallo de ping