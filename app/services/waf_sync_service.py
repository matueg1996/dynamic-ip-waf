import requests

API_URL = "http://api:8000/export"
API_KEY = "mi-api-key"

def sync_waf():
    headers = {"x-api-key": API_KEY}

    response = requests.get(API_URL, headers=headers)
    data = response.json()

    for ambiente, listas in data.items():
        allowlist = listas["allowlist"]
        blocklist = listas["blocklist"]

        print(f"[SYNC] {ambiente}")
        print(f"Allow: {allowlist}")
        print(f"Block: {blocklist}")

        actualizar_waf(ambiente, allowlist, blocklist)


def actualizar_waf(ambiente, allowlist, blocklist):
    """
    Overwrite completo del estado en el WAF.
    """

    print(f"[WAF UPDATE] {ambiente} actualizado")