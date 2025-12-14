"""
Data models for the Wolf of Allegro auction game.
"""

from pydantic import BaseModel, Field
from typing import Optional


class Item(BaseModel):
    """Represents an auction item."""
    name: str = Field(..., description="Unique item name")
    quality: int = Field(..., ge=0, le=100, description="Item quality (0-100, junk items have 0)")
    is_required: bool = Field(..., description="Whether this item is required to win")
    
    def model_post_init(self, __context) -> None:
        """Ensure junk items (is_required=False) have quality=0."""
        if not self.is_required and self.quality != 0:
            object.__setattr__(self, 'quality', 0)
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        if isinstance(other, Item):
            return self.name == other.name
        return False


class Bid(BaseModel):
    """Represents a bid made by a team."""
    team_name: str = Field(..., description="Name of the bidding team")
    amount: int = Field(..., ge=0, description="Bid amount")
    iteration: int = Field(..., ge=1, description="Iteration number when bid was made")


class AuctionResult(BaseModel):
    """Result of a single item auction."""
    item: Item
    winning_team: Optional[str] = Field(None, description="Name of winning team, None if no valid bids")
    winning_bid: int = Field(0, description="Winning bid amount")
    all_bids: list[Bid] = Field(default_factory=list, description="All bids made for this item")
    iterations: int = Field(1, description="Number of iterations before resolution")


class TeamState(BaseModel):
    """Current state of a team during the game."""
    name: str = Field(..., description="Team name (matches prompt file name)")
    budget: int = Field(..., ge=0, description="Remaining budget")
    acquired_items: list[Item] = Field(default_factory=list, description="Items won by this team")
    
    @property
    def required_count(self) -> int:
        """Number of required items acquired."""
        return sum(1 for item in self.acquired_items if item.is_required)
    
    @property
    def total_quality(self) -> int:
        """Sum of quality of all acquired items."""
        return sum(item.quality for item in self.acquired_items)


class GameState(BaseModel):
    """
    Complete game state passed to LLM for decision making.
    This is what each team agent sees when making a bid.
    """
    current_item: Item = Field(..., description="Item currently being auctioned")
    my_team: TeamState = Field(..., description="State of the bidding team")
    opponent_teams: list[TeamState] = Field(..., description="States of all opponent teams")
    remaining_items: list[Item] = Field(..., description="Items still to be auctioned")
    auction_history: list[AuctionResult] = Field(default_factory=list, description="Results of previous auctions")
    current_iteration: int = Field(1, ge=1, description="Current iteration for this item (1-10)")
    
    def to_prompt_context(self) -> str:
        """Convert game state to a string context for LLM prompt."""
        lines = [
            "=== CURRENT AUCTION ===",
            f"Item: {self.current_item.name}",
            f"Quality: {self.current_item.quality}",
            f"Required: {'YES' if self.current_item.is_required else 'NO'}",
            f"Iteration: {self.current_iteration}/45",
            "",
            "=== YOUR TEAM ===",
            f"Budget: {self.my_team.budget}",
            f"Required items collected: {self.my_team.required_count}",
            f"Items owned: {[item.name for item in self.my_team.acquired_items]}",
            "",
            "=== OPPONENTS ===",
        ]
        
        for opponent in self.opponent_teams:
            lines.append(f"- {opponent.name}: Budget={opponent.budget}, Required={opponent.required_count}, Items={[item.name for item in opponent.acquired_items]}")
        
        lines.extend([
            "",
            "=== REMAINING ITEMS ===",
            f"Total remaining: {len(self.remaining_items)}",
            f"Required remaining: {sum(1 for i in self.remaining_items if i.is_required)}",
        ])
        
        for item in self.remaining_items:
            req_marker = "[REQ]" if item.is_required else "[OPT]"
            lines.append(f"  - {item.name} (Q:{item.quality}) {req_marker}")
        
        return "\n".join(lines)


class GameConfig(BaseModel):
    """Configuration for a game session."""
    scenario_file: str = Field(..., description="Path to scenario JSON file")
    team_prompts: list[str] = Field(..., description="List of team prompt file names (without .txt)")
    max_iterations: int = Field(45, ge=1, le=100, description="Max iterations per item auction")
    llm_base_url: str = Field("http://localhost:11434/v1", description="Base URL for LLM API")
    llm_model: str = Field("qwen2.5:14b", description="LLM model to use")
    base_budget: int = Field(1500, ge=100, description="Base starting budget")
    budget_per_team: int = Field(200, ge=0, description="Additional budget per team")
    
    def calculate_starting_budget(self, num_teams: int) -> int:
        """Calculate starting budget: 1500 + (num_teams * 200)."""
        return self.base_budget + (num_teams * self.budget_per_team)


class FinalRanking(BaseModel):
    """Final ranking entry for a team."""
    rank: int = Field(..., ge=1, description="Final rank (1 = winner)")
    team_name: str
    required_count: int = Field(..., description="Number of required items")
    total_quality: int = Field(..., description="Sum of item qualities")
    remaining_budget: int = Field(..., description="Budget left over")
    items: list[str] = Field(..., description="Names of acquired items")
