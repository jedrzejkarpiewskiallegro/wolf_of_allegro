"""
Team agent that uses LLM to make bidding decisions.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import GameState, TeamState, Item, ItemJSON
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


def debug_dump(content: str, filename: str | None = None, subfolder: str = "debug") -> None:
    """
    Helper function to dump content to a file for debugging.
    
    Args:
        content: The content to write to file
        filename: Optional filename. If None, uses timestamp
        subfolder: Subfolder under project root (default: "debug")
    """
    # Create debug directory
    debug_dir = Path(__file__).parent.parent / subfolder
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename if not provided
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"dump_{timestamp}.txt"
    
    # Write to file
    filepath = debug_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    
    logger.debug(f"Debug dump saved to: {filepath}")


class Team:
    """
    Represents a team in the auction game.
    Each team has a strategy defined by a system prompt file.
    """
    
    def __init__(
        self,
        name: str,
        prompt_file: Path,
        starting_budget: int,
        llm_client: LLMClient
    ):
        """
        Initialize a team.
        
        Args:
            name: Team name (typically the prompt file name without extension)
            prompt_file: Path to the .txt file containing the system prompt
            starting_budget: Initial budget for the team
            llm_client: Shared LLM client instance
        """
        self.name = name
        self.prompt_file = prompt_file
        self.llm_client = llm_client
        
        # Load system prompt
        self.system_prompt = self._load_prompt()
        
        # Initialize state
        self.state = TeamState(
            name=name,
            budget=starting_budget,
            acquired_items=[]
        )
        
        # Cache for all_items (set once at game start, doesn't change)
        self._all_items: list[Item] = []
        self._all_items_json: str = "[]"
    
    def initialize_items(self, all_items: list[Item]) -> None:
        """
        Initialize the cached all_items list. Called once at game start.
        
        Args:
            all_items: Complete list of all auction items in the game
        """
        self._all_items = all_items
        # Pre-compute JSON representation for efficiency
        items_json = [
            ItemJSON(Name=item.name, Quality=item.quality, IsRequired=item.is_required)
            for item in all_items
        ]
        import json
        self._all_items_json = json.dumps(
            [item.model_dump() for item in items_json],
            indent=2
        )
        logger.info(f"Team '{self.name}' initialized with {len(all_items)} items")
    
    def _load_prompt(self) -> str:
        """Load the system prompt from file."""
        try:
            with open(self.prompt_file, "r", encoding="utf-8") as f:
                prompt = f.read().strip()
                logger.info(f"Loaded prompt for team '{self.name}' from {self.prompt_file}")
                return prompt
        except FileNotFoundError:
            logger.error(f"Prompt file not found: {self.prompt_file}")
            raise
        except Exception as e:
            logger.error(f"Error loading prompt for team '{self.name}': {e}")
            raise
    
    def get_bid(self, game_state: GameState) -> int:
        """
        Get a bid from this team for the current item.
        
        Args:
            game_state: Current state of the game from this team's perspective
            
        Returns:
            Bid amount (0 if LLM fails or returns invalid response)
        """
        # Convert game state to JSON format
        game_state_json = game_state.to_prompt_context()
        
        # Build user message with both all_items and game_state
        user_message = f"""all_items:
{self._all_items_json}

game_state:
{game_state_json}

Based on all_items and game_state JSON above, determine your bid.
Respond with ONLY a single integer (your bid amount). Nothing else."""
        
        # Uncomment to debug: dump user_message to file
        # debug_dump(user_message, filename=f"{self.name}_{game_state.current_item.name}_iter{game_state.current_iteration}.txt")
        
        # Call LLM
        logger.debug(f"Team '{self.name}' requesting bid for item '{game_state.current_item.name}'")
        response = self.llm_client.chat_completion(
            system_prompt=self.system_prompt,
            user_message=user_message
        )
        
        # Parse response
        bid = self.llm_client.parse_bid_response(response)
        
        # Validate bid doesn't exceed budget
        if bid > self.state.budget:
            logger.warning(
                f"Team '{self.name}' bid {bid} exceeds budget {self.state.budget}, "
                f"capping to budget"
            )
            bid = self.state.budget
        
        logger.info(f"Team '{self.name}' bids {bid} for '{game_state.current_item.name}'")
        return bid
    
    def win_item(self, item, price: int):
        """
        Record that this team won an item.
        
        Args:
            item: The Item that was won
            price: The price paid
        """
        self.state.budget -= price
        self.state.acquired_items.append(item)
        logger.info(
            f"Team '{self.name}' won '{item.name}' for {price}. "
            f"Remaining budget: {self.state.budget}"
        )
    
    def get_state(self) -> TeamState:
        """Get current team state."""
        return self.state.model_copy(deep=True)
    
    def __repr__(self) -> str:
        return f"Team(name='{self.name}', budget={self.state.budget}, items={len(self.state.acquired_items)})"
