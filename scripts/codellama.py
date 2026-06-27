#!/usr/bin/env python3
"""Quick interface to local CodeLlama via Ollama."""
import json
import sys
import urllib.request


def ask(prompt: str, model: str = "codellama:13b-instruct") -> str:
    data = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["response"]


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
    print(ask(prompt))
