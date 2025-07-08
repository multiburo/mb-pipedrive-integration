import pytest
import os
from mb_pipedrive_integration import PipedriveService, PipedriveConfig
from mb_pipedrive_integration.dataclasses import PersonData, DealData


@pytest.fixture
def mock_config():
    """Test configuration with mock values"""
    return PipedriveConfig(
        domain="test-domain",
        api_token="test-token",
        default_pipeline_id="1",
        default_stage_id="1",
        custom_fields={
            "folder_number": "test_folder_field",
            "folder_id": "test_folder_id_field",
        },
    )


@pytest.fixture
def sandbox_config():
    """Real sandbox configuration for integration tests"""
    return PipedriveConfig(
        domain=os.getenv("PIPEDRIVE_SANDBOX_DOMAIN", "test-sandbox"),
        api_token=os.getenv("PIPEDRIVE_SANDBOX_TOKEN", "test-token"),
        default_pipeline_id="1",
        default_stage_id="1",
    )


@pytest.fixture
def mock_service(mock_config):
    """PipedriveService with mock configuration"""
    return PipedriveService(config=mock_config)


@pytest.fixture
def integration_service(sandbox_config):
    """PipedriveService with real sandbox configuration"""
    return PipedriveService(config=sandbox_config)


@pytest.fixture
def sample_person_data():
    """Sample person data for testing"""
    return PersonData(
        name="Test Person", email="test@example.com", phone="+1234567890", role="tenant"
    )


@pytest.fixture
def sample_deal_data():
    """Sample deal data for testing"""
    return DealData(
        title="Test Deal",
        folder_number=12345,
        folder_id="test-folder-uuid",
        tenant=PersonData(name="John Tenant", email="john@test.com", tags=["INQUILINO"]),
        advisor=PersonData(name="Jane Advisor", email="jane@company.com", tags=["ASESOR INMOBILIARIO"]),
        property_address="123 Test Street",
        multiexpediente_url="https://test.com/folders/test-uuid",
    )


@pytest.fixture
def mock_pipedrive_responses():
    """Standard mock responses for Pipedrive API"""
    return {
        "person_created": {
            "success": True,
            "data": {
                "id": 123,
                "name": "Test Person",
                "email": [{"value": "test@example.com", "primary": True}],
            },
        },
        "organization_created": {"success": True, "data": {"id": 456, "name": "Test Organization"}},
        "deal_created": {"success": True, "data": {"id": 789, "title": "Test Deal", "stage_id": 1}},
        "search_empty": {"success": True, "data": {"items": []}},
    }
