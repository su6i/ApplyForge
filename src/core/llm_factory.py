from __future__ import annotations

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser

from src.core.settings import (
    OPENAI_API_KEY,
    DEEPSEEK_API_KEY,
    GEMINI_API_KEY,
    LLM_MODEL,
    FALLBACK_MODEL,
)
from src.core.logger import logger

def get_llm(temperature: float = 0, **kwargs) -> any:
    """
    Get the primary LLM (DeepSeek/OpenAI) with Gemini as an automatic fallback.
    """
    primary = None
    fallback = None

    # Identify primary
    if DEEPSEEK_API_KEY:
        logger.debug(f"Primary LLM: DeepSeek ({LLM_MODEL})")
        primary = ChatOpenAI(
            model_name=LLM_MODEL,
            openai_api_key=DEEPSEEK_API_KEY,
            openai_api_base="https://api.deepseek.com",
            temperature=temperature,
            **kwargs
        )
    elif OPENAI_API_KEY:
        logger.debug(f"Primary LLM: OpenAI ({LLM_MODEL})")
        primary = ChatOpenAI(
            model_name=LLM_MODEL,
            openai_api_key=OPENAI_API_KEY,
            temperature=temperature,
            **kwargs
        )

    # Identify fallback
    if GEMINI_API_KEY:
        logger.debug(f"Fallback LLM: Gemini ({FALLBACK_MODEL})")
        fallback = ChatGoogleGenerativeAI(
            model=FALLBACK_MODEL,
            google_api_key=GEMINI_API_KEY,
            temperature=temperature,
            **kwargs
        )

    if not primary and not fallback:
        raise ValueError("No LLM API keys found (DeepSeek, OpenAI, or Gemini).")

    if primary and fallback:
        return primary.with_fallbacks([fallback])
    
    return primary or fallback

def create_chain(prompt: any, temperature: float = 0, **kwargs):
    """Create a LangChain chain with automatic provider fallback."""
    llm = get_llm(temperature=temperature, **kwargs)
    return prompt | llm | StrOutputParser()
