import pytest
import os
from mb_pipedrive_integration.dataclasses import DealData

# Skip integration tests unless explicitly enabled
pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests",
)


class TestPipedriveServiceIntegration:
    """Integration tests with real Pipedrive sandbox"""

    def test_create_and_cleanup_person(self, integration_service):
        """Test person creation and cleanup with real API"""
        # Create test person
        person = integration_service.create_person(
            name="Integration Test Person", email="integration@test.com", role="tenant"
        )

        assert person is not None
        assert person["name"] == "Integration Test Person"
        assert "INQUILINO" in person.get("label", "")

        # Cleanup: In real tests, you might want to delete the created person
        # Note: Implement cleanup logic if needed

    def test_find_existing_person(self, integration_service):
        """Test finding an existing person"""
        # First create a person
        created = integration_service.create_person(
            name="Find Test Person", email="findtest@example.com"
        )
        assert created is not None

        # Then try to find it
        found = integration_service.find_person_by_email("findtest@example.com")
        assert found is not None
        assert found["id"] == created["id"]

    def test_create_minimal_deal(self, integration_service):
        """Test creating a minimal deal with real API"""
        deal_data = DealData(
            title="Integration Test Deal", folder_number=99999, folder_id="integration-test-uuid"
        )

        deal = integration_service.create_deal(deal_data)

        assert deal is not None
        assert deal["title"] == "Integration Test Deal"

        # Cleanup: Delete the test deal if needed
