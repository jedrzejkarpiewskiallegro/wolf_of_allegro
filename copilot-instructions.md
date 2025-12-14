# INSTRUCTIONS FOR AI DEVELOPER (GitHub Copilot / Cursor / Windsurf)

## 1. Project Goal
You are an expert Python Developer tasked with building a simulation engine for "The Agent Auction Game".
Your goal is to implement a robust, local CLI application that simulates an auction game involving AI agents (LLMs).

## 2. Context & Input Files
You will be working based on the `auction_game_spec.md` (Product Requirements Document) which defines the game logic, data structures, and output formats.

**Project Structure:**
- `main.py`: Entry point for the simulation.
- `engine/`: Core game logic (`AuctionEngine`, `Team`, `Item`).
- `prompts/`: Directory containing `.txt` files (one per team). The filename is the Team Name.
- `items/`: Directory containing `.json` scenarios (lists of items).

## 3. Technical Requirements

### Stack
- **Language:** Python 3.10+
- **LLM Client:** `openai` library (configured for local server, e.g., Ollama/LM Studio).
- **Data Validation:** `pydantic` (for strict `game_state` and `Item` schema validation).
- **Data Analysis:** `pandas` (for collecting and saving logs).
- **UI:** `tqdm` (for progress bars).

### Core Responsibilities

1.  **Strict State Management:**
    - You must implement the `game_state` structure EXACTLY as defined in the spec.
    - The LLM depends on this specific JSON structure to make decisions.

2.  **LLM Integration:**
    - Create an abstract client that connects to `http://localhost:11434/v1` (or configurable env var).
    - Implement a retry/fallback mechanism. If the LLM returns invalid JSON or text, the bid defaults to `0`.

3.  **The "Tie-Breaker" Logic:**
    - In a real server, the fastest request wins.
    - In this local simulation, strictly follow the spec: **Shuffle the list of teams randomly in every single iteration** before processing bids to simulate latency variations.

4.  **Data Logging:**
    - Do not just print to console.
    - Accumulate data in a list of dictionaries during the game.
    - At the end of the simulation, export two CSVs:
        - `detailed_logs.csv` (every bid, every iteration).
        - `game_results.csv` (final rankings).

## 4. Implementation Steps (Step-by-Step Guide)

**Step 1: Data Models (`engine/models.py`)**
- Create Pydantic models for `Item`, `TeamState`, `OpponentState`, `GameState`.
- This ensures that when we convert to JSON for the LLM, the types are correct.

**Step 2: Team Agent (`engine/team.py`)**
- Implement the `Team` class.
- It should load the system prompt from `prompts/{name}.txt`.
- It should method `get_bid(game_state: dict) -> int`.

**Step 3: Game Engine (`engine/simulation.py`)**
- Implement `AuctionEngine`.
- Load items from `items/scenario.json`.
- Run the loops: `For Item in Items` -> `For Iteration in 1..10`.
- Handle the bidding logic, budget updates, and inventory management.

**Step 4: Scenario Generator (`tools/generate_scenarios.py`)**
- Create a script to generate the JSON files for `items/` as requested in the spec (Standard, Scarcity, Abundance, etc.).

**Step 5: Main Entry (`main.py`)**
- Argument parser to select the `scenario` file.
- Initialize engine and run.
- Save results.

## 5. Constraint Checklist & Code Style
- **Type Hinting:** Use strict type hints for all functions.
- **Docstrings:** Add docstrings explaining the logic, especially for the Auction Rules.
- **Error Handling:** The simulation must NOT crash if the LLM hallucinates. Catch JSONDecodeErrors.
- **Configuration:** Use a `.env` file or constants for `MAX_ITERATIONS` (default 10) and `LLM_BASE_URL`.

Now, please generate the code starting with the Data Models.