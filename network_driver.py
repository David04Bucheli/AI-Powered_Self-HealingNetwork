from netmiko import ConnectHandler

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
