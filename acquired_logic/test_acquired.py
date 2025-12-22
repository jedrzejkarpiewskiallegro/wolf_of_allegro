"""
Test script for debugging LLM agent responses.
Tests a single response using prompt.txt and game_state.txt in this folder.

Usage: python test_acquired.py
"""

import sys
import re
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from engine.llm_client import LLMClient


def load_prompt() -> str:
    """Load system prompt from prompt.txt"""
    prompt_file = Path(__file__).parent / "prompt.txt"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Brak pliku: {prompt_file}")
    return prompt_file.read_text(encoding="utf-8")


def load_game_state() -> str:
    """Load game state from game_state.txt"""
    game_state_file = Path(__file__).parent / "game_state.txt"
    if not game_state_file.exists():
        raise FileNotFoundError(f"Brak pliku: {game_state_file}")
    return game_state_file.read_text(encoding="utf-8")


def parse_bid(response: str) -> int:
    """
    Parse bid amount from LLM response.
    Tries to extract the first integer from response.
    """
    if not response:
        return 0
    
    # Try to find first number in response
    numbers = re.findall(r'\d+', response)
    if numbers:
        return int(numbers[0])
    
    return 0


def main():
    print("=" * 60)
    print("TEST ACQUIRED LOGIC - Multiple Response Test")
    print("=" * 60)
    
    # Load files
    print("\n📄 Loading prompt.txt...")
    system_prompt = load_prompt()
    print(f"   Prompt length: {len(system_prompt)} chars")
    
    print("\n📄 Loading game_state.txt...")
    game_state = load_game_state()
    print(f"   Game state length: {len(game_state)} chars")
    
    # Initialize LLM client
    print("\n🤖 Initializing LLM client...")
    try:
        client = LLMClient()
        print(f"   Provider: {client.get_display_name()}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return 1
    
    # Run 10 tests
    NUM_TESTS = 10
    results = []
    
    print(f"\n🔄 Running {NUM_TESTS} tests...")
    print("=" * 60)
    
    for i in range(1, NUM_TESTS + 1):
        print(f"\n[Test {i}/{NUM_TESTS}]", end=" ")
        
        try:
            response = client.chat_completion(
                system_prompt=system_prompt,
                user_message=game_state,
                temperature=1.5
            )
            
            bid = parse_bid(response)
            results.append({
                "test_num": i,
                "response": response,
                "bid": bid,
                "success": response is not None
            })
            
            print(f"Bid: {bid:>4d} | Response: {response[:50]}..." if response else "Bid: 0 (empty)")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({
                "test_num": i,
                "response": None,
                "bid": 0,
                "success": False,
                "error": str(e)
            })
    
    client.close()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    
    successful = [r for r in results if r["success"]]
    bids = [r["bid"] for r in successful]
    
    print(f"\nSuccessful responses: {len(successful)}/{NUM_TESTS}")
    
    if bids:
        print(f"\nBid statistics:")
        print(f"   Min: {min(bids)}")
        print(f"   Max: {max(bids)}")
        print(f"   Avg: {sum(bids) / len(bids):.1f}")
        print(f"   Unique values: {len(set(bids))}")
        
        # Count bid frequencies
        from collections import Counter
        bid_counts = Counter(bids)
        print(f"\nBid distribution:")
        for bid, count in sorted(bid_counts.items()):
            bar = "█" * count
            print(f"   {bid:>4d}: {bar} ({count}x)")
    
    # Show all responses
    print("\n" + "=" * 60)
    print("📝 ALL RESPONSES")
    print("=" * 60)
    for r in results:
        print(f"\n[Test {r['test_num']}] Bid: {r['bid']}")
        print(f"Response: {r['response']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
