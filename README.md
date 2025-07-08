# Multiburo Pipedrive Integration

A Django-compatible Python package for seamless Pipedrive CRM integration.

## Features

- 🏷️ **Flexible tagging system** for person classification
- 🛡️ **Robust error handling** with custom exceptions
- 📊 **Comprehensive logging** for debugging and monitoring
- 🧪 **Thoroughly tested** with 95%+ test coverage

## Installation

### For Production
```bash
pip install mb-pipedrive-integration
```

### Local Development
```bash
git clone <repository-url>
cd mb-pipedrive-integration
uv sync --extra dev
uv run pre-commit install
```

## Quick Start

### 1. Configure Settings

#### Django Settings
```python
# settings.py
PIPEDRIVE_COMPANY_DOMAIN = "your-company"
PIPEDRIVE_API_TOKEN = "your-api-token"
PIPEDRIVE_DEFAULT_PIPELINE_ID = "1"
PIPEDRIVE_DEFAULT_STAGE_ID = "1"
PIPEDRIVE_CUSTOM_FIELDS = {
    "folder_number": "custom_field_hash_1",
    "folder_id": "custom_field_hash_2",
}
```

#### Environment Variables
```bash
export PIPEDRIVE_COMPANY_DOMAIN="your-company"
export PIPEDRIVE_API_TOKEN="your-api-token"
```

### 2. Basic Usage

```python
from mb_pipedrive_integration import PipedriveService, DealData, PersonData

# Initialize service
service = PipedriveService()

# Create a person
person = service.create_person(
    name="John Doe",
    email="john@example.com",
    tags=["Multiexpediente"]
)

# Create a deal
deal_data = DealData(
    title="Apartment Rental",
    folder_number=12345,
    folder_id="abc-123",
    tenant=PersonData(name="John Doe", email="john@example.com", tags=["INQUILINO"])
)

deal = service.create_deal(deal_data)
```

### 3. Django Integration with Celery

```python
# tasks.py
from celery import shared_task
from mb_pipedrive_integration import PipedriveService, DealData
from .adapters import FolderToPipedriveAdapter

@shared_task
def sync_folder_with_pipedrive(folder_id: str):
    folder = Folder.objects.get(id=folder_id)
    deal_data = FolderToPipedriveAdapter.to_deal_data(folder)
    
    service = PipedriveService()
    result = service.create_deal(deal_data)
    
    if result:
        folder.metadata['pipedrive_deal_id'] = result['id']
        folder.save()
```

## Role Mapping

The package automatically maps roles to Pipedrive tags:

| Role | Pipedrive Tag |
|------|---------------|
| `tenant` | INQUILINO |
| `advisor` | ASESOR INMOBILIARIO |
| `landlord` | PROPIETARIO |

## Error Handling

```python
from mb_pipedrive_integration.exceptions import (
    PipedriveAPIError,
    PipedriveNetworkError,
    PipedriveConfigError
)

try:
    person = service.create_person("John Doe")
except PipedriveAPIError as e:
    print(f"API Error: {e.status_code} - {e}")
except PipedriveNetworkError as e:
    print(f"Network Error: {e} (retried {e.retry_count} times)")
except PipedriveConfigError as e:
    print(f"Configuration Error: {e}")
```

## Development

### Running Tests
```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=mb_pipedrive_integration --cov-report=term-missing

# Integration tests (requires real API credentials)
uv run pytest tests/test_integration.py --integration
```

### Code Quality
```bash
# Run all pre-commit hooks
uv run pre-commit run --all-files

# Individual tools
uv run black .
uv run flake8
uv run mypy mb_pipedrive_integration/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Run pre-commit hooks
7. Submit a pull request

## License

**MIT License**

Copyright © 2025 Multiburó

See the [LICENSE](LICENSE) file for details.

## Support

For questions or issues, please open an issue on GitHub.