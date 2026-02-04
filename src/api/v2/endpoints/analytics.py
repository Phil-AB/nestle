"""
Universal Analytics API Endpoints.

100% config-driven, use-case based REST API for analytics.
Works for ANY use case - structure determined by config.

No hardcoded field names, metrics, or thresholds.
"""

from fastapi import APIRouter, HTTPException, status, Query, Path
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
import logging

from src.database.connection import get_session
from modules.analytics import AnalyticsService
from modules.analytics.config_loader import list_available_use_cases

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    responses={
        404: {"description": "Resource not found"},
        500: {"description": "Internal server error"}
    }
)


# ==============================================================================
# REQUEST/RESPONSE MODELS - 100% Dynamic
# ==============================================================================

class AnalyticsResponse(BaseModel):
    """
    Universal analytics response.

    All fields are dynamic - structure determined by use case config.
    """
    success: bool
    use_case_id: str
    overview: Dict[str, Any]
    dimensions: Dict[str, Any]
    trends: List[Dict[str, Any]]
    products: Dict[str, Any]
    metadata: Dict[str, Any]
    error: Optional[str] = None

    class Config:
        extra = "allow"


class DimensionBreakdownResponse(BaseModel):
    """Response for a single dimension breakdown."""
    success: bool
    dimension_id: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]


class TrendResponse(BaseModel):
    """Response for trend data."""
    success: bool
    period: str
    data: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class PercentileResponse(BaseModel):
    """Response for percentile comparison."""
    success: bool
    document_id: str
    percentiles: Dict[str, Optional[float]]
    total_compared: int


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@router.get(
    "/dashboard",
    response_model=AnalyticsResponse,
    summary="Get complete dashboard data",
    description="""
    Get all analytics data for the dashboard in a single request.

    The response structure is determined by the use case config.
    """
)
async def get_dashboard(
    use_case_id: str = Query(
        default="forms-capital-loan",
        description="Use case identifier"
    ),
    date_range: Optional[Literal["30d", "90d", "12m", "all"]] = Query(
        default="all",
        description="Time period for analytics"
    )
):
    """Get complete dashboard data using config-driven analytics."""
    try:
        async with get_session() as session:
            service = AnalyticsService(use_case_id, session)
            dashboard = await service.get_dashboard(date_range=date_range)

            return AnalyticsResponse(
                success=True,
                use_case_id=use_case_id,
                overview=dashboard.get("overview", {}),
                dimensions=dashboard.get("dimensions", {}),
                trends=dashboard.get("trends", []),
                products=dashboard.get("products", {}),
                metadata=dashboard.get("metadata", {})
            )

    except FileNotFoundError as e:
        logger.error(f"Use case not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Use case not found: {use_case_id}"
        )

    except Exception as e:
        logger.error(f"Error getting dashboard: {e}", exc_info=True)
        return AnalyticsResponse(
            success=False,
            use_case_id=use_case_id,
            overview={},
            dimensions={},
            trends=[],
            products={},
            metadata={"error_time": datetime.utcnow().isoformat()},
            error=str(e)
        )


@router.get(
    "/overview",
    summary="Get overview metrics",
    description="Get key metrics for the dashboard"
)
async def get_overview_metrics(
    use_case_id: str = Query(default="forms-capital-loan"),
    date_range: Optional[Literal["30d", "90d", "12m", "all"]] = Query(default="all")
):
    """Get overview metrics only."""
    try:
        async with get_session() as session:
            service = AnalyticsService(use_case_id, session)
            overview = await service.get_overview_metrics(date_range=date_range)

            return {
                "success": True,
                "use_case_id": use_case_id,
                "metrics": overview,
                "date_range": date_range
            }

    except Exception as e:
        logger.error(f"Error getting overview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/dimensions/{dimension_id}",
    response_model=DimensionBreakdownResponse,
    summary="Get breakdown for a specific dimension",
    description="Get aggregated data for a configured dimension"
)
async def get_dimension_breakdown(
    dimension_id: str,
    use_case_id: str = Query(default="forms-capital-loan"),
    date_range: Optional[Literal["30d", "90d", "12m", "all"]] = Query(default="all")
):
    """Get breakdown for a specific dimension."""
    try:
        async with get_session() as session:
            service = AnalyticsService(use_case_id, session)
            breakdown = await service.get_dimension_breakdown(
                dimension_id,
                date_range=date_range
            )

            return DimensionBreakdownResponse(
                success=True,
                dimension_id=dimension_id,
                data=breakdown,
                metadata={
                    "use_case_id": use_case_id,
                    "date_range": date_range,
                    "generated_at": datetime.utcnow().isoformat()
                }
            )

    except Exception as e:
        logger.error(f"Error getting dimension {dimension_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/dimensions",
    summary="Get all dimension breakdowns",
    description="Get breakdowns for all configured dimensions"
)
async def get_all_dimensions(
    use_case_id: str = Query(default="forms-capital-loan"),
    date_range: Optional[Literal["30d", "90d", "12m", "all"]] = Query(default="all")
):
    """Get all configured dimension breakdowns."""
    try:
        async with get_session() as session:
            service = AnalyticsService(use_case_id, session)
            dashboard = await service.get_dashboard(date_range=date_range)

            return {
                "success": True,
                "use_case_id": use_case_id,
                "dimensions": dashboard.get("dimensions", {}),
                "date_range": date_range
            }

    except Exception as e:
        logger.error(f"Error getting dimensions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/trends",
    response_model=TrendResponse,
    summary="Get trend data",
    description="Get time-series trend data"
)
async def get_trends(
    use_case_id: str = Query(default="forms-capital-loan"),
    period: Literal["daily", "monthly"] = Query(default="monthly"),
    count: int = Query(default=12, ge=1, le=36)
):
    """Get trend data over time."""
    try:
        async with get_session() as session:
            service = AnalyticsService(use_case_id, session)
            trends = await service.get_trends(period=period, count=count)

            return TrendResponse(
                success=True,
                period=period,
                data=trends,
                metadata={
                    "use_case_id": use_case_id,
                    "periods_requested": count,
                    "generated_at": datetime.utcnow().isoformat()
                }
            )

    except Exception as e:
        logger.error(f"Error getting trends: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/products",
    summary="Get product eligibility metrics",
    description="Get eligibility breakdown for configured products"
)
async def get_product_metrics(
    use_case_id: str = Query(default="forms-capital-loan"),
    date_range: Optional[Literal["30d", "90d", "12m", "all"]] = Query(default="all")
):
    """Get product eligibility metrics."""
    try:
        async with get_session() as session:
            service = AnalyticsService(use_case_id, session)
            dashboard = await service.get_dashboard(date_range=date_range)

            return {
                "success": True,
                "use_case_id": use_case_id,
                "products": dashboard.get("products", {}),
                "date_range": date_range
            }

    except Exception as e:
        logger.error(f"Error getting products: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/percentile/{document_id}",
    response_model=PercentileResponse,
    summary="Get percentile comparisons",
    description="Compare a document against all others"
)
async def get_percentile_comparisons(
    document_id: str,
    use_case_id: str = Query(default="forms-capital-loan")
):
    """Get percentile comparisons for a document."""
    try:
        async with get_session() as session:
            service = AnalyticsService(use_case_id, session)

            # Get percentiles for configured comparison metrics
            percentiles = {}
            config = service.metrics_config.get("comparison_metrics", {})

            for metric_id, metric_config in config.items():
                percentile = await service.get_percentile(document_id, metric_id)
                percentiles[metric_id] = percentile

            # Get total count
            dashboard = await service.get_dashboard()
            total = dashboard.get("overview", {}).get("total_documents", 0)

            return PercentileResponse(
                success=True,
                document_id=document_id,
                percentiles=percentiles,
                total_compared=total
            )

    except Exception as e:
        logger.error(f"Error getting percentiles: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/use-cases",
    summary="List available analytics use cases",
    description="Get a list of available analytics configurations"
)
async def list_use_cases():
    """List available analytics use cases."""
    try:
        use_cases = list_available_use_cases()

        return {
            "success": True,
            "use_cases": [
                {"id": uc, "name": uc.replace("-", " ").title()}
                for uc in use_cases
            ],
            "total": len(use_cases)
        }

    except Exception as e:
        logger.error(f"Error listing use cases: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/config/{use_case_id}",
    summary="Get analytics configuration for a use case",
    description="Get the full configuration (metrics and dimensions) for a specific use case"
)
async def get_use_case_config(use_case_id: str = Path(..., description="Use case identifier")):
    """Get full analytics configuration for a specific use case."""
    try:
        from modules.analytics.config_loader import AnalyticsConfigLoader

        loader = AnalyticsConfigLoader(use_case_id)
        config = loader.load_all()

        return {
            "success": True,
            "use_case_id": use_case_id,
            "config": config
        }

    except FileNotFoundError as e:
        logger.error(f"Use case config not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Use case configuration not found: {use_case_id}"
        )
    except Exception as e:
        logger.error(f"Error loading use case config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/health",
    summary="Health check for analytics service",
    description="Check health status of the analytics service"
)
async def health_check():
    """Health check for analytics service."""
    use_cases = list_available_use_cases()

    return {
        "status": "healthy",
        "service": "universal-analytics",
        "version": "2.0.0",
        "available_use_cases": use_cases,
        "capabilities": [
            "config_driven_metrics",
            "dynamic_dimensions",
            "trend_analysis",
            "product_eligibility",
            "percentile_comparisons",
            "use_case_based"
        ]
    }


# ==============================================================================
# BACKWARD COMPATIBILITY ALIASES
# ==============================================================================
# These endpoints maintain backward compatibility with old API structure

@router.get(
    "/demographics",
    summary="Get demographics (backward compatible)",
    description="Alias for dimension breakdowns - maintains backward compatibility"
)
async def get_demographics_compat(
    date_range: Optional[Literal["30d", "90d", "12m", "all"]] = Query(default="all")
):
    """Backward compatible demographics endpoint."""
    return await get_all_dimensions(
        use_case_id="forms-capital-loan",
        date_range=date_range
    )


@router.get(
    "/trends/monthly",
    summary="Get monthly trends (backward compatible)",
    description="Alias for trends endpoint - maintains backward compatibility"
)
async def get_monthly_trends_compat(
    months: int = Query(default=12, ge=1, le=24)
):
    """Backward compatible monthly trends endpoint."""
    result = await get_trends(
        use_case_id="forms-capital-loan",
        period="monthly",
        count=months
    )
    # Return just the data list for backward compatibility
    return result.data
