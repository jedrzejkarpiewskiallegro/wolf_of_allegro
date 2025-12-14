"""
Team agent that uses LLM to make bidding decisions.
"""

import logging
from pathlib import Path
from typing import Optional

from .models import GameState, TeamState
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


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
        # Convert game state to prompt context
        context = game_state.to_prompt_context()
        
        # Add instruction for response format
        user_message = f"""{context}

=== YOUR DECISION ===
Based on the above state, how much do you bid for this item?
Respond with ONLY a single integer (your bid amount). Nothing else."""
        
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
