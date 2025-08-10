import os
import openai
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class OpenRouterConfig:
    """Configuration for OpenRouter API client."""

    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    default_model: str = "anthropic/claude-3.5-sonnet"
    max_tokens: int = 1000
    temperature: float = 0.7


class OpenRouterClient:
    """Client for interacting with OpenRouter.ai LLM models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        config: Optional[OpenRouterConfig] = None,
    ):
        """Initialize the OpenRouter client.

        Args:
            api_key: API key for OpenRouter (can also be set via env var)
            model: Model to use (defaults to config default_model)
            config: Configuration object containing API key and settings
        """
        if config:
            self.config = config
        else:
            api_key = api_key or os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENROUTER_API_KEY not found in environment variables or parameters"
                )

            self.config = OpenRouterConfig(
                api_key=api_key, default_model=model or "anthropic/claude-3.5-sonnet"
            )

        self.client = openai.OpenAI(
            api_key=self.config.api_key, base_url=self.config.base_url
        )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Generate text using the specified model.

        This method provides a simplified interface for the pipeline.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Generated text response
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        result = self.chat_completion(
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            **kwargs,
        )

        if result["success"]:
            return result["content"]
        else:
            raise Exception(f"Generation failed: {result['error']}")

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate a chat completion using OpenRouter models.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model to use (defaults to config default_model)
            temperature: Sampling temperature (defaults to config temperature)
            max_tokens: Maximum tokens to generate (defaults to config max_tokens)
            **kwargs: Additional parameters to pass to the API

        Returns:
            API response dictionary
        """
        try:
            response = self.client.chat.completions.create(
                model=model or self.config.default_model,
                messages=messages,
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
                **kwargs,
            )
            return {
                "success": True,
                "response": response,
                "content": response.choices[0].message.content,
                "usage": response.usage.dict() if response.usage else None,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": None,
                "content": None,
                "usage": None,
            }

    def text_completion(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate text completion using OpenRouter models.

        Args:
            prompt: Text prompt to complete
            model: Model to use (defaults to config default_model)
            temperature: Sampling temperature (defaults to config temperature)
            max_tokens: Maximum tokens to generate (defaults to config max_tokens)
            **kwargs: Additional parameters to pass to the API

        Returns:
            API response dictionary
        """
        try:
            response = self.client.completions.create(
                model=model or self.config.default_model,
                prompt=prompt,
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
                **kwargs,
            )
            return {
                "success": True,
                "response": response,
                "content": response.choices[0].text,
                "usage": response.usage.dict() if response.usage else None,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": None,
                "content": None,
                "usage": None,
            }

    def list_models(self) -> Dict[str, Any]:
        """List available models from OpenRouter.

        Returns:
            Dictionary containing available models or error information
        """
        try:
            response = self.client.models.list()
            return {
                "success": True,
                "models": [model.dict() for model in response.data],
                "error": None,
            }
        except Exception as e:
            return {"success": False, "models": None, "error": str(e)}

    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """Get information about a specific model.

        Args:
            model_id: ID of the model to get info for

        Returns:
            Dictionary containing model information or error details
        """
        try:
            response = self.client.models.retrieve(model_id)
            return {"success": True, "model": response.dict(), "error": None}
        except Exception as e:
            return {"success": False, "model": None, "error": str(e)}


def create_client_from_env() -> OpenRouterClient:
    """Create an OpenRouter client using environment variables.

    Required environment variables:
    - OPENROUTER_API_KEY: Your OpenRouter API key

    Returns:
        Configured OpenRouterClient instance
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is required")

    config = OpenRouterConfig(api_key=api_key)
    return OpenRouterClient(config)


# Example usage
if __name__ == "__main__":
    # Example 1: Using environment variable
    try:
        client = create_client_from_env()

        # Chat completion example
        messages = [{"role": "user", "content": "Hello! How are you today?"}]

        result = client.chat_completion(messages)
        if result["success"]:
            print(f"Response: {result['content']}")
        else:
            print(f"Error: {result['error']}")

    except ValueError as e:
        print(f"Configuration error: {e}")

    # Example 2: Using custom configuration
    # config = OpenRouterConfig(
    #     api_key="your-api-key-here",
    #     default_model="anthropic/claude-3.5-sonnet",
    #     temperature=0.8
    # )
    # client = OpenRouterClient(config)
