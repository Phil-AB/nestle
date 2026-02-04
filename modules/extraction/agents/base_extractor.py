"""
Base extraction agent using LangChain.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from shared.utils.config import settings
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class BaseExtractor(ABC):
    """
    Base class for document field extraction using LLMs.
    """

    def __init__(self, model_name: Optional[str] = None, temperature: float = 0.0):
        """
        Initialize extractor with LLM.

        Args:
            model_name: Model name (overrides config)
            temperature: LLM temperature (default: 0 for deterministic)
        """
        self.llm = self._get_llm(model_name, temperature)
        logger.info(f"Initialized {self.__class__.__name__} with {settings.LLM_PROVIDER}")

    def _get_llm(self, model_name: Optional[str], temperature: float):
        """Get LLM based on provider configuration."""
        provider = settings.LLM_PROVIDER

        if provider == "openai":
            return ChatOpenAI(
                model=model_name or settings.CUSTOM_LLM_MODEL or "gpt-4",
                temperature=temperature,
                api_key=settings.OPENAI_API_KEY,
            )
        elif provider == "anthropic":
            return ChatAnthropic(
                model=model_name or "claude-3-sonnet-20240229",
                temperature=temperature,
                api_key=settings.ANTHROPIC_API_KEY,
            )
        elif provider == "custom":
            # For custom LLM endpoints (e.g., Ollama)
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                base_url=settings.CUSTOM_LLM_ENDPOINT,
                model=model_name or settings.CUSTOM_LLM_MODEL,
                temperature=temperature,
                api_key="not-needed",  # Local models don't need API key
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    @abstractmethod
    def get_extraction_prompt(self) -> ChatPromptTemplate:
        """
        Get the extraction prompt template for this document type.

        Returns:
            ChatPromptTemplate for extraction
        """
        pass

    @abstractmethod
    def get_document_type(self) -> str:
        """
        Get the document type this extractor handles.

        Returns:
            Document type string
        """
        pass

    async def extract(
        self,
        raw_text: str,
        structured_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract fields from document.

        Args:
            raw_text: Raw text from document
            structured_data: Structured data from parser (optional)
            **kwargs: Additional context

        Returns:
            Extracted fields as dictionary
        """
        try:
            logger.debug(f"Extracting fields from {self.get_document_type()}")

            # Build prompt
            prompt = self.get_extraction_prompt()

            # Create chain
            chain = prompt | self.llm

            # Execute extraction
            context = {
                "document_text": raw_text,
                "structured_data": structured_data or {},
                **kwargs
            }

            result = await chain.ainvoke(context)

            # Parse result
            extracted = self._parse_llm_response(result.content)

            logger.info(
                f"Extracted {len(extracted)} fields from {self.get_document_type()}"
            )

            return extracted

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            raise

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM response to extract structured data.

        Args:
            response: Raw LLM response

        Returns:
            Parsed dictionary
        """
        import json
        import re

        # Try to find JSON in response
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to parse entire response as JSON
            json_str = response

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response[:500]}")
            # Return empty dict rather than failing
            return {}
