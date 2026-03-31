"""
Script de utilidad para verificar que las variables de entorno
se carguen correctamente desde el archivo .env.
"""
import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Check variables
variables = ["DATABASE_URL", "API_KEY", "WAF_EXPORT_URL", "SLACK_SIGNING_SECRET", "SLACK_BOT_TOKEN"]
results = {}

for var in variables:
    val = os.getenv(var)
    results[var] = val if val else "MISSING"

print("--- Environment Variables Check ---")
for var, val in results.items():
    print(f"{var}: {val}")
