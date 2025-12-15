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
    
    def __init__(self, config: GameConfig, prompts_dir: Path):
        """
        Initialize the auction engine.
        
        Args:
            config: Game configuration
            prompts_dir: Directory containing team prompt files
        """
        self.config = config
        self.prompts_dir = prompts_dir
        
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
        
        # Track previous iteration's highest bid for stability check
        prev_highest_bid: int | None = None
        prev_highest_team: str | None = None
        stable_iterations: int = 0  # How many iterations the highest bid stayed the same
        
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
            bids_history_snapshot = all_bids.copy()
            
            for team in shuffled_teams:
                game_state = self._build_game_state(
                    team=team, 
                    current_item=item, 
                    iteration=iteration,
                    round_number=round_number,
                    current_highest_bid=iteration_start_high_bid,
                    current_highest_bidder=iteration_start_high_bidder,
                    bids_history=bids_history_snapshot  # Same snapshot for all teams
                )
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
                
                # Update state for NEXT iteration (all teams will see this)
                if max_bid.amount > iteration_start_high_bid:
                    iteration_start_high_bid = max_bid.amount
                    # In case of tie, first in shuffle order wins
                    tied_bids = [b for b in iteration_bids if b.amount == max_bid.amount]
                    iteration_start_high_bidder = tied_bids[0].team_name
                
                # Log iteration results
                logger.info(
                    f"Iteration {iteration}: Highest bid = {iteration_start_high_bid} "
                    f"by '{iteration_start_high_bidder if iteration_start_high_bidder else 'None'}'"
                )
                
                # Early exit: if no team can bid higher, end auction
                if iteration_start_high_bid > 0:
                    teams_that_can_outbid = [t for t in self.teams if t.state.budget > iteration_start_high_bid]
                    if not teams_that_can_outbid:
                        logger.info(
                            f"No team can bid higher than {iteration_start_high_bid}. "
                            f"'{iteration_start_high_bidder}' wins '{item.name}'."
                        )
                        winner = next(t for t in self.teams if t.name == iteration_start_high_bidder)
                        winner.win_item(item, iteration_start_high_bid)
                        
                        return AuctionResult(
                            item=item,
                            winning_team=iteration_start_high_bidder,
                            winning_bid=iteration_start_high_bid,
                            all_bids=all_bids,
                            iterations=iteration
                        )
                
                # Check for ties at the highest bid amount
                tied_bids = [b for b in iteration_bids if b.amount == max_bid.amount]
                
                if len(tied_bids) == 1:
                    # Single highest bidder this iteration
                    current_highest_bid = max_bid.amount
                    current_highest_team = max_bid.team_name
                    
                    # Check if highest bid is stable (same amount and team as previous iteration)
                    if (current_highest_bid == prev_highest_bid and 
                        current_highest_team == prev_highest_team):
                        stable_iterations += 1
                    else:
                        stable_iterations = 1  # Reset: new leader or new amount
                    
                    logger.debug(
                        f"Highest bid: {current_highest_bid} by '{current_highest_team}' "
                        f"(stable for {stable_iterations} iteration(s))"
                    )
                    
                    # Auction ends if stable for 2 iterations
                    if stable_iterations >= 2:
                        if current_highest_bid > 0:
                            winner = next(t for t in self.teams if t.name == current_highest_team)
                            winner.win_item(item, current_highest_bid)
                            
                            logger.info(
                                f"'{current_highest_team}' wins '{item.name}' "
                                f"for {current_highest_bid} (stable for 2 iterations)"
                            )
                            
                            return AuctionResult(
                                item=item,
                                winning_team=current_highest_team,
                                winning_bid=current_highest_bid,
                                all_bids=all_bids,
                                iterations=iteration
                            )
                        else:
                            # All bids are 0 for 2 iterations, no winner
                            logger.info(f"All bids for '{item.name}' are 0 for 2 iterations, no winner")
                            return AuctionResult(
                                item=item,
                                winning_team=None,
                                winning_bid=0,
                                all_bids=all_bids,
                                iterations=iteration
                            )
                    
                    # Update tracking for next iteration
                    prev_highest_bid = current_highest_bid
                    prev_highest_team = current_highest_team
                    
                else:
                    # Tie - reset stability counter, continue to next iteration
                    stable_iterations = 0
                    prev_highest_bid = max_bid.amount
                    prev_highest_team = None  # No single leader
                    logger.debug(
                        f"Tie between {[b.team_name for b in tied_bids]} "
                        f"at {max_bid.amount}, continuing..."
                    )
        
        # Max iterations reached with ties - use shuffle order (first in shuffled list wins)
        final_bids = all_bids[-len(self.teams):]
        max_amount = max(b.amount for b in final_bids)
        
        if max_amount > 0:
            # Winner is first team in shuffle order with max bid
            for bid in final_bids:
                if bid.amount == max_amount:
                    winner = next(t for t in self.teams if t.name == bid.team_name)
                    winner.win_item(item, max_amount)
                    
                    logger.info(
                        f"Max iterations reached. '{bid.team_name}' wins '{item.name}' "
                        f"for {max_amount} (random tie-break)"
                    )
                    
                    return AuctionResult(
                        item=item,
                        winning_team=bid.team_name,
                        winning_bid=max_amount,
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
    
    def close(self):
        """Clean up resources."""
        self.llm_client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
