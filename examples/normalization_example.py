"""
Normalization Example
Demonstrates field name mapping, unit conversion, and format normalization
"""

import asyncio
from modules.validation_engine.normalization import get_normalization_engine


async def main():
    """Run normalization example"""

    # Sample document with French field names and mixed formats
    raw_document = {
        # French field names
        "Poids Net": "1000 KG",
        "Poids Brut": "2204 LBS",  # Will be converted to KG
        "Code SH": "1234.56",
        "Quantité": "50",
        "Prix Unitaire": "$100.00",

        # Mixed date formats
        "Date de Facture": "09/02/2026",  # DD/MM/YYYY
        "Date d'Expédition": "2026-02-09",  # Already normalized

        # Mixed decimal formats
        "Montant Total": "5,000.00",  # US format
        "Valeur en Douane": "5.000,00",  # European format

        # Boolean variations
        "Active": "oui",
        "Enabled": "yes",
    }

    print("=" * 80)
    print("Normalization Example")
    print("=" * 80)

    # Get normalization engine
    engine = get_normalization_engine()

    print("\n📄 Raw Document:")
    for key, value in raw_document.items():
        print(f"   {key}: {value}")

    # Normalize document
    print("\n🔄 Normalizing...")
    normalized_document = await engine.normalize_document(
        document=raw_document,
        document_type="invoice"
    )

    print("\n✅ Normalized Document:")
    for key, value in normalized_document.items():
        print(f"   {key}: {value}")

    # Show specific transformations
    print("\n🔍 Transformations Applied:")

    # Field name mapping
    print("\n1. Field Name Normalization (Synonyms):")
    print("   'Poids Net' → 'net_weight'")
    print("   'Poids Brut' → 'gross_weight'")
    print("   'Code SH' → 'hs_code'")
    print("   'Quantité' → 'quantity'")
    print("   'Prix Unitaire' → 'unit_price'")

    # Unit conversion
    print("\n2. Unit Conversion:")
    print("   2204 LBS → 1000.0 KG")

    # Format normalization
    print("\n3. Format Normalization:")
    print("   Date: '09/02/2026' → '2026-02-09'")
    print("   Decimal (US): '5,000.00' → 5000.00")
    print("   Decimal (EU): '5.000,00' → 5000.00")
    print("   Currency: '$100.00' → 100.00")

    # Boolean normalization
    print("\n4. Boolean Normalization:")
    print("   'oui' → True")
    print("   'yes' → True")

    # Get statistics
    print("\n📊 Normalization Statistics:")
    stats = engine.get_normalization_stats()
    print(f"   Strategy: {stats['strategy']}")
    print(f"   Synonym Mapper: {stats['synonym_mapper']['canonical_fields']} fields, "
          f"{stats['synonym_mapper']['total_synonyms']} synonyms")

    print("\n" + "=" * 80)
    print("Normalization completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
