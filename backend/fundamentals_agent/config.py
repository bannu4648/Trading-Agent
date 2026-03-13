"""
Configuration for the Fundamentals Agent.
"""
import os
from typing import Dict, Any


DEFAULT_CONFIG = {
    # LLM settings
    "llm_provider": os.getenv("LLM_PROVIDER", "ollama"),  # ollama, openai, anthropic, google
    "model": os.getenv("LLM_MODEL", "llama3.2"),  # For Ollama: llama3.2, mistral, etc.
    "temperature": 0.7,
    "max_tokens": 4000,
    "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),  # Ollama default URL
    
    # Agent settings
    "max_iterations": 5,
    "vendor": os.getenv("DATA_VENDOR", "yfinance"),  # yfinance, alpha_vantage
    
    # Debug
    "debug": False,
}


def get_llm_client(config: Dict[str, Any] = None):
    """
    Create an LLM client based on configuration.
    
    Args:
        config: Configuration dictionary
    
    Returns:
        LangChain LLM instance
    """
    if config is None:
        config = DEFAULT_CONFIG.copy()
    
    provider = config.get("llm_provider", "openai").lower()
    model = config.get("model", "gpt-4o-mini")
    temperature = config.get("temperature", 0.7)
    max_tokens = config.get("max_tokens", 4000)
    
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
        )
    
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
        
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
        )
    
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set.")
        
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            api_key=api_key,
        )
    
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        
        base_url = config.get("base_url", "http://localhost:11434")
        
        return ChatOllama(
            model=model,
            temperature=temperature,
            base_url=base_url,
        )
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Supported: ollama, openai, anthropic, google")
