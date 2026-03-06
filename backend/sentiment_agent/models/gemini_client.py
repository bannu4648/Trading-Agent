"""
LLM client that works with multiple providers (Groq, DeepSeek, Gemini).

All agents just do `from sentiment_agent.models.gemini_client import gemini_client` and call
.generate() or .generate_json() -- they don't need to know which backend
is actually handling the request. The provider is picked from LLM_PROVIDER
in the .env file.

The client is lazy-initialized meaning it only actually connects to the
API on the first real call. This is important because tests mock everything
and we don't want them to fail just because there's no API key set up.
"""
import json
import re
import time
import logging
from sentiment_agent.config.settings import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Handles all LLM interactions. Lazy-init so tests don't need real keys."""

    def __init__(self):
        self.provider = settings.llm_provider.lower()
        self._client = None
        self._model = None

    def _ensure_initialized(self):
        """Set up the actual API client if we haven't already."""
        if self._client is not None:
            return

        logger.info(f"Initializing LLM client with provider: {self.provider}")

        if self.provider == "gemini":
            self._init_gemini()
        elif self.provider in ("groq", "deepseek"):
            self._init_openai_compatible()
        else:
            raise ValueError(
                f"Unknown LLM_PROVIDER: {self.provider}. "
                f"Supported: groq, deepseek, gemini"
            )

    def _init_gemini(self):
        from google import genai
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model

    def _init_openai_compatible(self):
        """Groq and DeepSeek both expose OpenAI-compatible endpoints."""
        from openai import OpenAI

        if self.provider == "groq":
            api_key = settings.groq_api_key
            base_url = "https://api.groq.com/openai/v1"
            self._model = settings.groq_model
            if not api_key:
                raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        elif self.provider == "deepseek":
            api_key = settings.deepseek_api_key
            base_url = "https://api.deepseek.com"
            self._model = settings.deepseek_model
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY is required when LLM_PROVIDER=deepseek")

        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, prompt: str, max_retries: int = 4) -> str:
        """Send a prompt and get text back. Has retry logic for rate limits."""
        self._ensure_initialized()
        if self.provider == "gemini":
            return self._generate_gemini(prompt, max_retries)
        else:
            return self._generate_openai(prompt, max_retries)

    def generate_json(self, prompt: str, max_retries: int = 4) -> dict:
        """Same as generate() but parses the response as JSON."""
        raw = self.generate(prompt, max_retries=max_retries)
        # strip markdown fences that LLMs sometimes wrap around JSON
        raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {raw[:500]}")
            raise ValueError(f"Invalid JSON from {self.provider}: {e}") from e

    def _generate_gemini(self, prompt: str, max_retries: int) -> str:
        delay = 15
        for attempt in range(max_retries):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                )
                return response.text.strip()
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    if attempt < max_retries - 1:
                        wait = delay * (2 ** attempt)
                        logger.warning(
                            f"Rate limit hit (attempt {attempt+1}/{max_retries}). "
                            f"Waiting {wait}s..."
                        )
                        time.sleep(wait)
                        continue
                logger.error(f"Gemini API error: {e}")
                raise

    def _generate_openai(self, prompt: str, max_retries: int) -> str:
        delay = 5
        for attempt in range(max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": "You are a financial sentiment analyst. Always respond with valid JSON when asked."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    if attempt < max_retries - 1:
                        wait = delay * (2 ** attempt)
                        logger.warning(
                            f"Rate limit hit (attempt {attempt+1}/{max_retries}). "
                            f"Waiting {wait}s..."
                        )
                        time.sleep(wait)
                        continue
                logger.error(f"{self.provider} API error: {e}")
                raise


# kept the name "gemini_client" so all the imports in agent files still work
gemini_client = LLMClient()
