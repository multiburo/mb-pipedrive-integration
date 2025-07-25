import pytest
from unittest.mock import patch

from mb_pipedrive_integration.dataclasses import (
    PersonData,
    OrganizationData,
    DealData,
    ProductData,
    PipedriveConfig,
)
from mb_pipedrive_integration.exceptions import PipedriveConfigError, PipedriveValidationError


class TestPersonData:
    """Test PersonData validation and functionality"""

    def test_valid_person_data(self):
        """Test creating valid person data"""
        person = PersonData(
            name="John Doe", email="john@example.com", phone="+1234567890", tags=["ASESOR INMOBILIARIO"]
        )
        assert person.name == "John Doe"
        assert person.email == "john@example.com"
        assert person.tags == ["ASESOR INMOBILIARIO"]

    def test_person_with_minimal_data(self):
        """Test person with only required fields"""
        person = PersonData(name="Jane Doe")
        assert person.name == "Jane Doe"
        assert person.email is None
        assert person.phone is None
        assert person.tags is None

    def test_empty_name_raises_error(self):
        """Test that empty name raises validation error"""
        with pytest.raises(PipedriveValidationError, match="Person name cannot be empty"):
            PersonData(name="")

    def test_whitespace_name_raises_error(self):
        """Test that whitespace-only name raises validation error"""
        with pytest.raises(PipedriveValidationError, match="Person name cannot be empty"):
            PersonData(name="   ")

    def test_invalid_email_raises_error(self):
        """Test that invalid email raises validation error"""
        with pytest.raises(PipedriveValidationError, match="Invalid email format"):
            PersonData(name="John Doe", email="invalid-email")

    def test_valid_emails(self):
        """Test various valid email formats"""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "test+tag@example.org",
            "123@numbers.com",
        ]

        for email in valid_emails:
            person = PersonData(name="Test User", email=email)
            assert person.email == email

class TestOrganizationData:
    """Test OrganizationData validation"""

    def test_valid_organization(self):
        """Test creating valid organization data"""
        org = OrganizationData(name="Test Company")
        assert org.name == "Test Company"

    def test_empty_name_raises_error(self):
        """Test that empty organization name raises error"""
        with pytest.raises(PipedriveValidationError, match="Organization name cannot be empty"):
            OrganizationData(name="")

    def test_whitespace_name_raises_error(self):
        """Test that whitespace-only name raises error"""
        with pytest.raises(PipedriveValidationError, match="Organization name cannot be empty"):
            OrganizationData(name="   ")


class TestOrganizationDataWithCustomFields:
    """Test OrganizationData with custom fields support"""

    def test_organization_with_custom_fields(self):
        """Test creating organization with custom fields"""
        org = OrganizationData(
            name="Test Org",
            custom_fields={"mb_id": "test-uuid-123", "external_id": "ext-456"}
        )

        assert org.name == "Test Org"
        assert org.custom_fields["mb_id"] == "test-uuid-123"
        assert org.custom_fields["external_id"] == "ext-456"

    def test_organization_without_custom_fields(self):
        """Test creating organization without custom fields"""
        org = OrganizationData(name="Simple Org")

        assert org.name == "Simple Org"
        assert org.custom_fields is None

    def test_organization_with_empty_custom_fields(self):
        """Test creating organization with empty custom fields dict"""
        org = OrganizationData(name="Empty Fields Org", custom_fields={})

        assert org.name == "Empty Fields Org"
        assert org.custom_fields == {}

    def test_organization_name_validation_still_works(self):
        """Test that name validation still works with custom fields"""
        with pytest.raises(PipedriveValidationError, match="Organization name cannot be empty"):
            OrganizationData(name="", custom_fields={"mb_id": "test"})

        with pytest.raises(PipedriveValidationError, match="Organization name cannot be empty"):
            OrganizationData(name="   ", custom_fields={"mb_id": "test"})


class TestDealData:
    """Test DealData validation"""

    def test_valid_deal_data(self):
        """Test creating valid deal data"""
        deal = DealData(
            title="Test Deal",
            folder_number=12345,
            folder_id="abc-123",
            tenant=PersonData(name="Tenant Name"),
            advisor=PersonData(name="Advisor Name"),
        )
        assert deal.title == "Test Deal"
        assert deal.folder_number == 12345
        assert deal.folder_id == "abc-123"

    def test_minimal_deal_data(self):
        """Test deal with only required fields"""
        deal = DealData(title="Minimal Deal", folder_number=1, folder_id="min-1")
        assert deal.tenant is None
        assert deal.advisor is None
        assert deal.landlord is None

    def test_empty_title_raises_error(self):
        """Test that empty title raises error"""
        with pytest.raises(PipedriveValidationError, match="Deal title cannot be empty"):
            DealData(title="", folder_number=1, folder_id="test")

    def test_whitespace_title_raises_error(self):
        """Test that whitespace-only title raises error"""
        with pytest.raises(PipedriveValidationError, match="Deal title cannot be empty"):
            DealData(title="   ", folder_number=1, folder_id="test")

    def test_zero_folder_number_raises_error(self):
        """Test that zero folder number raises error"""
        with pytest.raises(PipedriveValidationError, match="folder_number must be positive"):
            DealData(title="Test", folder_number=0, folder_id="test")

    def test_negative_folder_number_raises_error(self):
        """Test that negative folder number raises error"""
        with pytest.raises(PipedriveValidationError, match="folder_number must be positive"):
            DealData(title="Test", folder_number=-1, folder_id="test")

    def test_empty_folder_id_raises_error(self):
        """Test that empty folder_id raises error"""
        with pytest.raises(PipedriveValidationError, match="folder_id cannot be empty"):
            DealData(title="Test", folder_number=1, folder_id="")

    def test_whitespace_folder_id_raises_error(self):
        """Test that whitespace-only folder_id raises error"""
        with pytest.raises(PipedriveValidationError, match="folder_id cannot be empty"):
            DealData(title="Test", folder_number=1, folder_id="   ")


class TestPipedriveConfig:
    """Test PipedriveConfig validation and creation"""

    def test_valid_config(self):
        """Test creating valid config"""
        config = PipedriveConfig(
            domain="test-domain",
            api_token="test-token",
            default_pipeline_id="2",
            default_stage_id="3",
        )
        assert config.domain == "test-domain"
        assert config.api_token == "test-token"
        assert config.default_pipeline_id == "2"
        assert config.default_stage_id == "3"

    def test_base_url_property(self):
        """Test base_url property construction"""
        config = PipedriveConfig(domain="my-company", api_token="token")
        assert config.base_url == "https://my-company.pipedrive.com/v1"

    def test_empty_domain_raises_error(self):
        """Test that empty domain raises error"""
        with pytest.raises(PipedriveConfigError, match="Pipedrive domain cannot be empty"):
            PipedriveConfig(domain="", api_token="token")

    def test_empty_api_token_raises_error(self):
        """Test that empty API token raises error"""
        with pytest.raises(PipedriveConfigError, match="Pipedrive API token cannot be empty"):
            PipedriveConfig(domain="domain", api_token="")

    def test_whitespace_domain_raises_error(self):
        """Test that whitespace-only domain raises error"""
        with pytest.raises(PipedriveConfigError, match="Pipedrive domain cannot be empty"):
            PipedriveConfig(domain="   ", api_token="token")

    def test_default_values(self):
        """Test default pipeline and stage IDs"""
        config = PipedriveConfig(domain="test", api_token="token")
        assert config.default_pipeline_id == "1"
        assert config.default_stage_id == "1"
        assert config.custom_fields is None

    def test_from_env_success(self, monkeypatch):
        """Test successful config creation from environment"""
        monkeypatch.setenv("PIPEDRIVE_COMPANY_DOMAIN", "env-domain")
        monkeypatch.setenv("PIPEDRIVE_API_TOKEN", "env-token")
        monkeypatch.setenv("PIPEDRIVE_DEFAULT_PIPELINE_ID", "5")
        monkeypatch.setenv("PIPEDRIVE_DEFAULT_STAGE_ID", "10")

        config = PipedriveConfig.from_env()

        assert config.domain == "env-domain"
        assert config.api_token == "env-token"
        assert config.default_pipeline_id == "5"
        assert config.default_stage_id == "10"

    def test_from_env_minimal(self, monkeypatch):
        """Test config from env with only required variables"""
        monkeypatch.setenv("PIPEDRIVE_COMPANY_DOMAIN", "minimal-domain")
        monkeypatch.setenv("PIPEDRIVE_API_TOKEN", "minimal-token")
        # Clear optional vars
        monkeypatch.delenv("PIPEDRIVE_DEFAULT_PIPELINE_ID", raising=False)
        monkeypatch.delenv("PIPEDRIVE_DEFAULT_STAGE_ID", raising=False)

        config = PipedriveConfig.from_env()

        assert config.domain == "minimal-domain"
        assert config.api_token == "minimal-token"
        assert config.default_pipeline_id == "1"  # Should use default
        assert config.default_stage_id == "1"  # Should use default

    def test_from_env_missing_domain(self, monkeypatch):
        """Test config from env with missing domain"""
        monkeypatch.delenv("PIPEDRIVE_COMPANY_DOMAIN", raising=False)
        monkeypatch.setenv("PIPEDRIVE_API_TOKEN", "token")

        with pytest.raises(
            PipedriveConfigError,
            match="Missing required environment variables.*PIPEDRIVE_COMPANY_DOMAIN",
        ):
            PipedriveConfig.from_env()

    def test_from_env_missing_token(self, monkeypatch):
        """Test config from env with missing token"""
        monkeypatch.setenv("PIPEDRIVE_COMPANY_DOMAIN", "domain")
        monkeypatch.delenv("PIPEDRIVE_API_TOKEN", raising=False)

        with pytest.raises(
            PipedriveConfigError,
            match="Missing required environment variables.*PIPEDRIVE_API_TOKEN",
        ):
            PipedriveConfig.from_env()

    def test_from_env_missing_both(self, monkeypatch):
        """Test config from env with both required vars missing"""
        monkeypatch.delenv("PIPEDRIVE_COMPANY_DOMAIN", raising=False)
        monkeypatch.delenv("PIPEDRIVE_API_TOKEN", raising=False)

        with pytest.raises(PipedriveConfigError) as exc_info:
            PipedriveConfig.from_env()

        error_message = str(exc_info.value)
        assert "PIPEDRIVE_COMPANY_DOMAIN" in error_message
        assert "PIPEDRIVE_API_TOKEN" in error_message

    @patch("mb_pipedrive_integration.dataclasses.PipedriveConfig._get_django_settings")
    def test_from_django_settings_success(self, mock_get_settings):
        """Test successful config creation from Django settings"""
        mock_get_settings.return_value = {
            "PIPEDRIVE_COMPANY_DOMAIN": "django-domain",
            "PIPEDRIVE_API_TOKEN": "django-token",
            "PIPEDRIVE_DEFAULT_PIPELINE_ID": "7",
            "PIPEDRIVE_DEFAULT_STAGE_ID": "14",
            "PIPEDRIVE_CUSTOM_FIELDS": {"test": "field"},
            "PIPEDRIVE_PRODUCT_MAPPINGS": {"product_1": {"id": 1, "name": "Test Product 1", "price": 100}},
        }

        config = PipedriveConfig.from_django_settings()

        assert config.domain == "django-domain"
        assert config.api_token == "django-token"
        assert config.default_pipeline_id == "7"
        assert config.default_stage_id == "14"
        assert config.custom_fields == {"test": "field"}

    @patch("mb_pipedrive_integration.dataclasses.PipedriveConfig._get_django_settings")
    def test_from_django_settings_no_django(self, mock_get_settings):
        """Test config from Django settings when Django is not available"""
        mock_get_settings.side_effect = ImportError("Django not available")

        with pytest.raises(PipedriveConfigError, match="Django is not available"):
            PipedriveConfig.from_django_settings()

    @patch("mb_pipedrive_integration.dataclasses.PipedriveConfig._get_django_settings")
    def test_from_django_settings_missing_required(self, mock_get_settings):
        """Test config from Django settings with missing required settings"""
        mock_get_settings.return_value = {
            "SOME_OTHER_SETTING": "value"
            # Missing required settings
        }

        with pytest.raises(PipedriveConfigError, match="Missing required Django settings"):
            PipedriveConfig.from_django_settings()


class TestProductData:
    """Test ProductData dataclass validation and functionality"""

    def test_valid_product_data(self):
        """Test creating valid product data"""
        product = ProductData(
            product_id=123,
            quantity=2,
            item_price=99.99,
            comments="Test product",
            tax=10.0,
            discount=5.0,
            discount_type="percentage"
        )

        assert product.product_id == 123
        assert product.quantity == 2
        assert product.item_price == 99.99
        assert product.comments == "Test product"
        assert product.tax == 10.0
        assert product.discount == 5.0
        assert product.discount_type == "percentage"

    def test_minimal_product_data(self):
        """Test product with only required fields"""
        product = ProductData(product_id=456)

        assert product.product_id == 456
        assert product.quantity == 1  # Default
        assert product.item_price is None  # Default
        assert product.comments is None  # Default
        assert product.tax == 0  # Default
        assert product.discount == 0  # Default
        assert product.discount_type == "percentage"  # Default

    def test_product_data_with_amount_discount(self):
        """Test product with amount-based discount"""
        product = ProductData(
            product_id=789,
            discount=50.0,
            discount_type="amount"
        )

        assert product.discount == 50.0
        assert product.discount_type == "amount"

    def test_zero_product_id_raises_error(self):
        """Test that zero product ID raises validation error"""
        with pytest.raises(ValueError, match="Product ID must be positive"):
            ProductData(product_id=0)

    def test_negative_product_id_raises_error(self):
        """Test that negative product ID raises validation error"""
        with pytest.raises(ValueError, match="Product ID must be positive"):
            ProductData(product_id=-1)

    def test_negative_quantity_raises_error(self):
        """Test that negative quantity raises validation error"""
        with pytest.raises(ValueError, match="Quantity must be positive"):
            ProductData(product_id=123, quantity=-1)

    def test_zero_quantity_raises_error(self):
        """Test that zero quantity raises validation error"""
        with pytest.raises(ValueError, match="Quantity must be positive"):
            ProductData(product_id=123, quantity=0)

    def test_negative_item_price_raises_error(self):
        """Test that negative item price raises validation error"""
        with pytest.raises(ValueError, match="Item price cannot be negative"):
            ProductData(product_id=123, item_price=-10.0)

    def test_invalid_discount_type_raises_error(self):
        """Test that invalid discount type raises validation error"""
        with pytest.raises(ValueError, match="Discount type must be 'percentage' or 'amount'"):
            ProductData(product_id=123, discount_type="invalid")
