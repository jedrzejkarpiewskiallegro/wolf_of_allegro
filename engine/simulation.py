"""
Auction simulation engine - core game loop.
"""

import json
import logging
import random
from pathlib import Path
from typing import Optional

from .models import (
    Item, Bid, AuctionResult, TeamState, GameState,
    GameConfig, FinalRanking
)
from .team import Team
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class AuctionEngine:
    """
    Main auction game engine.
    Handles the game loop, bidding process, and final ranking.
    """
    
    def __init__(self, config: GameConfig, prompts_dir: Path, session_dir: Path | None = None):
        """
        Initialize the auction engine.
        
        Args:
            config: Game configuration
            prompts_dir: Directory containing team prompt files
            session_dir: Directory for this session's logs (optional)
        """
        self.config = config
        self.prompts_dir = prompts_dir
        self.session_dir = session_dir
        
        # Initialize LLM client
        self.llm_client = LLMClient(
            base_url=config.llm_base_url,
            model=config.llm_model
        )
        
        # Load items from scenario
        self.items = self._load_scenario()
        self.remaining_items = list(self.items)
        
        # Initialize teams (budget depends on team count)
        self.teams = self._init_teams()
        
        # Initialize all_items cache for each team (once at game start)
        for team in self.teams:
            team.initialize_items(self.items)
        
        # Track auction history
        self.auction_history: list[AuctionResult] = []
        
        logger.info(
            f"Initialized AuctionEngine with {len(self.items)} items "
            f"and {len(self.teams)} teams"
        )
    
    def _load_scenario(self) -> list[Item]:
        """Load items from scenario JSON file."""
        scenario_path = Path(self.config.scenario_file)
        
        try:
            with open(scenario_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Handle both formats: array or object with "items" key
            if isinstance(data, list):
                items_data = data
            elif isinstance(data, dict) and "items" in data:
                items_data = data["items"]
            else:
                raise ValueError("JSON must be an array or object with 'items' key")
            
            # Normalize keys to lowercase (handle Name->name, Quality->quality, IsRequired->is_required)
            items = []
            for item_data in items_data:
                normalized = {
                    "name": item_data.get("name") or item_data.get("Name"),
                    "quality": item_data.get("quality") or item_data.get("Quality"),
                    "is_required": item_data.get("is_required") if "is_required" in item_data else item_data.get("IsRequired")
                }
                items.append(Item(**normalized))
            
            logger.info(f"Loaded {len(items)} items from {scenario_path}")
            return items
            
        except FileNotFoundError:
            logger.error(f"Scenario file not found: {scenario_path}")
            raise
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Error parsing scenario file: {e}")
            raise
    
    def _init_teams(self) -> list[Team]:
        """Initialize all teams from prompt files."""
        teams = []
        
        # Calculate starting budget based on number of teams
        num_teams = len(self.config.team_prompts)
        starting_budget = self.config.calculate_starting_budget(num_teams)
        logger.info(f"Starting budget: {starting_budget} (base={self.config.base_budget} + {num_teams}*{self.config.budget_per_team})")
        
        for prompt_name in self.config.team_prompts:
            prompt_file = self.prompts_dir / f"{prompt_name}.txt"
            
            team = Team(
                name=prompt_name,
                prompt_file=prompt_file,
                starting_budget=starting_budget,
                llm_client=self.llm_client
            )
            teams.append(team)
        
        logger.info(f"Initialized {len(teams)} teams: {[t.name for t in teams]}")
        return teams
    
    def _build_game_state(
        self, 
        team: Team, 
        current_item: Item, 
        iteration: int,
        round_number: int = 1,
        current_highest_bid: int = 0,
        current_highest_bidder: str | None = None,
        bids_history: list[Bid] | None = None
    ) -> GameState:
        """Build the game state from a specific team's perspective."""
        opponent_states = [
            t.get_state() for t in self.teams if t.name != team.name
        ]
        
        return GameState(
            current_item=current_item,
            my_team=team.get_state(),
            opponent_teams=opponent_states,
            remaining_items=[i for i in self.remaining_items if i != current_item],
            auction_history=list(self.auction_history),
            current_iteration=iteration,
            round_number=round_number,
            current_highest_bid=current_highest_bid,
            current_highest_bidder=current_highest_bidder,
            bids_history=bids_history or []
        )
    
    def _run_single_auction(self, item: Item, round_number: int = 1) -> AuctionResult:
        """
        Run auction for a single item.
        Uses iterative bidding with shuffle for tie-breaking.
        Auction ends when highest bid stays unchanged for 2 consecutive iterations.
        """
        all_bids: list[Bid] = []
        winning_bids_history: list[Bid] = []  # Only highest bids from each iteration
        
        # Track current highest bid for game state (from END of previous iteration)
        # This is what all teams see at the START of each iteration
        iteration_start_high_bid: int = 0
        iteration_start_high_bidder: str | None = None
        
        for iteration in range(1, self.config.max_iterations + 1):
            logger.debug(f"Item '{item.name}' - Iteration {iteration}")
            
            # Shuffle teams for fair tie-breaking
            shuffled_teams = list(self.teams)
            random.shuffle(shuffled_teams)
            
            iteration_bids: list[Bid] = []
            
            # IMPORTANT: All teams see the SAME game_state within one iteration
            # This simulates simultaneous bidding - state is frozen from end of previous iteration
            bids_history_snapshot = winning_bids_history.copy()
            
            for team in shuffled_teams:
                game_state = self._build_game_state(
                    team=team, 
                    current_item=item, 
                    iteration=iteration,
                    round_number=round_number,
                    current_highest_bid=iteration_start_high_bid,
                    current_highest_bidder=iteration_start_high_bidder,
                    bids_history=bids_history_snapshot  # Only winning bids from previous iterations
                )
                
                # Save game_state to file for debugging
                self._save_game_state(game_state, round_number, iteration)
                
                bid_amount = team.get_bid(game_state)
                
                bid = Bid(
                    team_name=team.name,
                    amount=bid_amount,
                    iteration=iteration
                )
                iteration_bids.append(bid)
                all_bids.append(bid)
            
            # After ALL teams have bid, find the highest bid from THIS iteration
            if iteration_bids:
                max_bid = max(iteration_bids, key=lambda b: b.amount)
                
                # Check if anyone outbid the current highest
                if max_bid.amount > iteration_start_high_bid:
                    # New highest bid - update leader
                    iteration_start_high_bid = max_bid.amount
                    # In case of tie, first in shuffle order wins
                    tied_bids = [b for b in iteration_bids if b.amount == max_bid.amount]
                    iteration_start_high_bidder = tied_bids[0].team_name
                    
                    # Add winning bid to history
                    winning_bid = Bid(
                        team_name=iteration_start_high_bidder,
                        amount=iteration_start_high_bid,
                        iteration=iteration
                    )
                    winning_bids_history.append(winning_bid)
                    
                    # Log iteration results
                    logger.info(
                        f"Iteration {iteration}: Highest bid = {iteration_start_high_bid} "
                        f"by '{iteration_start_high_bidder}'"
                    )
                else:
                    # No one outbid - auction ends immediately
                    logger.info(
                        f"Iteration {iteration}: No higher bids. Auction ends."
                    )
                    
                    if iteration_start_high_bid > 0 and iteration_start_high_bidder:
                        winner = next(t for t in self.teams if t.name == iteration_start_high_bidder)
                        winner.win_item(item, iteration_start_high_bid)
                        
                        logger.info(
                            f"'{iteration_start_high_bidder}' wins '{item.name}' "
                            f"for {iteration_start_high_bid}"
                        )
                        
                        return AuctionResult(
                            item=item,
                            winning_team=iteration_start_high_bidder,
                            winning_bid=iteration_start_high_bid,
                            all_bids=all_bids,
                            iterations=iteration
                        )
                    else:
                        # No valid bids at all
                        logger.info(f"No valid bids for '{item.name}', no winner")
                        return AuctionResult(
                            item=item,
                            winning_team=None,
                            winning_bid=0,
                            all_bids=all_bids,
                            iterations=iteration
                        )
        
        # Max iterations reached - give item to current highest bidder
        if iteration_start_high_bid > 0 and iteration_start_high_bidder:
            winner = next(t for t in self.teams if t.name == iteration_start_high_bidder)
            winner.win_item(item, iteration_start_high_bid)
            
            logger.info(
                f"Max iterations reached. '{iteration_start_high_bidder}' wins '{item.name}' "
                f"for {iteration_start_high_bid}"
            )
            
            return AuctionResult(
                item=item,
                winning_team=iteration_start_high_bidder,
                winning_bid=iteration_start_high_bid,
                all_bids=all_bids,
                iterations=self.config.max_iterations
            )
        
        # No valid bids
        return AuctionResult(
            item=item,
            winning_team=None,
            winning_bid=0,
            all_bids=all_bids,
            iterations=self.config.max_iterations
        )
    
    def run(self) -> list[FinalRanking]:
        """
        Run the complete auction game.
        
        Returns:
            Final rankings of all teams
        """
        logger.info("=" * 50)
        logger.info("STARTING AUCTION GAME")
        logger.info("=" * 50)
        
        for i, item in enumerate(self.items, 1):
            logger.info(f"\n--- Auction {i}/{len(self.items)}: {item.name} ---")
            logger.info(f"Quality: {item.quality}, Required: {item.is_required}")
            
            result = self._run_single_auction(item, round_number=i)
            self.auction_history.append(result)
            
            # Save incremental logs after each auction
            self.save_session_logs()
            
            # Remove from remaining items
            if item in self.remaining_items:
                self.remaining_items.remove(item)
            
            if result.winning_team:
                logger.info(
                    f"Winner: {result.winning_team} with bid {result.winning_bid}"
                )
            else:
                logger.info("No winner - item not sold")
        
        # Calculate final rankings
        rankings = self._calculate_rankings()
        
        logger.info("\n" + "=" * 50)
        logger.info("FINAL RANKINGS")
        logger.info("=" * 50)
        
        for ranking in rankings:
            logger.info(
                f"#{ranking.rank} {ranking.team_name}: "
                f"Required={ranking.required_count}, "
                f"Quality={ranking.total_quality}, "
                f"Budget={ranking.remaining_budget}"
            )
        
        return rankings
    
    def _calculate_rankings(self) -> list[FinalRanking]:
        """
        Calculate final rankings.
        Priority: Required count > Total quality > Remaining budget
        """
        team_scores = []
        
        for team in self.teams:
            state = team.get_state()
            team_scores.append({
                "name": team.name,
                "required_count": state.required_count,
                "total_quality": state.total_quality,
                "budget": state.budget,
                "items": [item.name for item in state.acquired_items]
            })
        
        # Sort by ranking criteria (descending for all)
        team_scores.sort(
            key=lambda t: (t["required_count"], t["total_quality"], t["budget"]),
            reverse=True
        )
        
        rankings = []
        for rank, team_data in enumerate(team_scores, 1):
            rankings.append(FinalRanking(
                rank=rank,
                team_name=team_data["name"],
                required_count=team_data["required_count"],
                total_quality=team_data["total_quality"],
                remaining_budget=team_data["budget"],
                items=team_data["items"]
            ))
        
        return rankings
    
    def get_detailed_logs(self) -> list[dict]:
        """
        Get detailed logs for CSV export.
        Returns one row per bid.
        """
        logs = []
        
        for result in self.auction_history:
            for bid in result.all_bids:
                logs.append({
                    "item_name": result.item.name,
                    "item_quality": result.item.quality,
                    "item_required": result.item.is_required,
                    "team_name": bid.team_name,
                    "bid_amount": bid.amount,
                    "iteration": bid.iteration,
                    "won": bid.team_name == result.winning_team and bid.amount == result.winning_bid,
                    "winning_bid": result.winning_bid
                })
        
        return logs
    
    def save_session_logs(self) -> None:
        """
        Save current state of logs to session directory.
        Called incrementally during game and on interruption.
        """
        if not self.session_dir:
            return
        
        import csv
        from .models import ItemJSON
        
        # Save all_items.json (once)
        all_items_path = self.session_dir / "all_items.json"
        if not all_items_path.exists():
            items_json = [
                ItemJSON(Name=item.name, Quality=item.quality, IsRequired=item.is_required)
                for item in self.items
            ]
            with open(all_items_path, "w", encoding="utf-8") as f:
                json.dump([item.model_dump() for item in items_json], f, indent=2)
        
        # Save detailed logs (all bids)
        detailed_logs_path = self.session_dir / "detailed_logs.csv"
        logs = self.get_detailed_logs()
        if logs:
            with open(detailed_logs_path, "w", newline="", encoding="utf-8") as f:
                fieldnames = [
                    "item_name", "item_quality", "item_required",
                    "team_name", "bid_amount", "iteration", "won", "winning_bid"
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(logs)
        
        # Save auction results summary
        auction_summary_path = self.session_dir / "auction_results.csv"
        if self.auction_history:
            with open(auction_summary_path, "w", newline="", encoding="utf-8") as f:
                fieldnames = ["item_name", "winner", "winning_bid", "iterations"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for result in self.auction_history:
                    writer.writerow({
                        "item_name": result.item.name,
                        "winner": result.winning_team or "None",
                        "winning_bid": result.winning_bid,
                        "iterations": result.iterations
                    })
        
        # Save current team states
        team_states_path = self.session_dir / "team_states.json"
        team_states = []
        for team in self.teams:
            state = team.get_state()
            team_states.append({
                "name": state.name,
                "budget": state.budget,
                "acquired_items": [item.name for item in state.acquired_items]
            })
        with open(team_states_path, "w", encoding="utf-8") as f:
            json.dump(team_states, f, indent=2)
        
        logger.debug(f"Session logs saved to: {self.session_dir}")
    
    def _save_game_state(self, game_state: GameState, round_number: int, iteration: int) -> None:
        """
        Save game_state JSON for debugging.
        Organized in folders: game_states/round_X/iter_Y/team_NAME.json
        """
        if not self.session_dir:
            return
        
        # Create nested folder structure
        states_dir = self.session_dir / "game_states" / f"round_{round_number}" / f"iter_{iteration}"
        states_dir.mkdir(parents=True, exist_ok=True)
        
        # Filename: team_jj.json
        filename = f"team_{game_state.my_team.name}.json"
        filepath = states_dir / filename
        
        # Save as formatted JSON
        game_state_json = game_state.to_prompt_context()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(game_state_json)
    
    def close(self):
        """Clean up resources."""
        self.llm_client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
