# devices.py
r1 = {
    'device_type': 'vyos',
    'host': '192.168.1.1',
    'username': 'admin',
    'password': 'vyos',
}

r2 = {
    'device_type': 'vyos',
    'host': '10.0.12.2', # IP del enlace R1-R2
    'username': 'admin',
    'password': 'vyos',
}

r3 = {
    'device_type': 'vyos',
    'host': '10.0.13.3', # IP del enlace R1-R3
    'username': 'admin',
    'password': 'vyos',
}

# Lista maestra que recorrerá el script de monitoreo
all_devices = [r1, r2, r3]
