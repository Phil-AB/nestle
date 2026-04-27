"""Unit converter for weight, currency, volume, and length"""

from typing import Dict, Any, Optional, Union
from decimal import Decimal
import httpx
from datetime import datetime, timedelta
from ...core.config_loader import get_config_loader
from ...utils.exceptions import NormalizationException
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class UnitConverter:
    """
    Convert units to standard formats

    Supports:
    - Weight: LBS, MT, G → KG
    - Currency: EUR, GBP, JPY → USD
    - Volume: L, GAL, FT3 → M3
    - Length: CM, IN, FT → M
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize unit converter

        Args:
            config: Normalization configuration
        """
        self.config = config or {}

        # Load normalization config
        config_loader = get_config_loader()
        norm_config = config_loader.load_normalization_config()

        # Unit conversion settings
        self.unit_config = norm_config.get("unit_conversion", {})
        self.enabled = self.unit_config.get("enabled", True)

        # Load conversion tables
        self.weight_conversions = self.unit_config.get("weight", {}).get("conversions", {})
        self.weight_target = self.unit_config.get("weight", {}).get("target_unit", "KG")

        self.volume_conversions = self.unit_config.get("volume", {}).get("conversions", {})
        self.volume_target = self.unit_config.get("volume", {}).get("target_unit", "M3")

        self.length_conversions = self.unit_config.get("length", {}).get("conversions", {})
        self.length_target = self.unit_config.get("length", {}).get("target_unit", "M")

        # Currency conversion
        self.currency_config = self.unit_config.get("currency", {})
        self.currency_target = self.currency_config.get("target_unit", "USD")
        self.currency_source = self.currency_config.get("source", "exchange_rate_api")
        self.currency_api_endpoint = self.currency_config.get("api_endpoint")
        self.currency_cache_ttl = self.currency_config.get("cache_ttl", 86400)
        self.fallback_rates = self.currency_config.get("fallback_rates", {})

        # Exchange rate cache
        self.exchange_rates: Dict[str, float] = {}
        self.exchange_rates_fetched_at: Optional[datetime] = None

        logger.info("UnitConverter initialized")

    async def convert_weight(
        self,
        value: Union[int, float, Decimal, str],
        from_unit: str,
        to_unit: Optional[str] = None
    ) -> Decimal:
        """
        Convert weight to target unit

        Args:
            value: Value to convert
            from_unit: Source unit (LBS, MT, G, etc.)
            to_unit: Target unit (default: KG)

        Returns:
            Converted value in target unit

        Raises:
            NormalizationException: If conversion fails
        """
        if not self.enabled:
            return self._to_decimal(value)

        to_unit = to_unit or self.weight_target
        from_unit = from_unit.upper()
        to_unit = to_unit.upper()

        # No conversion needed
        if from_unit == to_unit:
            return self._to_decimal(value)

        # Get conversion factor
        if from_unit not in self.weight_conversions:
            raise NormalizationException(
                f"Unknown weight unit: {from_unit}. "
                f"Supported: {', '.join(self.weight_conversions.keys())}"
            )

        conversion_factor = Decimal(str(self.weight_conversions[from_unit]))
        value_decimal = self._to_decimal(value)

        # Convert to target unit (via base unit KG)
        converted = value_decimal * conversion_factor

        logger.debug(f"Weight conversion: {value} {from_unit} → {converted} {to_unit}")

        return converted

    async def convert_currency(
        self,
        value: Union[int, float, Decimal, str],
        from_currency: str,
        to_currency: Optional[str] = None
    ) -> Decimal:
        """
        Convert currency to target currency

        Args:
            value: Value to convert
            from_currency: Source currency (EUR, GBP, etc.)
            to_currency: Target currency (default: USD)

        Returns:
            Converted value in target currency

        Raises:
            NormalizationException: If conversion fails
        """
        if not self.enabled:
            return self._to_decimal(value)

        to_currency = to_currency or self.currency_target
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # No conversion needed
        if from_currency == to_currency:
            return self._to_decimal(value)

        # Get exchange rate
        try:
            rate = await self._get_exchange_rate(from_currency, to_currency)
        except Exception as e:
            logger.error(f"Currency conversion failed: {str(e)}")
            # Try fallback rate
            if from_currency in self.fallback_rates:
                rate = Decimal(str(self.fallback_rates[from_currency]))
                logger.warning(f"Using fallback rate for {from_currency}: {rate}")
            else:
                raise NormalizationException(
                    f"Cannot convert {from_currency} to {to_currency}: {str(e)}"
                )

        value_decimal = self._to_decimal(value)
        converted = value_decimal * rate

        logger.debug(
            f"Currency conversion: {value} {from_currency} → {converted} {to_currency} "
            f"(rate: {rate})"
        )

        return converted

    async def convert_volume(
        self,
        value: Union[int, float, Decimal, str],
        from_unit: str,
        to_unit: Optional[str] = None
    ) -> Decimal:
        """
        Convert volume to target unit

        Args:
            value: Value to convert
            from_unit: Source unit (L, GAL, FT3, etc.)
            to_unit: Target unit (default: M3)

        Returns:
            Converted value in target unit
        """
        if not self.enabled:
            return self._to_decimal(value)

        to_unit = to_unit or self.volume_target
        from_unit = from_unit.upper()
        to_unit = to_unit.upper()

        if from_unit == to_unit:
            return self._to_decimal(value)

        if from_unit not in self.volume_conversions:
            raise NormalizationException(f"Unknown volume unit: {from_unit}")

        conversion_factor = Decimal(str(self.volume_conversions[from_unit]))
        value_decimal = self._to_decimal(value)
        converted = value_decimal * conversion_factor

        logger.debug(f"Volume conversion: {value} {from_unit} → {converted} {to_unit}")

        return converted

    async def convert_length(
        self,
        value: Union[int, float, Decimal, str],
        from_unit: str,
        to_unit: Optional[str] = None
    ) -> Decimal:
        """
        Convert length to target unit

        Args:
            value: Value to convert
            from_unit: Source unit (CM, IN, FT, etc.)
            to_unit: Target unit (default: M)

        Returns:
            Converted value in target unit
        """
        if not self.enabled:
            return self._to_decimal(value)

        to_unit = to_unit or self.length_target
        from_unit = from_unit.upper()
        to_unit = to_unit.upper()

        if from_unit == to_unit:
            return self._to_decimal(value)

        if from_unit not in self.length_conversions:
            raise NormalizationException(f"Unknown length unit: {from_unit}")

        conversion_factor = Decimal(str(self.length_conversions[from_unit]))
        value_decimal = self._to_decimal(value)
        converted = value_decimal * conversion_factor

        logger.debug(f"Length conversion: {value} {from_unit} → {converted} {to_unit}")

        return converted

    async def _get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str
    ) -> Decimal:
        """
        Get exchange rate from API or cache

        Args:
            from_currency: Source currency
            to_currency: Target currency

        Returns:
            Exchange rate

        Raises:
            NormalizationException: If rate cannot be fetched
        """
        # Check if cache is valid
        if self._is_cache_valid():
            rate_key = f"{from_currency}_{to_currency}"
            if rate_key in self.exchange_rates:
                return Decimal(str(self.exchange_rates[rate_key]))

        # Fetch fresh rates
        await self._fetch_exchange_rates()

        # Get rate
        rate_key = f"{from_currency}_{to_currency}"
        if rate_key in self.exchange_rates:
            return Decimal(str(self.exchange_rates[rate_key]))

        # Calculate cross rate (via USD)
        if from_currency in self.exchange_rates and to_currency in self.exchange_rates:
            from_to_usd = Decimal(str(self.exchange_rates[from_currency]))
            to_to_usd = Decimal(str(self.exchange_rates[to_currency]))
            cross_rate = from_to_usd / to_to_usd
            return cross_rate

        raise NormalizationException(
            f"Exchange rate not available for {from_currency} to {to_currency}"
        )

    async def _fetch_exchange_rates(self):
        """Fetch latest exchange rates from API"""
        if not self.currency_api_endpoint:
            logger.warning("No currency API endpoint configured, using fallback rates")
            self.exchange_rates = {
                f"{curr}_USD": rate
                for curr, rate in self.fallback_rates.items()
            }
            self.exchange_rates_fetched_at = datetime.utcnow()
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.currency_api_endpoint)
                response.raise_for_status()

                data = response.json()

                # Parse rates (format depends on API)
                # Example: {"rates": {"EUR": 1.1, "GBP": 1.3, ...}}
                rates = data.get("rates", {})

                # Store rates as {CURRENCY_USD: rate}
                self.exchange_rates = {
                    f"{curr}_USD": rate
                    for curr, rate in rates.items()
                }

                self.exchange_rates_fetched_at = datetime.utcnow()

                logger.info(f"Fetched {len(self.exchange_rates)} exchange rates")

        except Exception as e:
            logger.error(f"Failed to fetch exchange rates: {str(e)}")
            # Use fallback rates
            self.exchange_rates = {
                f"{curr}_USD": rate
                for curr, rate in self.fallback_rates.items()
            }
            self.exchange_rates_fetched_at = datetime.utcnow()

    def _is_cache_valid(self) -> bool:
        """Check if exchange rate cache is valid"""
        if not self.exchange_rates_fetched_at:
            return False

        age = (datetime.utcnow() - self.exchange_rates_fetched_at).total_seconds()
        return age < self.currency_cache_ttl

    def _to_decimal(self, value: Union[int, float, Decimal, str]) -> Decimal:
        """Convert value to Decimal for precise calculations"""
        if isinstance(value, Decimal):
            return value

        if isinstance(value, (int, float)):
            return Decimal(str(value))

        if isinstance(value, str):
            # Remove formatting
            cleaned = value.replace(",", "").replace(" ", "").strip()
            return Decimal(cleaned)

        raise ValueError(f"Cannot convert {type(value)} to Decimal")

    def clear_cache(self):
        """Clear exchange rate cache"""
        self.exchange_rates.clear()
        self.exchange_rates_fetched_at = None
        logger.info("Exchange rate cache cleared")
