The Agent Auction Game
Welcome to the Agent Auction. We’re inviting the entire Allegro crew to join a playful challenge: compete to assemble the mythical Principal Blaster by bidding on its ten legendary components in a high-stakes auction.

The Principal Blaster began as an inside joke among Principal Software Engineers, but it has since evolved into a symbol of what powers Allegro: ambition, innovation, and the ability to turn ideas into real impact. Today, we treat it as a metaphor for the tool we’re building together — a tool that will help lift Allegro to the next level.

Principal Blaster illustration
Below are the components you’ll be fighting for. Each represents a key “super-module” of our organization.

The Visionary Compass
The guiding force that helps us navigate uncharted territory and stay aligned with our shared north star. A symbol of clarity, intentionality, and avoiding wasted effort.
The Interconnected Cognition Matrix
The brain of the set. It connects teams, initiatives, and systems into a coherent whole that performs better than the sum of its parts. The embodiment of systems thinking.
The Resilience Gyroscope
A stabilizer built for periods of rapid growth, shifting priorities, and sudden spikes. It keeps things balanced when the pace is high and pressure rises. The quiet guardian against chaos.
The Catalyst Ignition Spark
The energy source that turns good ideas into great outcomes. This component represents the moment when “it can’t be done” transforms into “done.”
The Automated Evolution Engine
A mechanism of progress. It simplifies, automates, raises quality, and opens new possibilities. A symbol of continuous improvement and reinvention.
The Cross-Domain Harmonizer
A connector of worlds. It bridges different teams, competencies, and projects; reduces friction; and strengthens collaboration across the entire organization.
The Legacy De-Tangler
A precision tool for unraveling outdated, overly complex structures. It makes room for modern, fast, and elegant solutions by clearing the path.
The Predictive Insight Array
A forward-looking scanner. It spots obstacles before they grow, highlights opportunities before they emerge, and empowers proactive rather than reactive action.
The Consensus Catalyst
A decision generator. It helps align diverse perspectives, resolve conflicting priorities, and turn long discussions into clear direction.
The Strategic Blueprint Stabilizer
A foundational element that ensures what we build is coherent, future-proof, and anchored in Allegro’s long-term strategy. It stabilizes the architecture of our decisions and actions.
How It Works: The Big Picture
The game is fully centrally orchestrated. Every round, every bid, every decision flows through the main control system. Your team contributes by updating only one thing: the prompt in your Team Admin Panel.

Core Components of the System
The Auctioneer:
A central server that manages the entire game, coordinates all rounds and iterations, controls state, and acts as the single source of truth.
Your Team Prompt (in the Team Admin Panel):
This is the “brain” of your agent. The Auctioneer sends your prompt together with the game_state to Gemini AI, and Gemini responds with your team’s bid.
That’s your entire interface. No applications to run, no code to deploy. Only strategy.

Gameplay Structure: Rounds & Iterations
Rounds
In every round, a single component is auctioned.

Iterations (Bidding Cycles)
Each round consists of several iterations.
In every iteration, each team’s agent submits the amount they want to bid.

Iterations continue until:

a team wins the item by holding the highest valid bid, or
the pre-defined iteration limit for the round is reached.
How a Team Wins an Iteration
The bid must be higher than the current bid.
The bid must be within the team’s remaining budget.
If multiple teams submit the same highest bid, the winner is the team whose agent submitted the bid first (fastest response).
How a Team Wins a Round
A team wins the round if:

they had the highest valid bid in the last iteration,
and no higher bid was submitted in that final iteration,
or the iteration limit for the round has been reached and they are holding the lead.
At the end of the round, the winning team pays their bid and receives the component.

The Mission: Your Objective
Your team aims to place first in the overall ranking, determined in this order:

Number of Required Components:
Teams that collect all required Principal Blaster components rank highest.
Total Quality Score:
If teams collected the same number of required components, the combined quality score of those components decides the ranking.
Remaining Budget:
If still tied, the team with the most budget left wins.
What Your Agent Sees
Your agent receives two sources of information: all_items and game_state.
Together they provide the full snapshot of the world at the moment the bid is requested.

all_items
A list of all auction items available in the game. Cached once per team at the start of the game — does not change between calls.

all_items: List
  ├─
  │    ├─ Name: string (Name of the component)
  │    ├─ Quality: int (Quality score [1-100])
  │    └─ IsRequired: bool (is it part of the Principal Blaster set?)
  └─ ...
game_state
The current state of the auction. Passed fresh with every LLM call — always reflects the latest situation.

game_state
  ├─ CurrentRound:
  │    ├─ Item:
  │    │    ├─ Name: string (Name of the auctioned component)
  │    │    │─ Quality: int (Quality score [1-100])
  │    │    └─ IsRequired: bool (is it part of the Principal Blaster set?)
  │    ├─ CurrentHighestBid:
  │    │    ├─ Bid: int (highest bid so far)
  │    │    └─ TeamName: string (name of the team with the highest bid)
  │    ├─ BidsHistoryForCurrentItem: List
  │    │    ├─ 1:
  │    │    │    ├─ Bid: int
  │    │    │    └─ TeamName: string
  │    │    ├─ 2:
  │    │    │    ├─ Bid: int
  │    │    │    └─ TeamName: string
  │    │    └─ ...
  │    ├─ RoundNumber: int (current item number)
  │    └─ RoundIteration: int (current bidding iteration for this item)
  ├─ YourTeam:
  │    ├─ Name: string (your team name)
  │    ├─ Budget: int (remaining budget for bidding)
  │    └─ Acquired: List
  │         ├─
  │         │    ├─ Name: string
  │         │    │─ Quality: int (Quality score [1-100])
  │         │    └─ IsRequired: bool (is it part of the Principal Blaster set?)
  │         └─ ...
  └─ OpponentTeams: List
       ├─
       │    ├─ Name: string (opponent team name)
       │    ├─ Budget: int (remaining budget for bidding)
       │    └─ Acquired: List
       │         ├─
       │         │    ├─ Name: string
       │         │    │─ Quality: int (Quality score [1-100])
       │         │    └─ IsRequired: bool (is it part of the Principal Blaster set?)
       │         └─ ...
       └─ ...
Your only strategic lever is the prompt. Use any data from the game_state in your prompt. Precision pays off.