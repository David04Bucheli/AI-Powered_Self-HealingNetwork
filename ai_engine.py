from openai import OpenAI

# Configura tu API Key de OpenAI
client = OpenAI(
    api_key="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",
    base_url="https://api.openai.com/v1"
)

def get_ai_remediation(telemetry_data):
    """Envía datos de congestión a la IA y recibe comandos de VyOS."""
    prompt = f"""
    Eres un experto en redes VyOS. Un router reporta congestión:
    {telemetry_data}
    
    Proporciona comandos 'set' de VyOS para mitigar esto (ej: QoS, limitación de ancho de banda). 
    Responde SOLO con los comandos, uno por línea, sin explicaciones.
    """
    
<<<<<<< HEAD
    response = client.chat.completions.create(
        model="llama-3.3-70b-instruct",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.choices[0].message.content.splitlines()
=======
    try:
        # El error 404 suele ocurrir aquí por el nombre del 'model'
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Cambia a "gpt-4" si tienes acceso, pero 3.5 es más seguro para evitar 404
            messages=[
                {"role": "system", "content": "Eres un asistente técnico de redes VyOS."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        return response.choices[0].message.content.splitlines()
    except Exception as e:
        # Esto te dirá exactamente qué falló si no es el 404
        print(f"[AI ERROR] Detalle: {e}")
        return []
>>>>>>> 028fc9f26b0cc5edff77fee6c0fac077261711ce
