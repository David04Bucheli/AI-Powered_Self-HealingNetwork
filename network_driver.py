from netmiko import ConnectHandler

def get_running_config(device_params):
    """Se conecta al router y extrae la configuración actual."""
    with ConnectHandler(**device_params) as ssh:
        return ssh.send_command("show running-config")

def apply_remediation(device_params, config_commands):
    """Aplica los comandos necesarios para reparar el router."""
    with ConnectHandler(**device_params) as ssh:
        return ssh.send_config_set(config_commands)
