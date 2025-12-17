"""
Skrypt do pobierania zawartości strony internetowej z przedmiotami.
Pobiera dane dla rund 1-80.
Użycie: python load_dataset.py
"""

import requests
from pathlib import Path
import time
import urllib3

# Wyłącz ostrzeżenia o niezweryfikowanym SSL (dla dev środowiska)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Hardcodowany base URL (zmień na właściwy)
BASE_URL = "https://dev.vabank.fintech.allegrogroup.com/funai/Tournaments/Auction?auctionId=2901730337263073280"

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


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    output_dir = script_dir / "downloaded_pages"
    output_dir.mkdir(exist_ok=True)
    
    print(f"Pobieranie danych z {START_ROUND} do {END_ROUND} rundy")
    print(f"Katalog wyjściowy: {output_dir}\n")
    
    success_count = 0
    failed_count = 0
    
    for round_num in range(START_ROUND, END_ROUND + 1):
        if fetch_round(BASE_URL, round_num, output_dir):
            success_count += 1
        else:
            failed_count += 1
        
        # Krótka przerwa między requestami (żeby nie obciążać serwera)
        if round_num < END_ROUND:
            time.sleep(2)
    
    print(f"\n{'='*50}")
    print(f"Pobrano: {success_count}/{END_ROUND} rund")
    if failed_count > 0:
        print(f"Błędy: {failed_count}")
    print(f"Pliki zapisane w: {output_dir}")
