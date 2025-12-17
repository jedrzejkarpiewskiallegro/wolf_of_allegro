"""
Skrypt do pobierania zawartości strony internetowej z przedmiotami.
Pobiera dane dla rund 1-80.
Użycie: python load_dataset.py
"""

import requests
from pathlib import Path
import time
import urllib3
import re
import json

# Wyłącz ostrzeżenia o niezweryfikowanym SSL (dla dev środowiska)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Hardcodowany base URL (zmień na właściwy)
BASE_URL = "https://dev.vabank.fintech.allegrogroup.com/funai/Tournaments/Auction?auctionId=2901549079106932736"

# Zakres rund do pobrania
START_ROUND = 1
END_ROUND = 80


def fetch_round(base_url: str, round_number: int, output_dir: Path):
    """
    Pobiera zawartość strony dla danej rundy.
    
    Args:
        base_url: Bazowy URL (bez suffixu z rundą)
        round_number: Numer rundy
        output_dir: Folder docelowy
    """
    url = f"{base_url}&roundNumber={round_number}"
    output_file = output_dir / f"webpage_round_{round_number}.html"
    
    print(f"[Runda {round_number:2d}] Pobieranie z: {url}")
    
    try:
        response = requests.get(url, timeout=30, verify=False)
        response.raise_for_status()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        print(f"[Runda {round_number:2d}] ✓ Zapisano ({len(response.text)} znaków)")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"[Runda {round_number:2d}] ✗ Błąd: {e}")
        return False


def parse_item_from_html(html_file: Path) -> dict | None:
    """
    Parsuje plik HTML i wyciąga dane przedmiotu z linii 556.
    
    Args:
        html_file: Ścieżka do pliku HTML
        
    Returns:
        Słownik z Name, Quality, IsRequired lub None jeśli parsowanie się nie powiodło
    """
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Linia 556 (indeks 555 bo 0-based)
        if len(lines) < 556:
            print(f"⚠ {html_file.name}: Za mało linii ({len(lines)})")
            return None
        
        line = lines[555]
        
        # Wyciągnij nazwę: <span id="round-item-name">Nazwa</span>
        name_match = re.search(r'<span id="round-item-name">([^<]+)</span>', line)
        
        # Wyciągnij quality: <span id="round-item-quality">88</span>
        quality_match = re.search(r'<span id="round-item-quality">(\d+)</span>', line)
        
        # Sprawdź czy jest "(required)": <span id="round-item-required"> (required)</span>
        is_required = '(required)' in line
        
        if not name_match or not quality_match:
            print(f"⚠ {html_file.name}: Nie znaleziono danych w linii 556")
            return None
        
        return {
            "Name": name_match.group(1),
            "Quality": int(quality_match.group(1)),
            "IsRequired": is_required
        }
        
    except Exception as e:
        print(f"✗ {html_file.name}: Błąd parsowania: {e}")
        return None


def extract_all_items(downloaded_dir: Path, output_dir: Path):
    """
    Parsuje wszystkie pobrane HTML-e i tworzy JSON z przedmiotami.
    
    Args:
        downloaded_dir: Folder z pobranymi HTML-ami
        output_dir: Folder docelowy dla JSON
    """
    print(f"\n{'='*50}")
    print("Parsowanie pobranych plików...")
    
    all_items = []
    
    for round_num in range(START_ROUND, END_ROUND + 1):
        html_file = downloaded_dir / f"webpage_round_{round_num}.html"
        
        if not html_file.exists():
            print(f"⚠ Brak pliku: {html_file.name}")
            continue
        
        item = parse_item_from_html(html_file)
        if item:
            all_items.append(item)
            print(f"[Runda {round_num:2d}] ✓ {item['Name']} (Q:{item['Quality']}, Req:{item['IsRequired']})")
    
    # Zapisz do JSON
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "all_items.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({"all_items": all_items}, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*50}")
    print(f"✓ Wyeksportowano {len(all_items)} przedmiotów")
    print(f"Plik: {output_file}")


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    output_dir = script_dir / "downloaded_pages"
    output_dir.mkdir(exist_ok=True)
    
    print(f"Pobieranie danych z {START_ROUND} do {END_ROUND} rundy")
    print(f"Katalog wyjściowy: {output_dir}\n")
    
    success_count = 0
    failed_count = 0
    
    # Odkomentuj żeby pobrać pliki:
    for round_num in range(START_ROUND, END_ROUND + 1):
        if fetch_round(BASE_URL, round_num, output_dir):
            success_count += 1
        else:
            failed_count += 1
        
        # Krótka przerwa między requestami (żeby nie obciążać serwera)
        if round_num < END_ROUND:
            time.sleep(1)
    
    print(f"\n{'='*50}")
    print(f"Pobrano: {success_count}/{END_ROUND} rund")
    if failed_count > 0:
        print(f"Błędy: {failed_count}")
    print(f"Pliki zapisane w: {output_dir}")
    
    # Parsuj pobrane pliki i stwórz JSON
    json_output_dir = script_dir / "parsed_items"
    extract_all_items(output_dir, json_output_dir)
