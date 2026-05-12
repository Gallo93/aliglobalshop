"""
Genera il sito statico leggendo i JSON in _data/ e i template in _templates/.
Output: en/ (prima lingua)
"""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "_data"
TEMPLATES_DIR = BASE_DIR / "_templates"
CONFIG_PATH = DATA_DIR / "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def main():
    config = load_config()
    print(f"Site URL: {config['site_url']}")
    print(f"Languages: {config['languages']}")
    # TODO: generazione pagine da template


if __name__ == "__main__":
    main()
