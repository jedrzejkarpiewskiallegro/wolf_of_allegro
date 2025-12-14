Specyfikacja Techniczna Symulatora "The Agent Auction Game"

1. Cel Projektu

Stworzenie lokalnego symulatora gry aukcyjnej w języku Python. System ma wczytywać prompty (strategie agentów) z plików tekstowych, symulować rozgrywkę turową z wykorzystaniem lokalnego modelu LLM (np. przez Ollama/OpenAI API) i zapisywać szczegółowe logi do analizy w Jupyter Notebook.

2. Architektura Systemu

System powinien składać się z następujących modułów/klas:

A. Konfiguracja i Pliki

Katalog prompts/: Zawiera pliki .txt. Każdy plik to osobny zespół.

Przykład: team_alpha.txt, team_beta.txt.

Nazwa pliku (bez rozszerzenia) staje się TeamName.

Katalog items/: Zawiera pliki .json z definicjami zestawów przedmiotów (all_items).

Każdy plik to osobny scenariusz rynkowy (np. standard_game.json, high_scarcity.json, many_duplicates.json).

Pozwala na powtarzalne testy na tych samych danych.

Model LLM: Abstrakcyjna warstwa do komunikacji z modelem (np. funkcja generate_bid(prompt, system_context_prompt, user_message)).

B. Główne Klasy

1. Item (Dataclass)

Reprezentuje przedmiot licytacji.

name: str (np. "The Visionary Compass")

quality: int (1-100, losowane przy generowaniu rundy)

is_required: bool (czy należy do zestawu "Principal Blaster")

2. Team (Class)

Reprezentuje stan pojedynczego agenta.

name: str (z nazwy pliku promptu)

system_prompt: str (treść pliku - strategia agenta)

budget: int (startowo np. 1000 lub 2000 - konfigurowalne)

inventory: List[Item] (zdobyte przedmioty)

knowledge_base: List[dict] (pole przechowujące all_items po inicjalizacji)

Metoda initialize(all_items): Zapisuje listę wszystkich przedmiotów w pamięci agenta (cache).

Metoda get_bid(game_state): Buduje zapytanie do LLM zawierające system_prompt oraz game_state, parsuje odpowiedź i zwraca int.

3. AuctionEngine (Class)

Zarządza logiką gry.

Inicjalizacja (scenario_file lub random):

Wczytuje listę przedmiotów z wybranego pliku JSON w folderze items/ LUB generuje losowy zestaw.

Zestaw musi zawierać:

10 unikalnych komponentów "Principal Blaster" (IsRequired: true).

X komponentów dodatkowych (duplikaty, "śmieci" IsRequired: false).

Przesyła all_items do wszystkich zespołów (metoda initialize w Team).

Pętla Gry: Prowadzi rundy zgodnie z kolejnością w all_items (lub losową, jeśli tak zakłada gra, ale zazwyczaj lista jest ustalona na starcie).

Generowanie stanu: Tworzy obiekt game_state dla każdego agenta w każdej iteracji.

3. Struktury Danych (Input dla Agenta)

Agent otrzymuje dwie struktury danych.

A. all_items (Static Context - format plików w folderze items/)

Lista wszystkich przedmiotów dostępnych w grze. Przekazywana raz na początku lub dołączana do promptu jako kontekst statyczny.

[
  {
    "Name": "The Visionary Compass",
    "Quality": 85,
    "IsRequired": true
  },
  {
    "Name": "Rusty Gear",
    "Quality": 15,
    "IsRequired": false
  },
  {
    "Name": "The Resilience Gyroscope",
    "Quality": 92,
    "IsRequired": true
  }
  // ... reszta przedmiotów
]


B. game_state (Dynamic Context)

Stan przekazywany przy każdym zapytaniu o ofertę ("bid").

Uwaga implementacyjna: Pole BidsHistoryForCurrentItem w instrukcji opisane jest jako List, ale wizualnie przedstawione jako mapa z kluczami "1", "2". Dla bezpieczeństwa w Pythonie najlepiej użyć słownika (dict), który w JSON wygląda tak:

{
  "CurrentRound": {
    "Item": {
      "Name": "The Visionary Compass",
      "Quality": 85,
      "IsRequired": true
    },
    "CurrentHighestBid": {
      "Bid": 150,
      "TeamName": "Team_Alpha"
    },
    "BidsHistoryForCurrentItem": {
      "1": {
        "Bid": 100,
        "TeamName": "Team_Beta"
      },
      "2": {
        "Bid": 120,
        "TeamName": "Team_Gamma"
      },
      "3": {
        "Bid": 150,
        "TeamName": "Team_Alpha"
      }
    },
    "RoundNumber": 5,
    "RoundIteration": 2
  },
  "YourTeam": {
    "Name": "Team_Beta",
    "Budget": 850,
    "Acquired": [
      {
        "Name": "The Resilience Gyroscope",
        "Quality": 70,
        "IsRequired": true
      }
    ]
  },
  "OpponentTeams": [
    {
      "Name": "Team_Alpha",
      "Budget": 600,
      "Acquired": [
        {
          "Name": "The Visionary Compass",
          "Quality": 90,
          "IsRequired": true
        }
      ]
    },
    {
      "Name": "Team_Gamma",
      "Budget": 900,
      "Acquired": []
    }
  ]
}


4. Logika Pętli Gry (Game Loop)

Symulacja powinna przebiegać według następującego algorytmu:

Setup:

Wczytaj prompty z folderu prompts/.

Wczytaj scenariusz przedmiotów (all_items) z wybranego pliku w folderze items/ (np. items/scenario_1.json).

Utwórz obiekty Team i przekaż im all_items (do zapamiętania/zcache'owania).

Pętla Rund (Rounds):

Iteruj przez listę all_items (kolejne przedmioty stają się przedmiotem aukcji).

Ustaw CurrentHighestBid na 0.

Wyzeruj BidsHistoryForCurrentItem.

Pętla Iteracji (Iterations) (np. max 10):

Dla każdego zespołu:

Wygeneruj game_state (uwzględniając perspektywę tego zespołu - tj. YourTeam vs OpponentTeams).

Zapytaj LLM o ofertę (przekazując system_prompt + all_items + game_state).

Symulacja kolejności: W środowisku lokalnym odpowiedzi przychodzą "równocześnie". Aby obsłużyć tie-breaker (kto pierwszy ten lepszy), w każdej iteracji należy przetasować listę zespołów (random.shuffle) przed przetwarzaniem ich ofert.

Walidacja ofert:

Bid > CurrentHighestBid (chyba że to pierwsza oferta, wtedy > 0).

Bid <= Team.Budget.

Wyłonienie lidera iteracji: Jeśli oferta jest poprawna i wyższa niż obecna, zaktualizuj CurrentHighestBid oraz dopisz wpis do BidsHistoryForCurrentItem.

Warunek stopu iteracji: Jeśli w danej iteracji nikt nie przebił obecnego lidera (wszyscy spasowali lub dali za mało) -> Koniec Rundy.

Rozstrzygnięcie Rundy:

Zwycięzca płaci: Team.Budget -= WinningBid.

Zwycięzca otrzymuje przedmiot: Team.Inventory.append(Item).

Jeśli runda skończyła się bez ofert (nikt nie chciał przedmiotu), przedmiot przepada.

Logowanie pełnych danych rundy.

Koniec Gry:

Obliczenie rankingu wg zasad:

Liczba IsRequired (max 10).

Suma Quality dla IsRequired.

Pozostały Budget.

5. Logowanie i Analiza Danych (Output)

Format danych wyjściowych (CSV/JSON/DataFrame):

Tabela detailed_logs:

ScenarioID (nazwa pliku z folderu items)

RoundID, ItemName, ItemQuality, IsRequired

IterationID

TeamName

BidAmount

IsValid, FailReason (np. "OverBudget", "LowerThanHighBid")

CurrentHighBidBefore

Tabela results:

ScenarioID

TeamName

CollectedItems (lista nazw)

Score_Count (0-10)

Score_Quality

Score_Budget

FinalRank

6. Generowanie Danych Testowych (Zadanie dla Copilota)

Należy wygenerować skrypt lub zestaw plików JSON w folderze items/, które pokrywają różne przypadki brzegowe:

Standard: 10 wymaganych, 5 śmieci, średnie quality.

Niedobór (Scarcity): Dokładnie 10 wymaganych przedmiotów (brak marginesu błędu).

Bogactwo (Abundance): Każdy wymagany przedmiot pojawia się 2 razy (łatwiej zebrać set, decyduje budżet/quality).

Wysoka Jakość: Wszystkie przedmioty quality > 90.

Pułapka: Dużo przedmiotów "IsRequired: False" na początku, żeby zmylić boty.

7. Wymagania Techniczne dla Implementacji Python

Biblioteki: openai (jako klient API), pandas (logi), random, json, dataclasses.

LLM Client: Kod powinien umożliwiać łatwe podpięcie lokalnego endpointu (np. base_url="http://localhost:11434/v1" dla Ollama).

Obsługa Błędów LLM:

Try-catch na parsowanie JSON z odpowiedzi LLM.

Jeśli parsowanie zawiedzie, oferta = 0 (agent pasuje).