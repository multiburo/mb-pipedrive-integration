import json
import pytest
import responses
from unittest.mock import patch

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

        responses.add(
            responses.GET,
            f"{mock_service.base_url}/persons/123",
            json={
                "success": True,
                "data": {
                    "id": 123,
                    "name": "Existing Person",
                    "email": [{"value": "existing@example.com", "primary": True, "label": "work"}],
                    "phone": [],
                },
            },
            status=200,
        )

        result = mock_service.get_or_create_person("Existing Person", "existing@example.com")

        assert result is not None
        assert result["id"] == 123
        assert result["name"] == "Existing Person"

        # The exact email already matched and there is nothing to add: just the search
        assert [c.request.method for c in responses.calls] == ["GET"]

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

def _search_item(person_id, name, emails=(), phones=()):
    return {"item": {"id": person_id, "name": name, "emails": list(emails), "phones": list(phones)}}


def _person(person_id, name, emails=(), phones=()):
    return {
        "id": person_id,
        "name": name,
        "email": [{"value": v, "primary": i == 0, "label": "work"} for i, v in enumerate(emails)],
        "phone": [{"value": v, "primary": i == 0, "label": "work"} for i, v in enumerate(phones)],
    }


class TestPersonExactMatching:
    """get_or_create_person must never rewrite a person that is not exactly the same one """

    @staticmethod
    def _mock_search(service, items):
        responses.add(
            responses.GET,
            f"{service.base_url}/persons/search",
            json={"success": True, "data": {"items": items}},
            status=200,
        )

    @staticmethod
    def _mock_create(service, person_id=900):
        responses.add(
            responses.POST,
            f"{service.base_url}/persons",
            json={"success": True, "data": {"id": person_id, "name": "created"}},
            status=200,
        )

    @staticmethod
    def _methods():
        return [c.request.method for c in responses.calls]

    @responses.activate
    def test_similar_email_is_not_matched(self, mock_service):
        """ana@x.com must not match juana@x.com even if Pipedrive's fuzzy search returns it"""
        self._mock_search(mock_service, [_search_item(1, "Juana", emails=["juana@x.com"])])
        self._mock_create(mock_service)

        result = mock_service.get_or_create_person("Ana", "ana@x.com")

        assert result["id"] == 900
        assert self._methods() == ["GET", "POST"]

    @responses.activate
    def test_exact_email_match_is_case_insensitive_and_never_renames(self, mock_service):
        self._mock_search(mock_service, [_search_item(1, "Juana", emails=["Ana@X.com"])])
        responses.add(
            responses.GET,
            f"{mock_service.base_url}/persons/1",
            json={"success": True, "data": _person(1, "Ana Original", emails=["Ana@X.com"])},
            status=200,
        )
        responses.add(
            responses.PUT,
            f"{mock_service.base_url}/persons/1",
            json={"success": True, "data": {"id": 1, "name": "Ana Original"}},
            status=200,
        )

        mock_service.get_or_create_person("Otro Nombre", "ana@x.com", phone="+52 55 1234 5678")

        put_body = json.loads(responses.calls[-1].request.body)
        assert "name" not in put_body
        assert "POST" not in self._methods()

    @responses.activate
    def test_phone_is_appended_to_existing_list(self, mock_service):
        self._mock_search(mock_service, [_search_item(1, "Ana", emails=["ana@x.com"])])
        responses.add(
            responses.GET,
            f"{mock_service.base_url}/persons/1",
            json={"success": True, "data": _person(1, "Ana", emails=["ana@x.com"], phones=["5511111111"])},
            status=200,
        )
        responses.add(
            responses.PUT,
            f"{mock_service.base_url}/persons/1",
            json={"success": True, "data": {"id": 1}},
            status=200,
        )

        mock_service.get_or_create_person("Ana", "ana@x.com", phone="5522222222")

        put_body = json.loads(responses.calls[-1].request.body)
        assert [p["value"] for p in put_body["phone"]] == ["5511111111", "5522222222"]
        assert [p["primary"] for p in put_body["phone"]] == [True, False]
        assert "email" not in put_body

    @responses.activate
    def test_known_phone_in_other_format_is_not_added_again(self, mock_service):
        self._mock_search(mock_service, [_search_item(1, "Ana", emails=["ana@x.com"])])
        responses.add(
            responses.GET,
            f"{mock_service.base_url}/persons/1",
            json={"success": True, "data": _person(1, "Ana", emails=["ana@x.com"], phones=["+52 1 55 1111 1111"])},
            status=200,
        )

        mock_service.get_or_create_person("Ana", "ana@x.com", phone="5511111111")

        assert "PUT" not in self._methods()

    @responses.activate
    def test_search_is_exact_and_url_encoded(self, mock_service):
        self._mock_search(mock_service, [])
        self._mock_create(mock_service)

        mock_service.get_or_create_person("Juan", "juan+tag@x.com")

        url = responses.calls[0].request.url
        assert "fields=email" in url
        assert "exact_match=true" in url
        assert "term=juan%2Btag%40x.com" in url

    @responses.activate
    def test_shared_office_phone_does_not_match_when_email_differs(self, mock_service):
        """A new advisor sharing an office phone with another person is created, not merged into them"""
        self._mock_search(mock_service, [])
        self._mock_create(mock_service)

        mock_service.get_or_create_person("Asesora Nueva", "nueva@x.com", phone="55 5555 0000")

        assert self._methods() == ["GET", "POST"]



    @responses.activate
    def test_lookup_failure_does_not_create_a_duplicate(self, mock_service):
        responses.add(
            responses.GET,
            f"{mock_service.base_url}/persons/search",
            json={"success": False},
            status=500,
        )

        assert mock_service.get_or_create_person("Ana", "ana@x.com") is None
        assert "POST" not in self._methods()

    @responses.activate
    def test_unusable_search_response_does_not_create_a_duplicate(self, mock_service):
        """2xx with success=false is not "nobody matches"; it must not end in a new person"""
        responses.add(
            responses.GET,
            f"{mock_service.base_url}/persons/search",
            json={"success": False},
            status=200,
        )

        assert mock_service.get_or_create_person("Ana", "ana@x.com") is None
        assert self._methods() == ["GET"]

    @responses.activate
    def test_deal_is_not_created_when_a_participant_lookup_fails(self, mock_service, sample_deal_data):
        responses.add(
            responses.GET,
            f"{mock_service.base_url}/persons/search",
            json={"success": False},
            status=200,
        )

        assert mock_service.create_deal(sample_deal_data) is None
        assert self._methods() == ["GET"]

    @responses.activate
    def test_unexpected_errors_are_not_swallowed_by_create_deal(self, mock_service, sample_deal_data):
        with patch.object(mock_service, "get_or_create_person", side_effect=KeyError("bug")):
            with pytest.raises(KeyError):
                mock_service.create_deal(sample_deal_data)

    @staticmethod
    def _service_with_person_fields():
        from mb_pipedrive_integration import PipedriveService

        return PipedriveService(
            PipedriveConfig(domain="test-domain", api_token="t", custom_fields={"person_rfc": "rfc_hash"})
        )

    @responses.activate
    def test_custom_field_already_set_sends_no_put(self):
        service = self._service_with_person_fields()
        self._mock_search(service, [_search_item(1, "Ana", emails=["ana@x.com"])])
        responses.add(
            responses.GET,
            f"{service.base_url}/persons/1",
            json={"success": True, "data": {**_person(1, "Ana", emails=["ana@x.com"]), "rfc_hash": "ABC"}},
            status=200,
        )

        service.get_or_create_person("Ana", "ana@x.com", custom_fields={"rfc": "ABC"})

        assert self._methods() == ["GET", "GET"]

    @responses.activate
    def test_changed_custom_field_is_sent_alone(self):
        service = self._service_with_person_fields()
        self._mock_search(service, [_search_item(1, "Ana", emails=["ana@x.com"])])
        responses.add(
            responses.GET,
            f"{service.base_url}/persons/1",
            json={"success": True, "data": {**_person(1, "Ana", emails=["ana@x.com"]), "rfc_hash": "OLD"}},
            status=200,
        )
        responses.add(
            responses.PUT,
            f"{service.base_url}/persons/1",
            json={"success": True, "data": {"id": 1}},
            status=200,
        )

        service.get_or_create_person("Ana", "ana@x.com", custom_fields={"rfc": "NEW"})

        assert json.loads(responses.calls[-1].request.body) == {"rfc_hash": "NEW"}

    @responses.activate
    def test_email_only_match_does_not_load_the_person(self, mock_service):
        self._mock_search(mock_service, [_search_item(1, "Ana", emails=["ana@x.com"])])

        result = mock_service.get_or_create_person("Ana", "ana@x.com")

        assert result["id"] == 1
        assert self._methods() == ["GET"]

    @responses.activate
    def test_phone_alone_never_matches_an_existing_person(self, mock_service):
        self._mock_create(mock_service)

        result = mock_service.get_or_create_person("Carlos Ruiz", phone="5512345678")

        assert result["id"] == 900
        assert self._methods() == ["POST"]
