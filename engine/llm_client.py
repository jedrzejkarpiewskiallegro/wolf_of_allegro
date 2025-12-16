"""
LLM Client for communicating with LLM APIs.
Supports: Google Gemini (via google-genai) and Ollama (OpenAI-compatible).
"""

import httpx
import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Client for making requests to LLM APIs.
    Supports Google Gemini and Ollama providers.
    """
    
    def __init__(
        self,
        provider: str = "google",
        model: str = None,
        base_url: str = "http://localhost:11434/v1",
        timeout: float = 60.0
    ):
        """
        Initialize LLM client.
        
        Args:
            provider: "google" or "ollama"
            model: Model name (required, from .env LLM_MODEL)
            base_url: Base URL for Ollama API (ignored for Google)
            timeout: Request timeout in seconds
        """
        self.provider = provider.lower()
        self.model = model or os.getenv("LLM_MODEL")
        if not self.model:
            raise ValueError("LLM_MODEL not set. Set it in .env file.")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        
        # Disable verbose logging from dependencies
        httpx_logger = logging.getLogger("httpx")
        httpx_logger.setLevel(logging.WARNING)
        
        genai_logger = logging.getLogger("google.genai")
        genai_logger.setLevel(logging.WARNING)
        
        if self.provider == "google":
            self._init_google()
        elif self.provider == "ollama":
            self._init_ollama()
        else:
            raise ValueError(f"Unsupported provider: {provider}. Use 'google' or 'ollama'.")
        
        logger.info(f"LLMClient initialized: {self.get_display_name()}")
    
    def _init_google(self):
        """Initialize Google Gemini client."""
        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai package not found. Install with: pip install google-genai"
            )
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key or api_key == "your_google_api_key_here":
            raise ValueError(
                "GOOGLE_API_KEY not set in environment. "
                "Get your key from https://aistudio.google.com/"
            )
        
        self._google_client = genai.Client(api_key=api_key)
        self._http_client = None
    
    def _init_ollama(self):
        """Initialize Ollama HTTP client."""
        self._http_client = httpx.Client(timeout=self.timeout)
        self._google_client = None
    
    def get_display_name(self) -> str:
        """Get human-readable provider and model name."""
        if self.provider == "google":
            return f"Google Gemini ({self.model})"
        elif self.provider == "ollama":
            return f"Ollama ({self.model}) @ {self.base_url}"
        return f"{self.provider} ({self.model})"
    
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
        if self.provider == "google":
            return self._chat_google(system_prompt, user_message, temperature)
        elif self.provider == "ollama":
            return self._chat_ollama(system_prompt, user_message, temperature)
        return None
    
    def _chat_google(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float
    ) -> Optional[str]:
        """Google Gemini API using google-genai library."""
        from google import genai
        from google.genai import types
        
        try:
            response = self._google_client.models.generate_content(
                model=self.model,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                    max_output_tokens=50,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    )
                )
            )
            
            if response.text:
                return response.text.strip()
            
            logger.warning("Empty response from Google Gemini")
            return None
            
        except Exception as e:
            logger.error(f"Google Gemini API error: {e}")
            return None
    
    def _chat_ollama(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float
    ) -> Optional[str]:
        """Ollama OpenAI-compatible API."""
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": temperature,
            "max_tokens": 50
        }
        
        try:
            response = self._http_client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Ollama request error: {e}")
            return None
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse Ollama response: {e}")
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
        
        # Clean up response
        cleaned = response.strip()
        
        # Try to extract just the first number found
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
        if self._http_client:
            self._http_client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
