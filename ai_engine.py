from openai import OpenAI

# Configura tu API Key de OpenAI
client = OpenAI(api_key="TU_API_KEY_AQUI")

def get_ai_remediation(telemetry_data):
    """Envía datos de congestión a la IA y recibe comandos de VyOS."""
    prompt = f"""
    Eres un experto en redes VyOS. Un router reporta congestión:
    {telemetry_data}
    
    Proporciona comandos 'set' de VyOS para mitigar esto (ej: QoS, limitación de ancho de banda). 
    Responde SOLO con los comandos, uno por línea, sin explicaciones.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o", # O gpt-3.5-turbo
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.choices[0].message.content.splitlines()
