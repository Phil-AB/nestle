"""
CET (Common External Tariff) File Service

Loads and queries the CET file for HS code validation.
The CET file contains:
- Column C: Description of goods
- Column E: HS Code (ID)
- Rate columns: Duty rates in percentages

Used for validating HS codes against official tariff schedules.
"""

import csv
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from functools import lru_cache
from decimal import Decimal
from datetime import datetime, timedelta

from shared.utils.logger import get_logger

logger = get_logger(__name__)

# Resolve project root relative to this file:
# modules/validation_engine/services/ -> modules/validation_engine/ -> modules/ -> project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class CETFileService:
    """
    Service for loading and querying CET (Common External Tariff) file

    The CET file is the official tariff schedule containing:
    - HS codes (Harmonized System codes)
    - Descriptions of goods
    - Duty rates
    - Statistical codes

    Features:
    - Loads CET from CSV/Excel
    - Caches CET data in memory
    - Fast HS code lookup
    - Fuzzy description matching
    - Duty rate retrieval
    """

    _instance = None
    _cet_data: Optional[pd.DataFrame] = None
    _cet_index: Optional[Dict[str, Dict[str, Any]]] = None
    _last_loaded: Optional[datetime] = None
    _cache_ttl: timedelta = timedelta(hours=24)

    def __new__(cls):
        """Singleton pattern - only one instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize CET File Service"""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._config = self._load_config()
            logger.info("CET File Service initialized")

    def _load_config(self) -> Dict[str, Any]:
        """
        Load CET configuration

        Returns:
            Configuration dictionary
        """
        # Default configuration — use absolute path so it resolves regardless of CWD
        config = {
            "cet_file_path": str(_PROJECT_ROOT / "config" / "data" / "CET_Ghana.csv"),
            "columns": {
                "hs_code": "E",  # Column E: HS Code ID
                "description": "C",  # Column C: Description
                "duty_rate": "Rate",  # Rate column
            },
            "cache_ttl_hours": 24,
            "encoding": "utf-8",
        }

        # Try to load from config file
        try:
            import yaml
            config_path = _PROJECT_ROOT / "config" / "validation" / "cet_integration.yaml"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    user_config = yaml.safe_load(f)
                    config.update(user_config.get("cet_integration", {}))
                    logger.info(f"Loaded CET config from {config_path}")
        except Exception as e:
            logger.warning(f"Could not load CET config file: {e}. Using defaults.")

        return config

    def load_cet_file(self, file_path: Optional[str] = None, force_reload: bool = False) -> bool:
        """
        Load CET file from CSV/Excel

        Args:
            file_path: Path to CET file (if None, use config path)
            force_reload: Force reload even if cached

        Returns:
            True if loaded successfully
        """
        # Check if already loaded and not expired
        if not force_reload and self._cet_data is not None and self._last_loaded:
            age = datetime.now() - self._last_loaded
            if age < self._cache_ttl:
                logger.debug(f"Using cached CET data (age: {age.total_seconds():.0f}s)")
                return True

        # Get file path
        if file_path is None:
            file_path = self._config.get("cet_file_path")

        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"CET file not found: {file_path}")
            return False

        try:
            # Load based on file extension
            if file_path.suffix.lower() == '.csv':
                self._cet_data = pd.read_csv(
                    file_path,
                    encoding=self._config.get("encoding", "utf-8")
                )
            elif file_path.suffix.lower() in ['.xlsx', '.xls']:
                self._cet_data = pd.read_excel(file_path)
            else:
                logger.error(f"Unsupported file format: {file_path.suffix}")
                return False

            # Build index for fast lookup
            self._build_index()

            self._last_loaded = datetime.now()
            logger.info(
                f"CET file loaded successfully: {len(self._cet_data)} entries from {file_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Error loading CET file: {e}", exc_info=True)
            return False

    def _build_index(self):
        """Build index for fast HS code lookup"""
        if self._cet_data is None:
            return

        self._cet_index = {}

        # Get column mappings
        hs_code_col = self._config["columns"].get("hs_code", "E")
        description_col = self._config["columns"].get("description", "C")
        duty_rate_col = self._config["columns"].get("duty_rate", "Rate")

        # Index by HS code
        for idx, row in self._cet_data.iterrows():
            try:
                hs_code = str(row.get(hs_code_col, "")).strip()
                if not hs_code or hs_code == "nan":
                    continue

                # Normalize HS code (remove dots, spaces)
                hs_code_normalized = hs_code.replace(".", "").replace(" ", "")

                # Extract data
                description = str(row.get(description_col, "")).strip()
                duty_rate_str = str(row.get(duty_rate_col, "0")).strip()

                # Parse duty rate
                try:
                    # Remove % sign if present
                    duty_rate_str = duty_rate_str.replace("%", "").strip()
                    duty_rate = Decimal(duty_rate_str) if duty_rate_str and duty_rate_str != "nan" else Decimal("0")
                except:
                    duty_rate = Decimal("0")

                self._cet_index[hs_code_normalized] = {
                    "hs_code": hs_code,
                    "hs_code_normalized": hs_code_normalized,
                    "description": description,
                    "duty_rate": duty_rate,
                    "duty_rate_percent": float(duty_rate),
                    "raw_data": row.to_dict()
                }

            except Exception as e:
                logger.warning(f"Error indexing row {idx}: {e}")
                continue

        logger.info(f"CET index built: {len(self._cet_index)} HS codes indexed")

    def get_hs_code_info(self, hs_code: str) -> Optional[Dict[str, Any]]:
        """
        Get information for an HS code

        Args:
            hs_code: HS code (e.g., "1234.56" or "123456")

        Returns:
            Dictionary with HS code info or None if not found
        """
        if not self._ensure_loaded():
            return None

        # Normalize HS code
        hs_code_normalized = hs_code.replace(".", "").replace(" ", "").strip()

        # Lookup in index
        return self._cet_index.get(hs_code_normalized)

    def verify_hs_code(self, hs_code: str) -> bool:
        """
        Verify if HS code exists in CET

        Args:
            hs_code: HS code to verify

        Returns:
            True if HS code exists in CET
        """
        info = self.get_hs_code_info(hs_code)
        return info is not None

    def get_duty_rate(self, hs_code: str) -> Optional[Decimal]:
        """
        Get duty rate for an HS code

        Args:
            hs_code: HS code

        Returns:
            Duty rate as Decimal (percentage) or None if not found
        """
        info = self.get_hs_code_info(hs_code)
        return info.get("duty_rate") if info else None

    def get_description(self, hs_code: str) -> Optional[str]:
        """
        Get description for an HS code

        Args:
            hs_code: HS code

        Returns:
            Description or None if not found
        """
        info = self.get_hs_code_info(hs_code)
        return info.get("description") if info else None

    def verify_description_match(
        self,
        hs_code: str,
        provided_description: str,
        similarity_threshold: float = 0.6
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Verify if provided description matches CET description

        Args:
            hs_code: HS code
            provided_description: Description from document
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            Tuple of (matches, similarity_score, cet_description)
        """
        cet_info = self.get_hs_code_info(hs_code)

        if not cet_info:
            return False, 0.0, None

        cet_description = cet_info.get("description", "")

        # Calculate similarity using simple word overlap
        similarity = self._calculate_similarity(provided_description, cet_description)

        matches = similarity >= similarity_threshold

        return matches, similarity, cet_description

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using enhanced word overlap with
        abbreviation expansion and keyword weighting.

        Handles cases like:
        - "FFP 28%" matching "Fat Filled Powder" (abbreviation expansion)
        - "MQAV004F-1 25KG BAG" partially matching "food preparations"
          (product terms are weighted)

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0-1)
        """
        if not text1 or not text2:
            return 0.0

        # Normalize
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()

        if text1 == text2:
            return 1.0

        # Expand common trade abbreviations so that "FFP" matches
        # "fat filled powder", "BG"/"BAG" match, etc.
        _EXPANSIONS = {
            "ffp": {"fat filled powder"},
            "wmp": {"whole milk powder"},
            "smp": {"skimmed milk powder"},
            "fcmp": {"full cream milk powder"},
            "veg": {"vegetable"},
            "min": {"mineral", "minerals"},
            "vit": {"vitamin", "vitamins"},
            "enr": {"enriched"},
            "kg": set(),   # unit — skip
            "bg": {"bag", "bags"},
            "bag": {"bag", "bags"},
            "mt": {"metric ton"},
        }

        def _expand_word(w: str) -> set:
            """Return the word itself plus any expansion terms."""
            expansions = _EXPANSIONS.get(w, set())
            return {w} | expansions

        # Tokenize and expand
        import re
        words1_raw = set(re.findall(r'[a-z]+', text1))
        words2_raw = set(re.findall(r'[a-z]+ text2'))

        words1 = set()
        words2 = set()
        for w in words1_raw:
            words1 |= _expand_word(w)
        for w in words2_raw:
            words2 |= _expand_word(w)

        # Also add numeric tokens (e.g. "28" for 28% fat content)
        nums1 = set(re.findall(r'\d+', text1))
        nums2 = set(re.findall(r'\d+', text2))

        all1 = words1 | nums1
        all2 = words2 | nums2

        if not all1 or not all2:
            return 0.0

        # Weighted Jaccard: shared meaningful words count more
        intersection = all1.intersection(all2)
        union = all1.union(all2)

        # Boost: if key product descriptors overlap, boost the score
        _KEY_TERMS = {"fat", "filled", "powder", "milk", "dairy", "food",
                      "preparation", "vegetable", "enriched", "whey",
                      "cream", "skimmed", "whole", "concentrate"}
        key_overlap = intersection.intersection(_KEY_TERMS)
        key_bonus = len(key_overlap) * 0.1  # each key term match adds 10%

        base_similarity = len(intersection) / len(union) if union else 0.0
        return min(base_similarity + key_bonus, 1.0)

    def search_by_description(
        self,
        description: str,
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search HS codes by description

        Args:
            description: Description to search for
            top_n: Number of top results to return

        Returns:
            List of matching HS code entries with similarity scores
        """
        if not self._ensure_loaded():
            return []

        results = []

        for hs_code, info in self._cet_index.items():
            similarity = self._calculate_similarity(
                description,
                info.get("description", "")
            )

            if similarity > 0.0:
                results.append({
                    **info,
                    "similarity_score": similarity
                })

        # Sort by similarity
        results.sort(key=lambda x: x["similarity_score"], reverse=True)

        return results[:top_n]

    def get_all_hs_codes(self) -> List[str]:
        """
        Get list of all HS codes in CET

        Returns:
            List of HS codes
        """
        if not self._ensure_loaded():
            return []

        return [info["hs_code"] for info in self._cet_index.values()]

    def get_cet_statistics(self) -> Dict[str, Any]:
        """
        Get CET file statistics

        Returns:
            Statistics dictionary
        """
        if not self._ensure_loaded():
            return {
                "loaded": False,
                "error": "CET file not loaded"
            }

        return {
            "loaded": True,
            "total_entries": len(self._cet_data),
            "indexed_hs_codes": len(self._cet_index),
            "last_loaded": self._last_loaded.isoformat() if self._last_loaded else None,
            "cache_age_seconds": (
                (datetime.now() - self._last_loaded).total_seconds()
                if self._last_loaded else None
            ),
            "file_path": self._config.get("cet_file_path"),
        }

    def _ensure_loaded(self) -> bool:
        """
        Ensure CET data is loaded

        Returns:
            True if loaded, False otherwise
        """
        if self._cet_data is None or self._cet_index is None:
            success = self.load_cet_file()
            if not success:
                logger.error("CET file not loaded and failed to load")
                return False

        return True

    def reload_cet(self, file_path: Optional[str] = None) -> bool:
        """
        Reload CET file (force reload)

        Args:
            file_path: Path to CET file

        Returns:
            True if reloaded successfully
        """
        logger.info("Reloading CET file...")
        return self.load_cet_file(file_path=file_path, force_reload=True)

    def clear_cache(self):
        """Clear CET cache"""
        self._cet_data = None
        self._cet_index = None
        self._last_loaded = None
        logger.info("CET cache cleared")


# Singleton instance getter
@lru_cache(maxsize=1)
def get_cet_service() -> CETFileService:
    """
    Get CET File Service singleton instance

    Returns:
        CETFileService instance
    """
    return CETFileService()
