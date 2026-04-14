from netmiko import ConnectHandler

def get_vyos_config(device_params):
    """Obtiene la configuración con manejo de errores de terminal."""
    # Añadimos parámetros globales de manejo de sesión
    device_params['global_delay_factor'] = 2  # Da más tiempo de respuesta
    
    with ConnectHandler(**device_params) as ssh:
        # Forzamos a Netmiko a encontrar el prompt sin importar caracteres especiales
        ssh.find_prompt()
        # VyOS a veces necesita 'set terminal length 0' para no pausar el texto largo
        return ssh.send_command("show configuration commands", expect_string=r"[\$#]")

def apply_repair(device_params, commands):
    """Aplica reparación con manejo de prompts de VyOS."""
    device_params['global_delay_factor'] = 2
    with ConnectHandler(**device_params) as ssh:
        ssh.find_prompt()
        # VyOS requiere entrar a modo configuración específicamente
        ssh.send_config_set(commands)
        ssh.send_command("commit")
        return ssh.send_command("save")
