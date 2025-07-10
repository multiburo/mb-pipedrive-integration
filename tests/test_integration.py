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

    def test_add_deal_tags_real_api(self, integration_service):
        """Test adding tags to a deal with real API"""
        # First create a minimal deal for testing
        deal_data = DealData(
            title="Tag Test Deal",
            folder_number=99999,
            folder_id="tag-test-001"
        )

        deal = integration_service.create_deal(deal_data)
        assert deal is not None

        deal_id = deal["id"]

        try:
            # Test adding tags
            test_tags = ["TEST_TAG_1", "TEST_TAG_2"]
            result = integration_service.add_deal_tags(deal_id, test_tags)
            assert result is True

            # Test adding more tags (should merge with existing)
            additional_tags = ["TEST_TAG_3", "TEST_TAG_1"]  # TEST_TAG_1 is duplicate
            result = integration_service.add_deal_tags(deal_id, additional_tags)
            assert result is True

            # Verify the deal has the expected tags by getting it
            deal_response = integration_service._make_request("GET", f"deals/{deal_id}")
            assert deal_response["success"] is True

            deal_data = deal_response["data"]
            deal_labels = deal_data.get("label", "")

            # Should have 3 unique tags
            if deal_labels:
                tags_set = set(tag.strip() for tag in deal_labels.split(",") if tag.strip())
                expected_tags = {"TEST_TAG_1", "TEST_TAG_2", "TEST_TAG_3"}
                assert expected_tags.issubset(tags_set)

        finally:
            # Cleanup: Delete the test deal
            try:
                integration_service._make_request("DELETE", f"deals/{deal_id}")
            except Exception as e:
                print(f"Warning: Could not cleanup test deal {deal_id}: {e}")
