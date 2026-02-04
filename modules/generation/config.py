"""
Generation module configuration.

Centralizes all configuration for standalone usage.
"""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class GenerationConfig:
    """
    Configuration for generation module.
    
    Makes the module fully configurable for standalone usage.
    """
    
    # Path configuration
    project_root: Path = field(default_factory=Path.cwd)
    templates_metadata_dir: Optional[Path] = None
    templates_files_dir: Optional[Path] = None
    mappings_dir: Optional[Path] = None
    output_dir: Optional[Path] = None
    
    # System configuration files
    system_config_path: Optional[Path] = None
    renderers_config_path: Optional[Path] = None
    data_sources_config_path: Optional[Path] = None
    data_provision_config_path: Optional[Path] = None
    
    # Runtime settings
    max_concurrent_jobs: int = 100
    generation_timeout: int = 60
    data_fetch_timeout: int = 30
    
    # Job storage
    job_storage_type: str = "memory"  # memory, redis, database
    job_retention_seconds: int = 86400  # 24 hours
    
    # Output settings
    output_retention_days: int = 30
    
    # Logging
    log_level: str = "INFO"
    enable_metrics: bool = True
    
    def __post_init__(self):
        """Initialize default paths if not provided."""
        if self.templates_metadata_dir is None:
            self.templates_metadata_dir = self.project_root / "config" / "generation" / "templates" / "metadata"
        
        if self.templates_files_dir is None:
            self.templates_files_dir = self.project_root / "config" / "generation" / "templates" / "files"
        
        if self.mappings_dir is None:
            self.mappings_dir = self.project_root / "config" / "generation" / "templates" / "mappings"
        
        if self.output_dir is None:
            self.output_dir = self.project_root / "generated_documents"
        
        if self.system_config_path is None:
            self.system_config_path = self.project_root / "config" / "generation" / "system.yaml"
        
        if self.renderers_config_path is None:
            self.renderers_config_path = self.project_root / "config" / "generation" / "renderers.yaml"
        
        if self.data_sources_config_path is None:
            self.data_sources_config_path = self.project_root / "config" / "generation" / "data_sources.yaml"
        
        if self.data_provision_config_path is None:
            self.data_provision_config_path = self.project_root / "config" / "generation" / "data_provision.yaml"
        
        # Ensure paths are Path objects
        self.project_root = Path(self.project_root)
        self.templates_metadata_dir = Path(self.templates_metadata_dir)
        self.templates_files_dir = Path(self.templates_files_dir)
        self.mappings_dir = Path(self.mappings_dir)
        self.output_dir = Path(self.output_dir)


# Global configuration instance
_config_instance: Optional[GenerationConfig] = None


def get_generation_config() -> GenerationConfig:
    """
    Get global generation config instance.
    
    Returns:
        GenerationConfig instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = GenerationConfig()
    return _config_instance


def set_generation_config(config: GenerationConfig) -> None:
    """
    Set global generation config instance.
    
    Args:
        config: GenerationConfig instance
    """
    global _config_instance
    _config_instance = config
