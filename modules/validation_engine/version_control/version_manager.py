"""Version manager for tracking validation versions"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime

from .version_models import VersionMetadata, VersionStatus
from ..core.base import ValidationContext
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class VersionManager:
    """
    Manages validation versions and metadata

    Responsibilities:
    - Track version lineage (parent → child relationships)
    - Store version metadata
    - Query version history
    - Manage version status transitions
    """

    def __init__(self):
        """Initialize version manager"""
        # In-memory storage (would be database in production)
        self._versions: Dict[str, VersionMetadata] = {}
        self._version_history: Dict[UUID, List[int]] = {}

        logger.info("VersionManager initialized")

    async def create_version_metadata(
        self,
        context: ValidationContext,
        created_by: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> VersionMetadata:
        """
        Create version metadata from validation context

        Args:
            context: Validation context
            created_by: User who created this version
            notes: Optional version notes
            tags: Optional version tags

        Returns:
            Version metadata
        """
        # Calculate summary statistics
        total_validations = len(context.validation_results)
        passed_validations = sum(
            1 for r in context.validation_results if r.passed
        )
        failed_validations = total_validations - passed_validations

        # Count discrepancies by severity
        severity_counts = {"critical": 0, "major": 0, "minor": 0, "info": 0}
        for disc in context.discrepancies:
            severity = disc.severity.lower()
            if severity in severity_counts:
                severity_counts[severity] += 1

        # Count auto-fixes and confirmations
        auto_fixed_count = sum(
            1 for disc in context.discrepancies
            if getattr(disc, 'auto_fix_applied', False)
        )
        user_confirmed_count = len(context.user_confirmations)

        # Calculate accuracy
        accuracy_score = None
        if total_validations > 0:
            accuracy_score = round(
                (passed_validations / total_validations) * 100, 2
            )

        # Determine final status
        if severity_counts["critical"] > 0:
            final_status = "failed"
        elif severity_counts["major"] > 0:
            final_status = "partial"
        elif severity_counts["minor"] > 0:
            final_status = "warning"
        else:
            final_status = "passed"

        # Create metadata
        metadata = VersionMetadata(
            session_id=context.session_id,
            version=context.version,
            status=VersionStatus.ACTIVE,
            total_validations=total_validations,
            passed_validations=passed_validations,
            failed_validations=failed_validations,
            total_discrepancies=len(context.discrepancies),
            critical_count=severity_counts["critical"],
            major_count=severity_counts["major"],
            minor_count=severity_counts["minor"],
            info_count=severity_counts["info"],
            auto_fixed_count=auto_fixed_count,
            user_confirmed_count=user_confirmed_count,
            final_status=final_status,
            accuracy_score=accuracy_score,
            is_revalidation=context.is_revalidation,
            previous_version_id=context.previous_version_id,
            parent_version=(
                await self._get_latest_version(context.previous_version_id)
                if context.previous_version_id else None
            ),
            created_by=created_by,
            notes=notes,
            tags=tags or []
        )

        # Store metadata
        version_key = self._get_version_key(context.session_id, context.version)
        self._versions[version_key] = metadata

        # Update version history
        if context.session_id not in self._version_history:
            self._version_history[context.session_id] = []
        self._version_history[context.session_id].append(context.version)

        logger.info(
            f"Created version metadata: V{context.version} "
            f"(session {context.session_id}), status: {final_status}"
        )

        return metadata

    async def get_version_metadata(
        self, session_id: UUID, version: int
    ) -> Optional[VersionMetadata]:
        """
        Get version metadata

        Args:
            session_id: Session UUID
            version: Version number

        Returns:
            Version metadata or None if not found
        """
        version_key = self._get_version_key(session_id, version)
        return self._versions.get(version_key)

    async def get_latest_version(self, session_id: UUID) -> Optional[int]:
        """
        Get latest version number for a session

        Args:
            session_id: Session UUID

        Returns:
            Latest version number or None
        """
        return await self._get_latest_version(session_id)

    async def _get_latest_version(self, session_id: Optional[UUID]) -> Optional[int]:
        """Internal method to get latest version"""
        if session_id is None:
            return None

        versions = self._version_history.get(session_id, [])
        return max(versions) if versions else None

    async def get_version_history(
        self, session_id: UUID
    ) -> List[VersionMetadata]:
        """
        Get version history for a session

        Args:
            session_id: Session UUID

        Returns:
            List of version metadata, ordered by version number
        """
        versions = self._version_history.get(session_id, [])
        metadata_list = []

        for version in sorted(versions):
            version_key = self._get_version_key(session_id, version)
            metadata = self._versions.get(version_key)
            if metadata:
                metadata_list.append(metadata)

        return metadata_list

    async def update_version_status(
        self,
        session_id: UUID,
        version: int,
        status: VersionStatus
    ) -> bool:
        """
        Update version status

        Args:
            session_id: Session UUID
            version: Version number
            status: New status

        Returns:
            True if updated successfully
        """
        version_key = self._get_version_key(session_id, version)
        metadata = self._versions.get(version_key)

        if metadata:
            metadata.status = status
            metadata.updated_at = datetime.utcnow()
            logger.info(
                f"Updated V{version} status to {status} "
                f"(session {session_id})"
            )
            return True

        return False

    async def supersede_version(
        self, session_id: UUID, version: int
    ) -> bool:
        """
        Mark version as superseded (replaced by newer version)

        Args:
            session_id: Session UUID
            version: Version number to supersede

        Returns:
            True if superseded successfully
        """
        return await self.update_version_status(
            session_id, version, VersionStatus.SUPERSEDED
        )

    async def archive_version(
        self, session_id: UUID, version: int
    ) -> bool:
        """
        Archive a version (no longer actively used)

        Args:
            session_id: Session UUID
            version: Version number to archive

        Returns:
            True if archived successfully
        """
        return await self.update_version_status(
            session_id, version, VersionStatus.ARCHIVED
        )

    async def get_lineage(
        self, session_id: UUID, version: int
    ) -> List[Dict[str, Any]]:
        """
        Get version lineage (ancestry chain)

        Args:
            session_id: Session UUID
            version: Version number

        Returns:
            List of versions in lineage, from oldest to newest
        """
        lineage = []
        current_session = session_id
        current_version = version

        # Traverse backward through parent versions
        while current_session is not None:
            metadata = await self.get_version_metadata(
                current_session, current_version
            )

            if metadata is None:
                break

            lineage.insert(0, {
                "session_id": str(current_session),
                "version": current_version,
                "status": metadata.status,
                "final_status": metadata.final_status,
                "accuracy_score": metadata.accuracy_score,
                "total_discrepancies": metadata.total_discrepancies,
                "created_at": metadata.created_at.isoformat()
            })

            # Move to parent version
            if metadata.previous_version_id:
                current_session = metadata.previous_version_id
                parent_version = await self._get_latest_version(current_session)
                if parent_version:
                    current_version = parent_version
                else:
                    break
            else:
                break

        return lineage

    async def search_versions(
        self,
        use_case: Optional[str] = None,
        status: Optional[VersionStatus] = None,
        tags: Optional[List[str]] = None,
        min_accuracy: Optional[float] = None,
        created_after: Optional[datetime] = None
    ) -> List[VersionMetadata]:
        """
        Search versions by criteria

        Args:
            use_case: Filter by use case
            status: Filter by status
            tags: Filter by tags (any match)
            min_accuracy: Minimum accuracy score
            created_after: Created after this date

        Returns:
            List of matching version metadata
        """
        results = []

        for metadata in self._versions.values():
            # Apply filters
            if status and metadata.status != status:
                continue

            if tags and not any(tag in metadata.tags for tag in tags):
                continue

            if min_accuracy and (
                metadata.accuracy_score is None or
                metadata.accuracy_score < min_accuracy
            ):
                continue

            if created_after and metadata.created_at < created_after:
                continue

            results.append(metadata)

        # Sort by creation date (newest first)
        results.sort(key=lambda m: m.created_at, reverse=True)

        return results

    async def get_version_summary(
        self, session_id: UUID, version: int
    ) -> Dict[str, Any]:
        """
        Get comprehensive version summary

        Args:
            session_id: Session UUID
            version: Version number

        Returns:
            Version summary with metadata and statistics
        """
        metadata = await self.get_version_metadata(session_id, version)

        if metadata is None:
            return {}

        lineage = await self.get_lineage(session_id, version)

        return {
            "session_id": str(session_id),
            "version": version,
            "status": metadata.status,
            "final_status": metadata.final_status,
            "accuracy_score": metadata.accuracy_score,
            "validation_summary": {
                "total": metadata.total_validations,
                "passed": metadata.passed_validations,
                "failed": metadata.failed_validations
            },
            "discrepancy_summary": {
                "total": metadata.total_discrepancies,
                "critical": metadata.critical_count,
                "major": metadata.major_count,
                "minor": metadata.minor_count,
                "info": metadata.info_count
            },
            "auto_fixes": metadata.auto_fixed_count,
            "user_confirmations": metadata.user_confirmed_count,
            "is_revalidation": metadata.is_revalidation,
            "lineage": lineage,
            "lineage_depth": len(lineage),
            "metadata": {
                "created_by": metadata.created_by,
                "created_at": metadata.created_at.isoformat(),
                "updated_at": metadata.updated_at.isoformat(),
                "tags": metadata.tags,
                "notes": metadata.notes
            }
        }

    def _get_version_key(self, session_id: UUID, version: int) -> str:
        """Generate unique version key"""
        return f"{session_id}:v{version}"


# Singleton instance
_version_manager_instance: Optional[VersionManager] = None


def get_version_manager() -> VersionManager:
    """
    Get singleton version manager instance

    Returns:
        VersionManager instance
    """
    global _version_manager_instance
    if _version_manager_instance is None:
        _version_manager_instance = VersionManager()
    return _version_manager_instance
