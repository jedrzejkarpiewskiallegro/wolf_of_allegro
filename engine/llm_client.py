"""
LLM Client for communicating with local Ollama API.
"""

import httpx
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for making requests to local LLM API (Ollama-compatible)."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "llama3.2",
        timeout: float = 30.0
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        # Disable httpx debug logging
        httpx_logger = logging.getLogger("httpx")
        httpx_logger.setLevel(logging.WARNING)
        self._client = httpx.Client(timeout=timeout)
    
    def chat_completion(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7
    ) -> Optional[str]:
        """
        Send a chat completion request to the LLM.
        
        Args:
            system_prompt: The system prompt defining agent behavior
            user_message: The user message (game state context)
            temperature: Sampling temperature
            
        Returns:
            The assistant's response text, or None if request failed
        """
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": temperature,
            "max_tokens": 50  # We only need a single integer
        }
        
        try:
            response = self._client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from LLM API: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error to LLM API: {e}")
            return None
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return None
    
    def parse_bid_response(self, response: Optional[str]) -> int:
        """
        Parse the LLM response to extract a bid amount.
        
        The agent should return ONLY a single integer.
        If parsing fails, returns 0 (forfeit bid).
        
        Args:
            response: Raw response from LLM
            
        Returns:
            Parsed bid amount (0 if invalid)
        """
        if response is None:
            logger.warning("No response from LLM, defaulting to bid 0")
            return 0
        
        # Clean up response - remove any non-digit characters except minus
        cleaned = response.strip()
        
        # Try to extract just the first number found
        import re
        match = re.search(r'^-?\d+', cleaned)
        
        if match:
            try:
                bid = int(match.group())
                # Bids cannot be negative
                if bid < 0:
                    logger.warning(f"Negative bid {bid} converted to 0")
                    return 0
                return bid
            except ValueError:
                pass
        
        logger.warning(f"Could not parse bid from response: '{response}', defaulting to 0")
        return 0
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
