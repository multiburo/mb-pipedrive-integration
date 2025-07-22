import json
import pytest
import responses

from mb_pipedrive_integration.dataclasses import PipedriveConfig
from mb_pipedrive_integration.exceptions import PipedriveConfigError
from mb_pipedrive_integration.dataclasses import OrganizationData


class TestPipedriveServiceUnit:
    """Unit tests with mocked HTTP calls"""

    @responses.activate
    def test_create_person_success(self, mock_service, mock_pipedrive_responses):
        """Test person creation with mocked API"""
        # Mock the API response
        responses.add(
            responses.POST,
            f"{mock_service.base_url}/persons",
            json={"success": True, "data": {"id": 123, "name": "Test Person"}},
            status=200,
        )

        result = mock_service.create_person("Test Person", "test@example.com", tags=["INQUILINO"])

        assert result is not None
        assert result["id"] == 123
        assert result["name"] == "Test Person"

        # Verify the request was made correctly
        assert len(responses.calls) == 1

        # Fix: Access request body properly
        request_body = responses.calls[0].request.body
        if isinstance(request_body, bytes):
            request_body = request_body.decode("utf-8")
        request_data = json.loads(request_body)

        assert request_data["name"] == "Test Person"
        assert request_data["email"] == "test@example.com"
        assert "INQUILINO" in request_data["label"]

    @responses.activate
    def test_create_person_with_tags(self, mock_service):
        """Test person creation with custom tags"""
        responses.add(
            responses.POST,
            f"{mock_service.base_url}/persons",
            json={"success": True, "data": {"id": 124, "name": "Test Person"}},
            status=200,
        )

        result = mock_service.create_person(
            "Test Person", "test@example.com", tags=["Custom Tag", "Another Tag"]
        )

        assert result is not None

        # Verify tags were included (check for tags without spaces after comma)
        request_body = responses.calls[0].request.body
        if isinstance(request_body, bytes):
            request_body = request_body.decode("utf-8")
        request_data = json.loads(request_body)

        # The service might join tags without spaces
        assert "Custom Tag" in request_data["label"]
        assert "Another Tag" in request_data["label"]

    @responses.activate
    def test_find_person_by_email_found(self, mock_service):
        """Test finding an existing person by email"""
        responses.add(
            responses.GET,
            f"{mock_service.base_url}/persons/search",
            json={
                "success": True,
                "data": {
                    "items": [
                        {
                            "item": {
                                "id": 123,
                                "name": "Found Person",
                                "emails": [{"value": "test@example.com"}],
                            }
                        }
                    ]
                },
            },
            status=200,
        )

        result = mock_service.find_person_by_email("test@example.com")

        assert result is not None
        assert result["id"] == 123
        assert result["name"] == "Found Person"

    @responses.activate
    def test_find_person_by_email_not_found(self, mock_service):
        """Test finding a person that doesn't exist"""
        responses.add(
            responses.GET,
            f"{mock_service.base_url}/persons/search",
            json={"success": True, "data": {"items": []}},
            status=200,
        )

        result = mock_service.find_person_by_email("notfound@example.com")
        assert result is None

    @responses.activate
    @responses.activate
    def test_create_organization_success(self, mock_service):
        """Test organization creation with custom_fields"""
        responses.add(
            responses.POST,
            f"{mock_service.base_url}/organizations",
            json={"success": True, "data": {"id": 456, "name": "Integration Test Org"}},
            status=200,
        )

        org_data = OrganizationData(name="Integration Test Org")
        result = mock_service.create_organization(org_data)

        assert result is not None
        assert result["id"] == 456
        assert result["name"] == "Integration Test Org"

    @responses.activate
    def test_create_organization_with_custom_fields(self, mock_service):
        """Test organization creation with custom fields"""

        # Set up mock service with custom fields configuration
        mock_service.config.custom_fields = {
            "org_mb_id": "a1b2c3d4e5f6g7h8"  # Mock Pipedrive custom field hash
        }

        # Mock the API response
        responses.add(
            responses.POST,
            f"{mock_service.base_url}/organizations",
            json={
                "success": True,
                "data": {
                    "id": 999,
                    "name": "Test Org with Custom Fields",
                    "a1b2c3d4e5f6g7h8": "test-uuid-123"  # Custom field in response
                }
            },
            status=200
        )

        # Create OrganizationData with custom fields
        org_data = OrganizationData(
            name="Test Org with Custom Fields",
            custom_fields={"mb_id": "test-uuid-123"}
        )

        result = mock_service.create_organization(org_data)

        assert result is not None
        assert result["name"] == "Test Org with Custom Fields"
        assert result["id"] == 999

        # Verify the request data included custom field
        request_body = responses.calls[0].request.body
        request_data = json.loads(request_body.decode('utf-8'))

        assert request_data["name"] == "Test Org with Custom Fields"
        # The custom field should be mapped to the Pipedrive hash
        assert "a1b2c3d4e5f6g7h8" in request_data
        assert request_data["a1b2c3d4e5f6g7h8"] == "test-uuid-123"

    # Alternative test approach - if you want to test without setting up custom_fields
    @responses.activate
    def test_create_organization_with_custom_fields_no_mapping(self, mock_service):
        """Test organization creation with custom fields but no mapping configured"""

        # Don't set up custom_fields mapping
        mock_service.config.custom_fields = None

        responses.add(
            responses.POST,
            f"{mock_service.base_url}/organizations",
            json={
                "success": True,
                "data": {
                    "id": 999,
                    "name": "Test Org with Custom Fields"
                }
            },
            status=200
        )

        org_data = OrganizationData(
            name="Test Org with Custom Fields",
            custom_fields={"mb_id": "test-uuid-123"}
        )

        result = mock_service.create_organization(org_data)

        assert result is not None
        assert result["name"] == "Test Org with Custom Fields"

        # Verify only the name was sent (no custom fields without mapping)
        request_body = responses.calls[0].request.body
        request_data = json.loads(request_body.decode('utf-8'))

        assert request_data["name"] == "Test Org with Custom Fields"
        # No custom field hashes should be present
        assert len(request_data) == 1  # Only name field

    @responses.activate
    def test_create_deal_full_workflow(
        self, mock_service, sample_deal_data, mock_pipedrive_responses
    ):
        """Test complete deal creation workflow"""
        base_url = mock_service.base_url

        # Mock person search (not found) for tenant
        responses.add(
            responses.GET,
            f"{base_url}/persons/search",
            json={"success": True, "data": {"items": []}},
            status=200,
        )

        # Mock person creation for tenant
        responses.add(
            responses.POST,
            f"{base_url}/persons",
            json={"success": True, "data": {"id": 123, "name": "Test Tenant"}},
            status=200,
        )

        # Mock person search (not found) for advisor
        responses.add(
            responses.GET,
            f"{base_url}/persons/search",
            json={"success": True, "data": {"items": []}},
            status=200,
        )

        # Mock person creation for advisor
        responses.add(
            responses.POST,
            f"{base_url}/persons",
            json={"success": True, "data": {"id": 124, "name": "Test Advisor"}},
            status=200,
        )

        # Mock organization search (not found)
        responses.add(
            responses.GET,
            f"{base_url}/organizations/search",
            json={"success": True, "data": {"items": []}},
            status=200,
        )

        # Mock organization creation
        responses.add(
            responses.POST,
            f"{base_url}/organizations",
            json={"success": True, "data": {"id": 456, "name": "Test Organization"}},
            status=200,
        )

        # Mock deal creation
        responses.add(
            responses.POST,
            f"{base_url}/deals",
            json={"success": True, "data": {"id": 789, "title": "Test Deal"}},
            status=200,
        )

        # Mock notes creation
        responses.add(
            responses.POST,
            f"{base_url}/notes",
            json={"success": True, "data": {"id": 999}},
            status=200,
        )

        result = mock_service.create_deal(sample_deal_data)

        assert result is not None
        assert result["id"] == 789
        assert result["title"] == "Test Deal"

        # Verify the expected number of API calls (might be fewer if no landlord in sample data)
        # 2 person searches + 2 person creates + 1 org search + 1 org create + 1 deal create + 1 note create
        assert len(responses.calls) >= 6  # At least 6 calls, could be more depending on sample data

    def test_config_from_env(self, monkeypatch):
        """Test configuration from environment variables"""
        monkeypatch.setenv("PIPEDRIVE_COMPANY_DOMAIN", "test-domain")
        monkeypatch.setenv("PIPEDRIVE_API_TOKEN", "test-token")
        monkeypatch.setenv("PIPEDRIVE_DEFAULT_PIPELINE_ID", "2")
        monkeypatch.setenv("PIPEDRIVE_DEFAULT_STAGE_ID", "3")

        config = PipedriveConfig.from_env()

        assert config.domain == "test-domain"
        assert config.api_token == "test-token"
        assert config.default_pipeline_id == "2"
        assert config.default_stage_id == "3"

    def test_config_from_env_missing_required(self, monkeypatch):
        """Test configuration with missing required environment variables"""
        # Clear any existing env vars
        monkeypatch.delenv("PIPEDRIVE_COMPANY_DOMAIN", raising=False)
        monkeypatch.delenv("PIPEDRIVE_API_TOKEN", raising=False)

        with pytest.raises(PipedriveConfigError, match="Missing required environment variables"):
            PipedriveConfig.from_env()

    @responses.activate
    def test_api_error_handling(self, mock_service):
        """Test handling of API errors"""
        responses.add(
            responses.POST,
            f"{mock_service.base_url}/persons",
            json={"success": False, "error": "Invalid data"},
            status=400,
        )

        result = mock_service.create_person("Test Person")
        assert result is None  # Should handle error gracefully

    @responses.activate
    def test_network_error_handling(self, mock_service):
        """Test handling of network errors"""
        responses.add(
            responses.POST,
            f"{mock_service.base_url}/persons",
            body=ConnectionError("Network error"),
        )

        result = mock_service.create_person("Test Person")
        assert result is None  # Should handle error gracefully

    @responses.activate
    def test_get_or_create_person_existing(self, mock_service):
        """Test get_or_create_person when person already exists"""
        # Mock person search (found)
        responses.add(
            responses.GET,
            f"{mock_service.base_url}/persons/search",
            json={
                "success": True,
                "data": {
                    "items": [
                        {
                            "item": {
                                "id": 123,
                                "name": "Existing Person",
                                "emails": [{"value": "existing@example.com"}],
                            }
                        }
                    ]
                },
            },
            status=200,
        )

        result = mock_service.get_or_create_person("Existing Person", "existing@example.com")

        assert result is not None
        assert result["id"] == 123
        assert result["name"] == "Existing Person"

        # Should only make search call, not create call
        assert len(responses.calls) == 1

    @responses.activate
    def test_get_or_create_person_new(self, mock_service):
        """Test get_or_create_person when person doesn't exist"""
        # Mock person search (not found)
        responses.add(
            responses.GET,
            f"{mock_service.base_url}/persons/search",
            json={"success": True, "data": {"items": []}},
            status=200,
        )

        # Mock person creation
        responses.add(
            responses.POST,
            f"{mock_service.base_url}/persons",
            json={"success": True, "data": {"id": 124, "name": "New Person"}},
            status=200,
        )

        result = mock_service.get_or_create_person("New Person", "new@example.com")

        assert result is not None
        assert result["id"] == 124
        assert result["name"] == "New Person"

        # Should make both search and create calls
        assert len(responses.calls) == 2

    @responses.activate
    def test_update_deal_stage(self, mock_service):
        """Test updating deal stage"""
        responses.add(
            responses.PUT,
            f"{mock_service.base_url}/deals/123",
            json={"success": True, "data": {"id": 123, "stage_id": 5}},
            status=200,
        )

        result = mock_service.update_deal_stage(123, "5")

        assert result is True

        # Verify the request was made correctly
        request_body = responses.calls[0].request.body
        if isinstance(request_body, bytes):
            request_body = request_body.decode("utf-8")
        request_data = json.loads(request_body)

        assert request_data["stage_id"] == 5

    @responses.activate
    def test_close_deal(self, mock_service):
        """Test closing a deal"""
        responses.add(
            responses.PUT,
            f"{mock_service.base_url}/deals/123",
            json={"success": True, "data": {"id": 123, "status": "won"}},
            status=200,
        )

        result = mock_service.close_deal(123, "won")

        assert result is True

        # Verify the request was made correctly
        request_body = responses.calls[0].request.body
        if isinstance(request_body, bytes):
            request_body = request_body.decode("utf-8")
        request_data = json.loads(request_body)

        assert request_data["status"] == "won"

    @responses.activate
    def test_add_deal_tags_integration(self, mock_service):
        """Test add_deal_tags method integration"""
        deal_id = 456
        tags = ["INQUILINO", "MULTIREPORTE"]

        # Mock GET current deal
        responses.add(
            responses.GET,
            f"{mock_service.base_url}/deals/{deal_id}",
            json={
                "success": True,
                "data": {
                    "id": deal_id,
                    "title": "Integration Test Deal",
                    "label": "EXISTING"
                }
            },
            status=200
        )

        # Mock PUT update
        responses.add(
            responses.PUT,
            f"{mock_service.base_url}/deals/{deal_id}",
            json={
                "success": True,
                "data": {
                    "id": deal_id,
                    "title": "Integration Test Deal",
                    "label": "EXISTING,INQUILINO,MULTIREPORTE"
                }
            },
            status=200
        )

        result = mock_service.add_deal_tags(deal_id, tags)

        assert result is True
        assert len(responses.calls) == 2

    @responses.activate
    def test_add_deal_tags_network_error(self, mock_service):
        """Test add_deal_tags with network error"""
        deal_id = 789
        tags = ["TEST_TAG"]

        # Mock network error on GET
        responses.add(
            responses.GET,
            f"{mock_service.base_url}/deals/{deal_id}",
            body=ConnectionError("Network error")
        )

        result = mock_service.add_deal_tags(deal_id, tags)

        assert result is False