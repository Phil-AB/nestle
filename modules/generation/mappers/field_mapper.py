"""
Field mapper implementation.

Maps source data fields to template fields with transformations.
Self-registers with MapperRegistry - NO factory changes needed.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal
import re

from modules.generation.core.interfaces import IMapper, MappingResult
from modules.generation.core.exceptions import MappingException
from modules.generation.core.registry import register_mapper
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


@register_mapper("field")  # ← SELF-REGISTERS! Zero factory changes.
class FieldMapper(IMapper):
    """
    Field-to-field mapper with transformations.
    
    Supports:
    - Direct field mapping
    - Nested field mapping (dot notation)
    - Default values
    - Data transformations
    - Calculated fields
    - Table mappings
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize field mapper."""
        super().__init__(config)
        logger.info("Initialized FieldMapper")
    
    async def map_data(
        self,
        source_data: Dict[str, Any],
        mapping_config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> MappingResult:
        """
        Map source data to target format.
        
        Args:
            source_data: Data from data provider
            mapping_config: Mapping configuration (from YAML)
            context: Optional context
        
        Returns:
            MappingResult with mapped data
        """
        try:
            logger.info("Starting data mapping")
            logger.info(f"Input source_data keys: {list(source_data.keys())}")
            logger.info(f"Mapping config keys: {list(mapping_config.keys())}")
            
            mapped_data = {}
            unmapped_fields = []
            warnings = []
            errors = []
            
            # 1. Apply field mappings
            field_mappings = mapping_config.get('field_mappings', {})
            logger.info(f"Found {len(field_mappings)} field mappings in config")
            logger.info(f"Field mapping keys sample: {list(field_mappings.keys())[:10]}")
            
            for target_field, field_config in field_mappings.items():
                if target_field == 'defaults':
                    continue
                
                # Handle both simple (string) and advanced (dict) formats
                if isinstance(field_config, str):
                    # Simple format: target_field: source_field
                    source_field = field_config
                    fallback_fields = []
                    default_value = None
                elif isinstance(field_config, dict):
                    # Advanced format: target_field: {source: ..., fallback: [...], default: ..., transformation: ...}
                    source_field = field_config.get('source')
                    fallback_fields = field_config.get('fallback', [])
                    # Ensure fallback is a list
                    if isinstance(fallback_fields, str):
                        fallback_fields = [fallback_fields]
                    default_value = field_config.get('default')
                else:
                    logger.warning(f"Invalid field mapping config for '{target_field}'")
                    continue

                if not source_field:
                    if default_value is not None:
                        mapped_data[target_field] = default_value
                    continue

                # Try to get value from source
                value = self._get_nested_value(source_data, source_field)

                # If not found, try fallback fields
                if value is None and fallback_fields:
                    for fallback_field in fallback_fields:
                        value = self._get_nested_value(source_data, fallback_field)
                        if value is not None:
                            logger.debug(f"'{target_field}' using fallback '{fallback_field}': {value}")
                            break

                if value is not None:
                    mapped_data[target_field] = value
                    if target_field.startswith('risk_') or target_field.startswith('extra_') or target_field.startswith('premium_'):
                        logger.info(f"Mapped '{target_field}' <- '{source_field}': {value}")
                else:
                    # Use default if value not found
                    if default_value is not None:
                        mapped_data[target_field] = default_value
                        logger.info(f"Applied default for '{target_field}': {default_value}")
                    else:
                        unmapped_fields.append(source_field)
                        if 'insights' in source_field:
                            logger.info(f"Field '{target_field}' <- '{source_field}' not found in source data. Keys: {list(source_data.keys())[:5]}")
            
            # 3. Apply transformations
            transformations = mapping_config.get('transformations', [])
            for transform in transformations:
                try:
                    mapped_data = self._apply_transformation(mapped_data, transform)
                except Exception as e:
                    error_msg = f"Transformation failed for {transform.get('field')}: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
            
            # 4. Map tables
            if 'table_mappings' in mapping_config:
                try:
                    table_data = self._map_tables(
                        source_data,
                        mapping_config['table_mappings']
                    )
                    mapped_data['tables'] = table_data
                except Exception as e:
                    error_msg = f"Table mapping failed: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
            
            # 5. Calculate fields
            if 'calculated_fields' in mapping_config:
                try:
                    calculated = self._calculate_fields(
                        source_data,
                        mapped_data,
                        mapping_config['calculated_fields']
                    )
                    mapped_data.update(calculated)
                except Exception as e:
                    error_msg = f"Field calculation failed: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
            
            # 6. Post-processing
            post_processing = mapping_config.get('post_processing', {})
            
            if post_processing.get('remove_null_fields', False):
                mapped_data = {k: v for k, v in mapped_data.items() if v is not None}
            
            if post_processing.get('remove_empty_arrays', False):
                mapped_data = {k: v for k, v in mapped_data.items() 
                             if not (isinstance(v, list) and len(v) == 0)}
            
            if post_processing.get('trim_strings', False):
                for key, value in mapped_data.items():
                    if isinstance(value, str):
                        mapped_data[key] = value.strip()
            
            logger.info(f"✅ Mapping completed. Mapped {len(mapped_data)} fields")
            logger.info(f"📝 Mapped keys: {list(mapped_data.keys())[:10]}")
            if mapped_data:
                logger.info(f"📊 First 3 values: {dict(list(mapped_data.items())[:3])}")

            # Add generation timestamp
            mapped_data['_generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            success = len(errors) == 0
            if not success:
                logger.warning(f"Mapping completed with {len(errors)} errors")

            return MappingResult(
                success=success,
                mapped_data=mapped_data,
                unmapped_fields=unmapped_fields,
                warnings=warnings,
                errors=errors
            )
            
        except Exception as e:
            logger.error(f"Mapping failed: {str(e)}")
            raise MappingException(f"Field mapping failed: {str(e)}")
    
    def _get_nested_value(self, data: Dict, field_path: str) -> Any:
        """Get value from nested dict using dot notation."""
        keys = field_path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
            
            if value is None:
                return None
        
        return value
    
    def _apply_transformation(
        self,
        data: Dict[str, Any],
        transform: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply transformation to a field."""
        field = transform['field']
        transform_type = transform['type']
        params = transform.get('params', {})
        
        if field not in data:
            return data
        
        value = data[field]
        
        # Apply transformation based on type
        if transform_type == 'date_format':
            data[field] = self._format_date(value, params)
        
        elif transform_type == 'currency_format':
            data[field] = self._format_currency(value, params)
        
        elif transform_type == 'uppercase':
            data[field] = str(value).upper() if value else ""
        
        elif transform_type == 'lowercase':
            data[field] = str(value).lower() if value else ""
        
        elif transform_type == 'concatenate':
            data[field] = self._concatenate_fields(data, params)
        
        elif transform_type == 'replace':
            pattern = params.get('pattern', '')
            replacement = params.get('replacement', '')
            data[field] = str(value).replace(pattern, replacement) if value else ""
        
        return data
    
    def _format_date(self, value: Any, params: Dict) -> str:
        """Format date value."""
        if not value:
            return ""
        
        input_format = params.get('input_format', '%Y-%m-%d')
        output_format = params.get('output_format', '%B %d, %Y')
        
        try:
            if isinstance(value, str):
                date_obj = datetime.strptime(value, input_format)
            elif isinstance(value, datetime):
                date_obj = value
            else:
                return str(value)
            
            return date_obj.strftime(output_format)
        except Exception as e:
            logger.warning(f"Date format failed: {str(e)}")
            return str(value)
    
    def _format_currency(self, value: Any, params: Dict) -> str:
        """Format currency value."""
        if not value:
            return ""
        
        decimal_places = params.get('decimal_places', 2)
        include_symbol = params.get('include_symbol', False)
        currency = params.get('currency', 'USD')
        
        try:
            amount = Decimal(str(value))
            formatted = f"{amount:,.{decimal_places}f}"
            
            if include_symbol:
                symbols = {'USD': '$', 'EUR': '€', 'GBP': '£'}
                symbol = symbols.get(currency, currency)
                formatted = f"{symbol}{formatted}"
            
            return formatted
        except Exception as e:
            logger.warning(f"Currency format failed: {str(e)}")
            return str(value)
    
    def _concatenate_fields(self, data: Dict, params: Dict) -> str:
        """Concatenate multiple fields."""
        fields = params.get('fields', [])
        separator = params.get('separator', ' ')
        
        values = []
        for field in fields:
            value = data.get(field)
            if value:
                values.append(str(value))
        
        return separator.join(values)
    
    def _map_tables(
        self,
        source_data: Dict[str, Any],
        table_mappings: Dict[str, Any]
    ) -> Dict[str, List[Dict]]:
        """Map table/array data."""
        result = {}
        
        for table_name, config in table_mappings.items():
            source_array_path = config.get('source')
            source_array = self._get_nested_value(source_data, source_array_path)
            
            if not source_array or not isinstance(source_array, list):
                logger.warning(f"Table source '{source_array_path}' not found or not a list")
                continue
            
            mappings = config.get('mappings', {})
            mapped_rows = []
            
            for row in source_array:
                mapped_row = {}
                for source_field, target_field in mappings.items():
                    value = row.get(source_field)
                    if value is not None:
                        mapped_row[target_field] = value
                
                # Apply table transformations if any
                transformations = config.get('transformations', [])
                for transform in transformations:
                    try:
                        mapped_row = self._apply_transformation(mapped_row, transform)
                    except Exception as e:
                        logger.warning(f"Table transformation failed: {str(e)}")
                
                mapped_rows.append(mapped_row)
            
            result[table_name] = mapped_rows
            logger.debug(f"Mapped table '{table_name}' with {len(mapped_rows)} rows")
        
        return result
    
    def _calculate_fields(
        self,
        source_data: Dict[str, Any],
        mapped_data: Dict[str, Any],
        calculated_fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate derived fields."""
        result = {}
        
        for field_name, calc_config in calculated_fields.items():
            calc_type = calc_config.get('type')
            
            try:
                if calc_type == 'sum':
                    # Sum array field
                    source = calc_config.get('source')
                    field = calc_config.get('field')
                    array = self._get_nested_value(source_data, source) or []
                    total = sum(Decimal(str(item.get(field, 0))) for item in array if isinstance(item, dict))
                    result[field_name] = total
                
                elif calc_type == 'multiply':
                    # Multiply field by value
                    params = calc_config.get('params', {})
                    field = params.get('field')
                    multiplier = params.get('multiplier', 1)
                    value = mapped_data.get(field, 0)
                    result[field_name] = Decimal(str(value)) * Decimal(str(multiplier))
                
                elif calc_type == 'add':
                    # Add multiple fields
                    params = calc_config.get('params', {})
                    fields = params.get('fields', [])
                    total = Decimal('0')
                    for field in fields:
                        value = mapped_data.get(field, 0)
                        total += Decimal(str(value))
                    result[field_name] = total
                
                logger.debug(f"Calculated field '{field_name}': {result[field_name]}")
                
            except Exception as e:
                logger.warning(f"Calculation failed for '{field_name}': {str(e)}")
        
        return result
    
    def validate_mapping_config(self, mapping_config: Dict[str, Any]) -> bool:
        """Validate mapping configuration."""
        # Check required keys
        if 'field_mappings' not in mapping_config:
            return False
        
        # Field mappings should be a dict
        if not isinstance(mapping_config['field_mappings'], dict):
            return False
        
        return True
