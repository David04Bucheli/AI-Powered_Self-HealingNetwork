# network_driver.py
from netmiko import ConnectHandler

def get_vyos_config(device_params):
    """Obtiene la configuración actual en formato de comandos 'set'."""
    with ConnectHandler(**device_params) as ssh:
        # VyOS requiere este comando específico para auditoría de cambios
        return ssh.send_command("show configuration commands")

def apply_repair(device_params, commands):
    """Ingresa al modo configuración y restaura los comandos faltantes."""
    with ConnectHandler(**device_params) as ssh:
        ssh.send_config_set(commands)
        ssh.send_command("commit")
        return ssh.send_command("save")
