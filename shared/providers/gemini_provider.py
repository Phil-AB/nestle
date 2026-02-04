"""
Google Gemini Provider for Vision and Text Tasks.

Unified provider for Gemini API supporting:
- Vision tasks (PDF/image analysis, field detection, OCR)
- Text tasks (structured extraction, reasoning, validation)
- Multimodal tasks (combining vision and text)

This replaces the form_generator-specific GeminiVisionProvider with a
shared implementation usable by all modules.
"""

import os
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from io import BytesIO
from dataclasses import dataclass
import logging

try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
except ImportError:
    genai = None

from PIL import Image
import pdfplumber

from shared.providers.base_provider import BaseProvider, ProviderConfig, ProviderResponse
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class GeminiVisionResult:
    """
    Result from Gemini vision analysis.

    Attributes:
        text: Generated text response
        confidence: Confidence score (0.0-1.0)
        metadata: Additional metadata (tokens, finish_reason, etc.)
    """
    text: str
    confidence: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


class GeminiProvider(BaseProvider):
    """
    Google Gemini provider for vision and text tasks.

    Capabilities:
    - PDF/image analysis
    - Form field detection
    - OCR and text extraction
    - Structured data extraction
    - Multimodal reasoning

    Example (Vision):
        >>> config = ProviderConfig(
        ...     provider_name="gemini",
        ...     api_key=os.getenv("GEMINI_API_KEY"),
        ...     model="gemini-1.5-flash",
        ...     temperature=0.1
        ... )
        >>> provider = GeminiProvider(config)
        >>> result = await provider.analyze_image(
        ...     image_path="form.png",
        ...     prompt="Detect all form fields"
        ... )

    Example (Text):
        >>> result = await provider.generate_text(
        ...     prompt="Extract invoice data from: [text]"
        ... )
    """

    def _validate_config(self) -> None:
        """Validate Gemini provider configuration."""
        if genai is None:
            raise ImportError(
                "google-generativeai not installed. "
                "Install with: pip install google-generativeai"
            )

        if not self.config.api_key:
            raise ValueError(
                "Gemini API key required. Set GEMINI_API_KEY environment variable "
                "or pass api_key in config"
            )

        # Validate model
        valid_models = [
            "gemini-pro",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
        ]
        if not any(self.config.model.startswith(m) for m in valid_models):
            self.logger.warning(
                f"Model {self.config.model} may not be supported. "
                f"Valid models: {', '.join(valid_models)}"
            )

    def _initialize_client(self) -> None:
        """Initialize Gemini client."""
        # Configure Gemini API
        genai.configure(api_key=self.config.api_key)

        # Initialize model with safety settings
        self.model = genai.GenerativeModel(
            model_name=self.config.model,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )

        self.logger.info(f"Initialized Gemini model: {self.config.model}")

    async def health_check(self) -> bool:
        """
        Check Gemini API health.

        Returns:
            True if API is accessible

        Raises:
            Exception: If health check fails
        """
        try:
            # Try a simple generation
            response = self.model.generate_content("ping")
            self.logger.debug(f"Gemini health check passed: {response.text[:50]}")
            return True
        except Exception as e:
            self.logger.error(f"Gemini health check failed: {e}")
            raise

    # ==========================================================================
    # TEXT GENERATION
    # ==========================================================================

    async def generate_text(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> GeminiVisionResult:
        """
        Generate text using Gemini.

        Args:
            prompt: Text prompt
            temperature: Override default temperature
            max_tokens: Maximum output tokens

        Returns:
            GeminiVisionResult with generated text
        """
        async def _generate():
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature or self.config.temperature,
                    "max_output_tokens": max_tokens or 8192,
                    "top_p": 0.8,
                    "top_k": 40,
                }
            )
            return response

        result = await self._retry_operation(_generate, "generate_text")

        if not result.success:
            raise RuntimeError(f"Text generation failed: {result.error}")

        response = result.data

        return GeminiVisionResult(
            text=response.text,
            metadata={
                "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else None,
                "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else None,
                "finish_reason": response.candidates[0].finish_reason if response.candidates else None
            }
        )

    # ==========================================================================
    # VISION ANALYSIS
    # ==========================================================================

    async def analyze_image(
        self,
        image: Union[str, Path, Image.Image, bytes],
        prompt: str,
        temperature: Optional[float] = None
    ) -> GeminiVisionResult:
        """
        Analyze image with Gemini vision.

        Args:
            image: Image path, PIL Image, or bytes
            prompt: Analysis prompt
            temperature: Override default temperature

        Returns:
            GeminiVisionResult with analysis text
        """
        # Convert image to PIL Image if needed
        pil_image = self._load_image(image)

        async def _analyze():
            response = self.model.generate_content(
                [prompt, pil_image],
                generation_config={
                    "temperature": temperature or self.config.temperature,
                    "max_output_tokens": 8192,
                    "top_p": 0.8,
                    "top_k": 40,
                }
            )
            return response

        result = await self._retry_operation(_analyze, "analyze_image")

        if not result.success:
            raise RuntimeError(f"Image analysis failed: {result.error}")

        response = result.data

        return GeminiVisionResult(
            text=response.text,
            metadata={
                "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else None,
                "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else None,
            }
        )

    async def analyze_pdf(
        self,
        pdf_path: Union[str, Path],
        prompt: str,
        page_num: Optional[int] = None,
        dpi: int = 300
    ) -> GeminiVisionResult:
        """
        Analyze PDF with Gemini vision.

        Args:
            pdf_path: Path to PDF file
            prompt: Analysis prompt
            page_num: Specific page to analyze (None = first page)
            dpi: Resolution for PDF rendering

        Returns:
            GeminiVisionResult with analysis text
        """
        # Convert PDF page to image
        image = self._pdf_to_image(pdf_path, page_num or 0, dpi)

        # Analyze image
        return await self.analyze_image(image, prompt)

    async def analyze_pdf_multipage(
        self,
        pdf_path: Union[str, Path],
        prompt: str,
        pages: Optional[List[int]] = None,
        dpi: int = 300
    ) -> List[GeminiVisionResult]:
        """
        Analyze multiple PDF pages.

        Args:
            pdf_path: Path to PDF file
            prompt: Analysis prompt
            pages: List of page numbers (None = all pages)
            dpi: Resolution for PDF rendering

        Returns:
            List of GeminiVisionResult (one per page)
        """
        pdf_path = Path(pdf_path)

        # Get page count
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)

        if pages is None:
            pages = list(range(page_count))

        results = []
        for page_num in pages:
            self.logger.debug(f"Analyzing page {page_num + 1}/{page_count}")
            result = await self.analyze_pdf(pdf_path, prompt, page_num, dpi)
            results.append(result)

        return results

    # ==========================================================================
    # STRUCTURED EXTRACTION
    # ==========================================================================

    async def extract_json(
        self,
        image: Union[str, Path, Image.Image],
        prompt: str,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Extract structured JSON from image.

        Args:
            image: Image to analyze
            prompt: Extraction prompt (should request JSON format)
            temperature: Override default temperature

        Returns:
            Parsed JSON dictionary

        Raises:
            ValueError: If response is not valid JSON
        """
        import json
        import re

        result = await self.analyze_image(image, prompt, temperature)

        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'```json\s*(.*?)\s*```', result.text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            # Try to find JSON object directly
            json_match = re.search(r'\{.*\}', result.text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            else:
                # Try array
                json_match = re.search(r'\[.*\]', result.text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(0)
                else:
                    raise ValueError(f"No JSON found in response: {result.text[:200]}")

        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON: {e}\n{json_text[:500]}")
            raise ValueError(f"Invalid JSON in response: {e}")

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _load_image(self, image: Union[str, Path, Image.Image, bytes]) -> Image.Image:
        """
        Load image from various formats.

        Args:
            image: Image path, PIL Image, or bytes

        Returns:
            PIL Image

        Raises:
            ValueError: If image format not supported
        """
        if isinstance(image, Image.Image):
            return image

        elif isinstance(image, (str, Path)):
            return Image.open(image)

        elif isinstance(image, bytes):
            return Image.open(BytesIO(image))

        else:
            raise ValueError(f"Unsupported image type: {type(image)}")

    def _pdf_to_image(
        self,
        pdf_path: Union[str, Path],
        page_num: int = 0,
        dpi: int = 300
    ) -> Image.Image:
        """
        Convert PDF page to image.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (0-indexed)
            dpi: Resolution

        Returns:
            PIL Image
        """
        try:
            from pdf2image import convert_from_path

            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=page_num + 1,
                last_page=page_num + 1
            )
            return images[0]

        except ImportError:
            # Fallback to pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                page = pdf.pages[page_num]
                return page.to_image(resolution=dpi).original

    def get_page_info(self, pdf_path: Union[str, Path], page_num: int = 0) -> Dict[str, Any]:
        """
        Get PDF page metadata.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (0-indexed)

        Returns:
            Page metadata dictionary
        """
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_num]
            return {
                "width": page.width,
                "height": page.height,
                "page_num": page_num,
                "page_count": len(pdf.pages)
            }
