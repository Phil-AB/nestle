"""
Base class for specialised document type extractors.

Each extractor receives the full Reducto output (fields, items, blocks) and
returns a dict of enhanced fields.  The extractor has full knowledge of the
target document's layout conventions and field semantics, which the generic
AI semantic enhancer cannot know.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class BaseDocumentExtractor(ABC):
    """
    Abstract base for specialised document type extractors.

    Subclasses implement `extract` with document-specific logic:
    - Custom LLM prompts that describe the document's actual layout
    - Knowledge of where totals live vs per-item rows
    - Label disambiguation (e.g. "Our Order No" vs "Your Order No")
    - Multi-section awareness (e.g. BOL totals block on page 2)

    All extractors MUST use structured outputs (Pydantic + `llm.with_structured_output`)
    to avoid field-naming non-determinism.
    """

    def __init__(self, llm_extraction, llm_resolution):
        """
        Args:
            llm_extraction: LLM bound to DocumentExtractionFields schema
            llm_resolution: LLM bound to SemanticResolutionFields schema
        """
        self.llm_extraction = llm_extraction
        self.llm_resolution = llm_resolution

    @abstractmethod
    async def extract(
        self,
        fields: Dict[str, Any],
        items: List[Dict],
        blocks: List[Dict],
        document_type: str,
    ) -> Dict[str, Any]:
        """
        Run specialised extraction and return enhanced fields dict.

        Args:
            fields:        Raw fields extracted by Reducto provider
            items:         Table row items extracted by Reducto provider
            blocks:        Raw text/content blocks from the document
            document_type: Canonical document type string

        Returns:
            Dict of enhanced fields (values are plain scalars — wrapping is done
            by the caller in ai_semantic_enhancer._wrap_fields).
        """

    # ──────────────────────────────────────────────────────────────────────────
    # Shared helpers available to all subclasses
    # ──────────────────────────────────────────────────────────────────────────

    def _val(self, v: Any) -> Any:
        """Unwrap {'value': ...} envelope if present."""
        if isinstance(v, dict) and "value" in v:
            return v["value"]
        return v

    def _is_empty(self, v: Any) -> bool:
        raw = self._val(v)
        return raw is None or str(raw).strip() in ("", "<empty>", "-", "—", "N/A")

    def _serialize_items(self, items: List[Dict], max_rows: int = 60) -> str:
        """Serialise table items to readable text for the LLM."""
        lines = []
        for i, item in enumerate(items[:max_rows]):
            if not isinstance(item, dict):
                continue
            parts = []
            for key, value in item.items():
                if key.startswith("_") or key in ("row_index", "table_bbox"):
                    continue
                v = self._val(value)
                if v is not None:
                    parts.append(f"{key}: {v}")
            if parts:
                lines.append(f"Row {i+1}: " + " | ".join(parts))
        return "\n".join(lines)

    def _serialize_blocks(self, blocks: List[Dict], max_blocks: int = 80) -> str:
        """Serialise content blocks to plain text for the LLM.

        Each block is prefixed with [Block N of M] so the LLM can reason about
        document position — Block 1 is the header/letterhead; the last block is
        typically footer legal text.
        """
        total = min(len(blocks), max_blocks)
        parts = []
        for i, block in enumerate(blocks[:max_blocks]):
            text = ""
            if isinstance(block, dict):
                text = block.get("content") or block.get("text") or block.get("value", "")
                text = str(text) if text else ""
            elif isinstance(block, str):
                text = block
            if text:
                parts.append(f"[Block {i + 1} of {total}]\n{text}")
        return "\n\n".join(parts)

    def _fields_summary(self, fields: Dict[str, Any], max_fields: int = 20) -> str:
        """Summarise already-extracted fields for the LLM context."""
        parts = []
        for k, v in list(fields.items())[:max_fields]:
            val = self._val(v)
            if val is not None:
                parts.append(f"{k}={val}")
        return ", ".join(parts) if parts else "none"

    def _all_fields_text(self, fields: Dict[str, Any]) -> str:
        """
        Render ALL raw extracted fields as 'key: value' lines for the LLM.

        Used when we need the LLM to see every field Reducto extracted,
        including cases where the article description was parsed as a field KEY
        (e.g. Reducto turns 'FFP 28% MQAV004F-1 25kg bag' into a column header
        key like 'ffp_28%_mqav004f_1_25kg_bag').
        """
        lines = []
        for k, v in fields.items():
            val = self._val(v)
            lines.append(f"{k}: {val}")
        return "\n".join(lines) if lines else "(none)"
