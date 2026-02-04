"""
Job storage abstraction for generation module.

Allows different storage backends (memory, Redis, database, etc.)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from modules.generation.core.interfaces import GenerationStatus


@dataclass
class JobData:
    """Data structure for generation jobs."""
    job_id: str
    status: GenerationStatus
    created_at: float
    completed_at: Optional[float] = None
    request: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "status": self.status.value if isinstance(self.status, GenerationStatus) else self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "request": self.request,
            "error": self.error,
        }


class IJobStorage(ABC):
    """
    Abstract interface for job storage.
    
    Allows swapping storage backends without changing engine code.
    """
    
    @abstractmethod
    async def save_job(self, job_id: str, job_data: JobData) -> bool:
        """
        Save job data.
        
        Args:
            job_id: Job identifier
            job_data: Job data to save
        
        Returns:
            True if saved successfully
        """
        pass
    
    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[JobData]:
        """
        Get job data by ID.
        
        Args:
            job_id: Job identifier
        
        Returns:
            JobData or None if not found
        """
        pass
    
    @abstractmethod
    async def list_jobs(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[JobData]:
        """
        List jobs with optional filters.
        
        Args:
            filters: Optional filters (status, created_after, etc.)
            limit: Maximum number of jobs to return
        
        Returns:
            List of JobData
        """
        pass
    
    @abstractmethod
    async def delete_job(self, job_id: str) -> bool:
        """
        Delete job data.
        
        Args:
            job_id: Job identifier
        
        Returns:
            True if deleted successfully
        """
        pass
    
    @abstractmethod
    async def update_job_status(
        self,
        job_id: str,
        status: GenerationStatus,
        error: Optional[str] = None
    ) -> bool:
        """
        Update job status.
        
        Args:
            job_id: Job identifier
            status: New status
            error: Optional error message
        
        Returns:
            True if updated successfully
        """
        pass
    
    @abstractmethod
    async def cleanup_old_jobs(self, older_than_seconds: int) -> int:
        """
        Clean up old jobs.
        
        Args:
            older_than_seconds: Delete jobs older than this
        
        Returns:
            Number of jobs deleted
        """
        pass


class InMemoryJobStorage(IJobStorage):
    """
    In-memory job storage implementation.
    
    Simple, fast, but jobs lost on restart.
    Good for development and small deployments.
    """
    
    def __init__(self):
        """Initialize in-memory storage."""
        self._storage: Dict[str, JobData] = {}
    
    async def save_job(self, job_id: str, job_data: JobData) -> bool:
        """Save job to memory."""
        self._storage[job_id] = job_data
        return True
    
    async def get_job(self, job_id: str) -> Optional[JobData]:
        """Get job from memory."""
        return self._storage.get(job_id)
    
    async def list_jobs(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[JobData]:
        """List jobs from memory."""
        jobs = list(self._storage.values())
        
        # Apply filters
        if filters:
            if 'status' in filters:
                status_filter = filters['status']
                jobs = [j for j in jobs if j.status == status_filter]
            
            if 'created_after' in filters:
                created_after = filters['created_after']
                jobs = [j for j in jobs if j.created_at >= created_after]
        
        # Sort by creation time (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        return jobs[:limit]
    
    async def delete_job(self, job_id: str) -> bool:
        """Delete job from memory."""
        if job_id in self._storage:
            del self._storage[job_id]
            return True
        return False
    
    async def update_job_status(
        self,
        job_id: str,
        status: GenerationStatus,
        error: Optional[str] = None
    ) -> bool:
        """Update job status in memory."""
        if job_id in self._storage:
            self._storage[job_id].status = status
            if error:
                self._storage[job_id].error = error
            if status in [GenerationStatus.COMPLETED, GenerationStatus.FAILED]:
                self._storage[job_id].completed_at = datetime.utcnow().timestamp()
            return True
        return False
    
    async def cleanup_old_jobs(self, older_than_seconds: int) -> int:
        """Clean up old jobs from memory."""
        import time
        cutoff_time = time.time() - older_than_seconds
        
        jobs_to_delete = [
            job_id for job_id, job_data in self._storage.items()
            if job_data.created_at < cutoff_time
        ]
        
        for job_id in jobs_to_delete:
            del self._storage[job_id]
        
        return len(jobs_to_delete)
