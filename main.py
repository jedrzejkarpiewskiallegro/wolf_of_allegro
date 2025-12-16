"""
Wolf of Allegro - Auction Game
Main entry point with CLI interface.
"""

import argparse
import csv
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from engine.models import GameConfig
from engine.simulation import AuctionEngine

# Load environment variables
load_dotenv()


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )


def get_available_scenarios(items_dir: Path) -> list[str]:
    """List available scenario files."""
    if not items_dir.exists():
        return []
    return [f.stem for f in items_dir.glob("*.json")]


def get_available_teams(prompts_dir: Path) -> list[str]:
    """List available team prompt files."""
    if not prompts_dir.exists():
        return []
    return [f.stem for f in prompts_dir.glob("*.txt")]


def export_detailed_logs(logs: list[dict], output_path: Path):
    """Export detailed bid logs to CSV."""
    if not logs:
        print("No logs to export")
        return
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    fieldnames = [
        "item_name", "item_quality", "item_required",
        "team_name", "bid_amount", "iteration", "won", "winning_bid"
    ]
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(logs)
    
    print(f"Detailed logs exported to: {output_path}")


def export_results(rankings: list, output_path: Path):
    """Export final rankings to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    fieldnames = [
        "rank", "team_name", "required_count", 
        "total_quality", "remaining_budget", "items"
    ]
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for r in rankings:
            writer.writerow({
                "rank": r.rank,
                "team_name": r.team_name,
                "required_count": r.required_count,
                "total_quality": r.total_quality,
                "remaining_budget": r.remaining_budget,
                "items": "; ".join(r.items)
            })
    
    print(f"Results exported to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Wolf of Allegro - LLM Auction Game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --scenario standard --teams 1 2
  python main.py --scenario trap --teams 1 2 --max-iterations 45
  python main.py --list-scenarios
  python main.py --list-teams
        """
    )
    
    # Project paths
    project_dir = Path(__file__).parent
    items_dir = project_dir / "items"
    prompts_dir = project_dir / "prompts"
    output_dir = project_dir / "output"
    
    # Arguments
    parser.add_argument(
        "--scenario", "-s",
        help="Scenario name (without .json extension)"
    )
    parser.add_argument(
        "--teams", "-t",
        nargs="+",
        default=None,
        help="Team names (prompt file names without .txt). If not specified, uses all teams from prompts/"
    )
    parser.add_argument(
        "--max-iterations", "-i",
        type=int,
        default=int(os.getenv("MAX_ITERATIONS", "45")),
        help="Max bidding iterations per item (default: 45)"
    )
    parser.add_argument(
        "--llm-url",
        default=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
        help="LLM API base URL (only for Ollama provider)"
    )
    parser.add_argument(
        "--llm-model",
        default=os.getenv("LLM_MODEL", "gemini-2.5-flash-preview-05-20"),
        help="LLM model name"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=output_dir,
        help="Output directory for CSV files"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List available scenarios and exit"
    )
    parser.add_argument(
        "--list-teams",
        action="store_true",
        help="List available teams and exit"
    )
    parser.add_argument(
        "--generate-scenarios",
        action="store_true",
        help="Generate all scenario files and exit"
    )
    
    args = parser.parse_args()
    
    # Handle list commands
    if args.list_scenarios:
        scenarios = get_available_scenarios(items_dir)
        if scenarios:
            print("Available scenarios:")
            for s in scenarios:
                print(f"  - {s}")
        else:
            print("No scenarios found. Run with --generate-scenarios first.")
        return
    
    if args.list_teams:
        teams = get_available_teams(prompts_dir)
        if teams:
            print("Available teams:")
            for t in teams:
                print(f"  - {t}")
        else:
            print("No team prompts found in prompts/ directory.")
        return
    
    if args.generate_scenarios:
        from tools.generate_scenarios import generate_all_scenarios
        generate_all_scenarios(items_dir)
        return
    
    # Validate required arguments
    if not args.scenario:
        parser.error("--scenario is required")
    
    # Auto-discover teams if not specified
    if not args.teams:
        args.teams = get_available_teams(prompts_dir)
        if not args.teams:
            parser.error("No team prompts found in prompts/ directory")
        print(f"Auto-discovered teams: {', '.join(args.teams)}")
    
    if len(args.teams) < 2:
        parser.error(f"At least 2 teams required, found {len(args.teams)}: {args.teams}")
    
    # Setup
    setup_logging(args.verbose)
    
    # Validate scenario exists
    scenario_file = items_dir / f"{args.scenario}.json"
    if not scenario_file.exists():
        print(f"Error: Scenario '{args.scenario}' not found at {scenario_file}")
        print("Available scenarios:", get_available_scenarios(items_dir))
        sys.exit(1)
    
    # Validate team prompts exist
    for team in args.teams:
        prompt_file = prompts_dir / f"{team}.txt"
        if not prompt_file.exists():
            print(f"Error: Team prompt '{team}' not found at {prompt_file}")
            print("Available teams:", get_available_teams(prompts_dir))
            sys.exit(1)
    
    # Build config
    llm_provider = os.getenv("LLM_PROVIDER", "google")
    
    config = GameConfig(
        scenario_file=str(scenario_file),
        team_prompts=args.teams,
        max_iterations=args.max_iterations,
        llm_provider=llm_provider,
        llm_base_url=args.llm_url,
        llm_model=args.llm_model,
        base_budget=int(os.getenv("BASE_BUDGET", "1500")),
        budget_per_team=int(os.getenv("BUDGET_PER_TEAM", "200"))
    )
    
    # Calculate dynamic budget
    starting_budget = config.calculate_starting_budget(len(args.teams))
    
    # Get display name for LLM
    if llm_provider == "google":
        llm_display = f"Google Gemini ({args.llm_model})"
    else:
        llm_display = f"Ollama ({args.llm_model}) @ {args.llm_url}"
    
    print("\n" + "=" * 60)
    print("WOLF OF ALLEGRO - AUCTION GAME")
    print("=" * 60)
    print(f"Scenario: {args.scenario}")
    print(f"Teams: {', '.join(args.teams)}")
    print(f"Starting Budget: {starting_budget} (1500 + {len(args.teams)} × 200)")
    print(f"Max Iterations: {args.max_iterations}")
    print(f"LLM: {llm_display}")
    print("=" * 60 + "\n")
    
    # Create session directory with timestamp and parameters
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scenario_short = args.scenario[:20]  # Limit length
    teams_short = "_".join(args.teams[:3])[:30]  # Max 3 teams, limit length
    session_name = f"{timestamp}_{scenario_short}_{teams_short}"
    session_dir = args.output / session_name
    session_dir.mkdir(parents=True, exist_ok=True)
    
    # Save run configuration
    config_path = session_dir / "run_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "scenario": args.scenario,
            "teams": args.teams,
            "starting_budget": starting_budget,
            "max_iterations": args.max_iterations,
            "llm_model": args.llm_model,
            "llm_url": args.llm_url
        }, f, indent=2)
    
    print(f"Session logs: {session_dir}\n")
    
    # Run game
    engine = None
    try:
        engine = AuctionEngine(config, prompts_dir, session_dir=session_dir)
        engine.__enter__()
        
        rankings = engine.run()
        
        # Calculate final rankings
        final_rankings_path = session_dir / "final_rankings.csv"
        export_results(rankings, final_rankings_path)
        
        print("\n" + "=" * 60)
        print("GAME COMPLETE!")
        print("=" * 60)
        print(f"\n🏆 WINNER: {rankings[0].team_name}")
        print(f"   Required items: {rankings[0].required_count}")
        print(f"   Total quality: {rankings[0].total_quality}")
        print(f"   Remaining budget: {rankings[0].remaining_budget}")
        print(f"\nAll logs saved to: {session_dir}")
        
    except KeyboardInterrupt:
        print("\n\nGame interrupted by user (Ctrl+C)")
        if engine:
            print("Saving partial results...")
            engine.save_session_logs()
            print(f"Partial logs saved to: {session_dir}")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Game error: {e}", exc_info=True)
        if engine:
            print("Saving partial results...")
            engine.save_session_logs()
            print(f"Partial logs saved to: {session_dir}")
        sys.exit(1)
    finally:
        if engine:
            engine.__exit__(None, None, None)


if __name__ == "__main__":
    main()
