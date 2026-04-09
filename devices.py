# devices.py
router_r1 = {
    'device_type': 'cisco_ios',
    'host': '192.168.1.10',  # La IP que le diste en GNS3
    'username': 'admin',
    'password': 'password123',
    'secret': 'admin_secret', # Si usas enable password
}

# Puedes crear una lista para que el script recorra varios equipos
all_devices = [router_r1]
