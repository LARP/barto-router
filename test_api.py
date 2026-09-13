import urllib.request
import json
import sys

url = "http://192.168.100.105:8080/v1/chat/completions"
data = {
    "model": "/data/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
    "messages": [
        {"role": "system", "content": "Eres un asistente util."},
        {"role": "user", "content": "Saluda al usuario indicando que el servidor de IA local esta 100% operativo."}
    ],
    "max_tokens": 60,
    "temperature": 0.7
}

req = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print("RESPUESTA MODELO:")
        print(res["choices"][0]["message"]["content"])
        print("\nMETRICAS DE USO:")
        print(json.dumps(res.get("usage", {}), indent=2))
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
