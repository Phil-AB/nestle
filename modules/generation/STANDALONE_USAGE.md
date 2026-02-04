# Standalone Usage Guide

## Generation Module as Standalone Library

The generation module is now **100% modular** and can be used independently in any Python project.

## Installation

### Option 1: Copy Module
```bash
# Copy the generation module to your project
cp -r modules/generation /path/to/your/project/
cp -r modules/generation/config.py /path/to/your/project/generation/

# Install dependencies
pip install python-docx pyyaml sqlalchemy asyncpg pydantic
```

### Option 2: Pip Install (future)
```bash
pip install nestle-generation-module
```

## Basic Usage

### 1. Simple Setup (Using Defaults)

```python
from generation.engine import GenerationEngine
from generation.config import GenerationConfig, set_generation_config
from pathlib import Path

# Configure paths
config = GenerationConfig(
    project_root=Path("/path/to/your/project"),
    output_dir=Path("/path/to/output")
)
set_generation_config(config)

# Initialize engine
engine = GenerationEngine()

# Generate document
result = await engine.generate({
    "template_id": "my_template",
    "data_source": {
        "provider": "static",
        "query": {"data_key": "test_data"}
    }
})

print(f"Generated: {result.output_path}")
```

### 2. Custom Database Connection

```python
from generation.data_providers.db_interface import CustomDatabaseConnection
from generation.data_providers.postgres_provider import PostgresDataProvider
from generation.config import GenerationConfig

# Custom database
db_connection = CustomDatabaseConnection(
    connection_string="postgresql+asyncpg://user:pass@localhost/mydb",
    pool_size=10
)

# Use with provider
provider = PostgresDataProvider(
    config={"name": "postgres"},
    db_connection=db_connection
)

# Fetch data
data = await provider.fetch_data({"document_id": "123"})
```

### 3. Custom Job Storage

```python
from generation.storage.job_storage import IJobStorage, JobData
from generation.engine import GenerationEngine

# Implement custom storage (e.g., Redis)
class RedisJobStorage(IJobStorage):
    def __init__(self, redis_url):
        import redis.asyncio as redis
        self.redis = redis.from_url(redis_url)
    
    async def save_job(self, job_id, job_data):
        await self.redis.set(
            f"job:{job_id}",
            json.dumps(job_data.to_dict()),
            ex=86400  # 24h expiry
        )
        return True
    
    async def get_job(self, job_id):
        data = await self.redis.get(f"job:{job_id}")
        return JobData(**json.loads(data)) if data else None
    
    # ... implement other methods

# Use custom storage
job_storage = RedisJobStorage("redis://localhost:6379")
engine = GenerationEngine(job_storage=job_storage)
```

### 4. Complete Standalone Example

```python
"""
Standalone document generation without any project dependencies.
"""

import asyncio
from pathlib import Path
from generation.engine import GenerationEngine
from generation.config import GenerationConfig, set_generation_config
from generation.data_providers.db_interface import CustomDatabaseConnection
from generation.storage.job_storage import InMemoryJobStorage

async def main():
    # 1. Configure module
    config = GenerationConfig(
        project_root=Path("/my/project"),
        templates_metadata_dir=Path("/my/project/templates/metadata"),
        templates_files_dir=Path("/my/project/templates/files"),
        mappings_dir=Path("/my/project/templates/mappings"),
        output_dir=Path("/my/project/output"),
        max_concurrent_jobs=50,
        generation_timeout=120
    )
    set_generation_config(config)
    
    # 2. Setup custom database (if needed)
    db_connection = CustomDatabaseConnection(
        connection_string="postgresql+asyncpg://user:pass@localhost/db",
        pool_size=5,
        echo=False
    )
    
    # 3. Setup job storage
    job_storage = InMemoryJobStorage()
    
    # 4. Initialize engine
    engine = GenerationEngine(
        config=config,
        job_storage=job_storage
    )
    
    # 5. Generate document
    result = await engine.generate({
        "template_id": "invoice_template",
        "mapping_id": "invoice_mapping",
        "data_source": {
            "provider": "postgres",
            "query": {"document_id": "doc-123"}
        }
    })
    
    if result.success:
        print(f"✅ Document generated: {result.output_path}")
        print(f"   Time: {result.generation_time_ms}ms")
    else:
        print(f"❌ Generation failed: {result.error_message}")
    
    # 6. Cleanup
    await db_connection.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Dependencies (Minimal)

**Required:**
- `python-docx` - For DOCX rendering
- `pyyaml` - For config files
- `pydantic` - For data validation

**Optional:**
- `sqlalchemy` + `asyncpg` - Only if using PostgresDataProvider
- `redis` - Only if using RedisJobStorage
- Custom renderer dependencies as needed

## No Dependencies On:
- ✅ Project database layer
- ✅ Project logging setup
- ✅ Project configuration
- ✅ FastAPI/web framework
- ✅ UI components
- ✅ Authentication

## Architecture

```
generation/
  ├── core/              # Pure interfaces, no dependencies
  ├── data_providers/    # Pluggable data sources
  │   ├── db_interface.py       # Database abstraction
  │   ├── postgres_provider.py  # PostgreSQL implementation
  │   └── static_provider.py    # Static data
  ├── renderers/         # Pluggable renderers
  │   └── docx_renderer.py
  ├── mappers/           # Data transformation
  │   └── field_mapper.py
  ├── storage/           # Job storage abstraction
  │   └── job_storage.py
  ├── templates/         # Template management
  ├── config.py          # Configuration
  └── engine.py          # Orchestrator
```

## Modularity Score: 100%

All hard dependencies removed. Module can be:
- Used standalone in any Python project
- Integrated with different databases
- Deployed with different storage backends
- Extended with custom components
- Packaged as standalone library
