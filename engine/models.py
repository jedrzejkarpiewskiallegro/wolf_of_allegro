"""
Data models for the Wolf of Allegro auction game.
"""

import json
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


# === JSON Format Models (matching specification) ===

class CurrentHighestBid(BaseModel):
    """Current highest bid in the auction."""
    Bid: int = Field(0, description="Highest bid amount so far")
    TeamName: Optional[str] = Field(None, description="Name of the team with highest bid")


class BidHistoryEntry(BaseModel):
    """Single entry in bid history."""
    Bid: int
    TeamName: str


class ItemJSON(BaseModel):
    """Item in JSON format for API."""
    Name: str
    Quality: int
    IsRequired: bool


class CurrentRound(BaseModel):
    """Current round state."""
    Item: ItemJSON
    CurrentHighestBid: CurrentHighestBid
    BidsHistoryForCurrentItem: list[BidHistoryEntry] = Field(default_factory=list)
    RoundNumber: int
    RoundIteration: int


class TeamJSON(BaseModel):
    """Team state in JSON format."""
    Name: str
    Budget: int
    Acquired: list[ItemJSON] = Field(default_factory=list)


class GameStateJSON(BaseModel):
    """Game state in JSON format matching the specification."""
    CurrentRound: CurrentRound
    YourTeam: TeamJSON
    OpponentTeams: list[TeamJSON]


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
    current_iteration: int = Field(1, ge=1, description="Current iteration for this item")
    round_number: int = Field(1, ge=1, description="Current round/item number")
    current_highest_bid: int = Field(0, ge=0, description="Current highest bid for this item")
    current_highest_bidder: Optional[str] = Field(None, description="Team name with highest bid")
    bids_history: list[Bid] = Field(default_factory=list, description="Bid history for current item")
    
    def to_json_format(self) -> GameStateJSON:
        """Convert to JSON format matching the specification."""
        # Convert current item
        current_item_json = ItemJSON(
            Name=self.current_item.name,
            Quality=self.current_item.quality,
            IsRequired=self.current_item.is_required
        )
        
        # Convert bid history
        bids_history_json = [
            BidHistoryEntry(Bid=b.amount, TeamName=b.team_name)
            for b in self.bids_history
        ]
        
        # Build CurrentRound
        current_round = CurrentRound(
            Item=current_item_json,
            CurrentHighestBid=CurrentHighestBid(
                Bid=self.current_highest_bid,
                TeamName=self.current_highest_bidder
            ),
            BidsHistoryForCurrentItem=bids_history_json,
            RoundNumber=self.round_number,
            RoundIteration=self.current_iteration
        )
        
        # Convert YourTeam
        your_team = TeamJSON(
            Name=self.my_team.name,
            Budget=self.my_team.budget,
            Acquired=[
                ItemJSON(Name=i.name, Quality=i.quality, IsRequired=i.is_required)
                for i in self.my_team.acquired_items
            ]
        )
        
        # Convert OpponentTeams
        opponent_teams = [
            TeamJSON(
                Name=t.name,
                Budget=t.budget,
                Acquired=[
                    ItemJSON(Name=i.name, Quality=i.quality, IsRequired=i.is_required)
                    for i in t.acquired_items
                ]
            )
            for t in self.opponent_teams
        ]
        
        return GameStateJSON(
            CurrentRound=current_round,
            YourTeam=your_team,
            OpponentTeams=opponent_teams
        )
    
    def to_prompt_context(self) -> str:
        """Convert game state to JSON string for LLM prompt."""
        json_state = self.to_json_format()
        return json_state.model_dump_json(indent=2)


class GameConfig(BaseModel):
    """Configuration for a game session."""
    scenario_file: str = Field(..., description="Path to scenario JSON file")
    team_prompts: list[str] = Field(..., description="List of team prompt file names (without .txt)")
    max_iterations: int = Field(45, ge=1, le=100, description="Max iterations per item auction")
    llm_provider: str = Field("google", description="LLM provider: 'google' or 'ollama'")
    llm_base_url: str = Field("http://localhost:11434/v1", description="Base URL for Ollama API")
    llm_model: str = Field(..., description="LLM model name (from .env)")
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
