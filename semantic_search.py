"""
semantic_search.py — Buscador Semántico y RAG Local para Código y Documentación (Fase 16)
Utiliza barto-router (127.0.0.1:9000/v1) para:
1. Generar embeddings vectoriales con BGE-Small (GT 1030 en el nodo secundario).
2. Indexar archivos locales con caché persistente (embeddings_cache.json).
3. Realizar búsqueda semántica por similitud coseno (dot product).
4. Opcional: Responder preguntas usando el contexto recuperado (RAG con Qwen/Llama).
"""

import os
import sys
import json
import math
import time
import urllib.request
from typing import List, Dict, Tuple

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROUTER_EMBED_URL = "http://127.0.0.1:9000/v1/embeddings"
ROUTER_CHAT_URL = "http://127.0.0.1:9000/v1/chat/completions"
CACHE_FILE = "embeddings_cache.json"

def get_embedding(text: str) -> List[float]:
    """Obtiene el embedding vectorial de 384 dimensiones a través del router."""
    payload = {
        "model": "bge-small",
        "input": text.strip()
    }
    req = urllib.request.Request(
        ROUTER_EMBED_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["data"][0]["embedding"]

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calcula la similitud coseno entre dos vectores."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    return dot / (norm1 * norm2) if (norm1 and norm2) else 0.0

def chunk_file(filepath: str, max_chunk_chars: int = 450, overlap: int = 50) -> List[Dict]:
    """Divide un archivo en fragmentos (chunks) con solapamiento y número de línea."""
    chunks = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return chunks

    current_chunk = []
    current_chars = 0
    start_line = 1

    for idx, line in enumerate(lines, 1):
        line_len = len(line)
        if current_chars + line_len > max_chunk_chars and current_chunk:
            text = "".join(current_chunk).strip()
            if text:
                chunks.append({
                    "file": filepath,
                    "start_line": start_line,
                    "end_line": idx - 1,
                    "text": text
                })
            # Solapamiento básico
            overlap_lines = current_chunk[-2:] if len(current_chunk) >= 2 else []
            current_chunk = list(overlap_lines)
            current_chars = sum(len(l) for l in current_chunk)
            start_line = idx - len(overlap_lines)

        current_chunk.append(line)
        current_chars += line_len

    if current_chunk:
        text = "".join(current_chunk).strip()
        if text:
            chunks.append({
                "file": filepath,
                "start_line": start_line,
                "end_line": len(lines),
                "text": text
            })

    return chunks

class LocalRAGIndex:
    def __init__(self, cache_file: str = CACHE_FILE):
        self.cache_file = cache_file
        self.index = {}  # filepath: {"mtime": float, "chunks": [...]}
        self.load_cache()

    def load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.index = json.load(f)
            except Exception:
                self.index = {}

    def save_cache(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.index, f, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando caché: {e}")

    def build_index(self, directory: str, extensions=(".py", ".md", ".cs", ".txt")):
        """Indexa todos los archivos soportados en el directorio."""
        print(f"\n[Indexador] Escaneando '{directory}'...")
        files_to_process = []
        for root, _, files in os.walk(directory):
            if any(skip in root for skip in [".git", "__pycache__", "llama-win", "node_modules", "brain"]):
                continue
            for f in files:
                if any(f.endswith(ext) for ext in extensions):
                    files_to_process.append(os.path.join(root, f))

        total_embedded = 0
        t0 = time.time()
        for fpath in files_to_process:
            mtime = os.path.getmtime(fpath)
            cached = self.index.get(fpath)
            if cached and cached.get("mtime") == mtime:
                continue

            chunks = chunk_file(fpath)
            if not chunks:
                continue

            print(f"  -> Indexando: {os.path.basename(fpath)} ({len(chunks)} fragmentos)")
            for ch in chunks:
                ch["vector"] = get_embedding(ch["text"])
                total_embedded += 1

            self.index[fpath] = {
                "mtime": mtime,
                "chunks": chunks
            }

        self.save_cache()
        elapsed = time.time() - t0
        print(f"[Indexador] Listo. {total_embedded} nuevos fragmentos vectorizados en {elapsed:.2f}s.")

    def search(self, query: str, top_k: int = 3) -> List[Tuple[float, Dict]]:
        """Realiza búsqueda semántica y devuelve los top_k fragmentos más cercanos."""
        q_vec = get_embedding(query)
        scored = []

        for fpath, data in self.index.items():
            for ch in data.get("chunks", []):
                score = cosine_similarity(q_vec, ch.get("vector", []))
                scored.append((score, ch))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    def ask(self, question: str, top_k: int = 2, model: str = "qwen"):
        """Ejecuta un flujo RAG completo: Recupera contexto y sintetiza respuesta con el LLM."""
        print(f"\n🔍 Buscando contexto relevante para: \"{question}\"")
        results = self.search(question, top_k=top_k)

        if not results:
            print("No se encontró contexto relevante.")
            return

        print("\n--- Fragmentos de Código / Documentación Encontrados ---")
        context_parts = []
        for rank, (score, ch) in enumerate(results, 1):
            fname = os.path.basename(ch['file'])
            print(f"[{rank}] Similitud: {score*100:.1f}% | {fname} (Líneas {ch['start_line']}-{ch['end_line']})")
            context_parts.append(f"--- Documento: {fname} (Líneas {ch['start_line']}-{ch['end_line']}) ---\n{ch['text']}")

        context_text = "\n\n".join(context_parts)

        prompt = (
            f"Utiliza el siguiente contexto técnico recuperado para responder de forma precisa a la pregunta.\n\n"
            f"CONTEXTO:\n{context_text}\n\n"
            f"PREGUNTA:\n{question}\n\n"
            f"RESPUESTA:"
        )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Eres un asistente de arquitectura y desarrollo técnico. Sé conciso y fundamenta tu respuesta en el contexto proporcionado."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 160,
            "stream": True
        }

        req = urllib.request.Request(
            ROUTER_CHAT_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        print(f"\n🧠 [RAG - LLM {model.upper()}] Generando respuesta con contexto en streaming...")
        print("-" * 65)
        with urllib.request.urlopen(req, timeout=25) as resp:
            for line in resp:
                l_str = line.decode("utf-8").strip()
                if not l_str.startswith("data: "): continue
                d_str = l_str[6:].strip()
                if d_str == "[DONE]": break
                try:
                    c = json.loads(d_str)
                    token = c["choices"][0].get("delta", {}).get("content", "")
                    if token:
                        print(token, end="", flush=True)
                except Exception:
                    pass
        print("\n" + "-" * 65)

if __name__ == "__main__":
    rag = LocalRAGIndex()
    # Construir / actualizar índice del directorio de trabajo
    rag.build_index(directory=".")

    query = sys.argv[1] if len(sys.argv) > 1 else "¿Cómo funciona el filtro duro de VRAM y el factor de protección?"
    rag.ask(query, top_k=2, model="qwen")
