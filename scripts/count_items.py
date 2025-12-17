"""
Skrypt do analizy setów przedmiotów z folderu parsed_items.
Podsumowuje ile czego jest w każdym secie.
"""

import json
from pathlib import Path
from collections import Counter


def analyze_item_set(json_file: Path):
    """
    Analizuje pojedynczy plik JSON z przedmiotami.
    
    Args:
        json_file: Ścieżka do pliku JSON
    """
    print(f"\n{'='*60}")
    print(f"📦 SET: {json_file.stem}")
    print(f"{'='*60}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    items = data.get("all_items", [])
    
    if not items:
        print("⚠ Brak przedmiotów w secie")
        return
    
    # Zlicz przedmioty po nazwie
    item_counts = Counter(item["Name"] for item in items)
    
    # Podziel na required i optional
    required_items = [item for item in items if item.get("IsRequired", False)]
    optional_items = [item for item in items if not item.get("IsRequired", False)]
    
    required_counts = Counter(item["Name"] for item in required_items)
    optional_counts = Counter(item["Name"] for item in optional_items)
    
    # Statystyki ogólne
    print(f"\n📊 STATYSTYKI OGÓLNE:")
    print(f"   Wszystkich przedmiotów: {len(items)}")
    print(f"   Required: {len(required_items)}")
    print(f"   Optional: {len(optional_items)}")
    print(f"   Unikalnych nazw: {len(item_counts)}")
    
    # Required items
    if required_counts:
        print(f"\n✅ REQUIRED ITEMS ({len(required_items)} total):")
        for name, count in required_counts.most_common():
            qualities = [item["Quality"] for item in items if item["Name"] == name and item.get("IsRequired")]
            avg_quality = sum(qualities) / len(qualities)
            min_q, max_q = min(qualities), max(qualities)
            print(f"   {count:2d}x {name}")
            print(f"       Quality: avg={avg_quality:.1f}, min={min_q}, max={max_q}")
    
    # Optional items
    if optional_counts:
        print(f"\n❌ OPTIONAL ITEMS ({len(optional_items)} total):")
        for name, count in optional_counts.most_common():
            qualities = [item["Quality"] for item in items if item["Name"] == name and not item.get("IsRequired")]
            avg_quality = sum(qualities) / len(qualities)
            min_q, max_q = min(qualities), max(qualities)
            print(f"   {count:2d}x {name}")
            print(f"       Quality: avg={avg_quality:.1f}, min={min_q}, max={max_q}")


def analyze_all_sets(parsed_items_dir: Path):
    """
    Analizuje wszystkie sety JSON z folderu parsed_items.
    
    Args:
        parsed_items_dir: Folder z plikami JSON
    """
    json_files = list(parsed_items_dir.glob("*.json"))
    
    if not json_files:
        print(f"❌ Brak plików JSON w {parsed_items_dir}")
        return
    
    print(f"Znaleziono {len(json_files)} setów do analizy")
    
    for json_file in sorted(json_files):
        analyze_item_set(json_file)
    
    print(f"\n{'='*60}")
    print(f"✓ Przeanalizowano {len(json_files)} setów")
    print(f"{'='*60}")


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    parsed_items_dir = script_dir / "parsed_items"
    
    if not parsed_items_dir.exists():
        print(f"❌ Folder {parsed_items_dir} nie istnieje!")
        print("Najpierw uruchom load_dataset.py żeby sparsować dane")
        exit(1)
    
    analyze_all_sets(parsed_items_dir)
