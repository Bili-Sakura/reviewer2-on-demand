# OpenRouter LLM Client

This module provides a Python client for interacting with LLM models through [OpenRouter.ai](https://openrouter.ai/) using the `openai` package.

## Features

- **Chat Completions**: Generate conversational responses using chat-based models
- **Text Completions**: Generate text completions for prompts
- **Model Management**: List available models and get model information
- **Error Handling**: Comprehensive error handling with detailed response objects
- **Configuration**: Flexible configuration with sensible defaults

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Set your OpenRouter API key as an environment variable:
```bash
export OPENROUTER_API_KEY="your-api-key-here"
```

## Quick Start

### Basic Usage

```python
from src.llms import create_client_from_env

# Create client using environment variable
client = create_client_from_env()

# Chat completion
messages = [
    {"role": "user", "content": "Hello! How are you today?"}
]

result = client.chat_completion(messages)
if result["success"]:
    print(f"Response: {result['content']}")
else:
    print(f"Error: {result['error']}")
```

### Custom Configuration

```python
from src.llms import OpenRouterClient, OpenRouterConfig

config = OpenRouterConfig(
    api_key="your-api-key-here",
    default_model="anthropic/claude-3.5-sonnet",
    temperature=0.8,
    max_tokens=2000
)

client = OpenRouterClient(config)
```

## Available Models

OpenRouter provides access to various LLM models including:

- **Anthropic**: Claude 3.5 Sonnet, Claude 3 Haiku
- **OpenAI**: GPT-4, GPT-3.5 Turbo
- **Google**: Gemini Pro, Gemini Flash
- **Meta**: Llama 3.1, Code Llama
- **Mistral**: Mistral 7B, Mixtral 8x7B

## API Methods

### `chat_completion(messages, model=None, temperature=None, max_tokens=None, **kwargs)`

Generate chat completions using conversation messages.

**Parameters:**
- `messages`: List of message dictionaries with 'role' and 'content'
- `model`: Model to use (defaults to config default_model)
- `temperature`: Sampling temperature (0.0 to 2.0)
- `max_tokens`: Maximum tokens to generate
- `**kwargs`: Additional OpenAI API parameters

**Returns:** Dictionary with success status, response content, and usage information

### `text_completion(prompt, model=None, temperature=None, max_tokens=None, **kwargs)`

Generate text completions for prompts.

**Parameters:**
- `prompt`: Text prompt to complete
- `model`: Model to use (defaults to config default_model)
- `temperature`: Sampling temperature (0.0 to 2.0)
- `max_tokens`: Maximum tokens to generate
- `**kwargs`: Additional OpenAI API parameters

**Returns:** Dictionary with success status, response content, and usage information

### `list_models()`

List all available models from OpenRouter.

**Returns:** Dictionary with success status and list of available models

### `get_model_info(model_id)`

Get detailed information about a specific model.

**Parameters:**
- `model_id`: ID of the model to get info for

**Returns:** Dictionary with success status and model information

## Configuration

The `OpenRouterConfig` class allows you to customize:

- `api_key`: Your OpenRouter API key (required)
- `base_url`: API base URL (defaults to OpenRouter API)
- `default_model`: Default model to use for completions
- `max_tokens`: Default maximum tokens for completions
- `temperature`: Default temperature for completions

## Error Handling

All methods return a dictionary with a `success` boolean field. When `success` is `False`, the `error` field contains the error message.

## Examples

### Multi-turn Conversation

```python
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is the capital of France?"},
    {"role": "assistant", "content": "The capital of France is Paris."},
    {"role": "user", "content": "Tell me more about it."}
]

result = client.chat_completion(messages, temperature=0.3)
```

### Text Generation

```python
prompt = "Write a short story about a robot learning to paint:"

result = client.text_completion(
    prompt, 
    model="anthropic/claude-3-haiku",
    max_tokens=500,
    temperature=0.9
)
```

### List Available Models

```python
models_result = client.list_models()
if models_result["success"]:
    for model in models_result["models"]:
        print(f"Model: {model['id']} - {model['object']}")
```

## Getting an API Key

1. Visit [OpenRouter.ai](https://openrouter.ai/)
2. Sign up for an account
3. Navigate to your API keys section
4. Create a new API key
5. Set it as an environment variable: `OPENROUTER_API_KEY`

## Rate Limits and Pricing

OpenRouter pricing varies by model. Check their [pricing page](https://openrouter.ai/pricing) for current rates and rate limits.

## Support

For issues with the OpenRouter API, visit their [documentation](https://openrouter.ai/docs) or [support](https://openrouter.ai/support).
