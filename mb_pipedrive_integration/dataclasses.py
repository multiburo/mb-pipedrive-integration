import os
import re
from dataclasses import dataclass
from typing import Optional, Dict, Union, List

from .exceptions import PipedriveConfigError, PipedriveValidationError


@dataclass
class PersonData:
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    tags: Optional[Union[str, List[str]]] = None
    custom_fields: Optional[Dict[str, any]] = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise PipedriveValidationError("Person name cannot be empty")

        if self.email and not self._is_valid_email(self.email):
            raise PipedriveValidationError(f"Invalid email format: {self.email}")

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None


@dataclass
class OrganizationData:
    name: str
    custom_fields: Optional[Dict[str, any]] = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise PipedriveValidationError("Organization name cannot be empty")


@dataclass
class ProductData:
    """Data class for product attachment to deals"""
    product_id: int
    quantity: int = 1
    item_price: Optional[float] = None
    comments: Optional[str] = None
    tax: float = 0
    discount: float = 0
    discount_type: str = "percentage"

    def __post_init__(self) -> None:
        """Validate ProductData fields after initialization"""

        if not isinstance(self.product_id, int) or self.product_id <= 0:
            raise ValueError("Product ID must be positive")

        if not isinstance(self.quantity, int) or self.quantity <= 0:
            raise ValueError("Quantity must be positive")

        if self.item_price is not None and self.item_price < 0:
            raise ValueError("Item price cannot be negative")

        if self.discount_type not in ["percentage", "amount"]:
            raise ValueError("Discount type must be 'percentage' or 'amount'")

        if self.tax < 0:
            raise ValueError("Tax cannot be negative")

        if self.discount < 0:
            raise ValueError("Discount cannot be negative")


@dataclass
class DealData:
    title: str
    folder_number: int
    folder_id: str
    tenant: Optional[PersonData] = None
    advisor: Optional[PersonData] = None
    landlord: Optional[PersonData] = None
    organization: Optional[OrganizationData] = None
    property_address: Optional[str] = None
    multiexpediente_url: Optional[str] = None
    pipeline_id: Optional[int] = None
    stage_id: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise PipedriveValidationError("Deal title cannot be empty")

        if self.folder_number <= 0:
            raise PipedriveValidationError("folder_number must be positive")

        if not self.folder_id or not self.folder_id.strip():
            raise PipedriveValidationError("folder_id cannot be empty")


@dataclass
class PipedriveConfig:
    domain: str
    api_token: str
    default_pipeline_id: str = "1"
    default_stage_id: str = "1"
    custom_fields: Optional[Dict[str, str]] = None
    product_mappings: Optional[Dict[str, str]] = None

    def __post_init__(self) -> None:
        if not self.domain or not self.domain.strip():
            raise PipedriveConfigError("Pipedrive domain cannot be empty")

        if not self.api_token or not self.api_token.strip():
            raise PipedriveConfigError("Pipedrive API token cannot be empty")

    @property
    def base_url(self) -> str:
        """Get the base URL for Pipedrive API"""
        return f"https://{self.domain}.pipedrive.com/v1"

    @classmethod
    def _get_django_settings(cls) -> dict:
        """Helper method to get Django settings - makes testing easier"""
        try:
            from django.conf import settings
        except ImportError:
            raise ImportError("Django is not available")

        settings_dict = {}
        for attr_name in dir(settings):
            if attr_name.startswith('PIPEDRIVE_'):
                settings_dict[attr_name] = getattr(settings, attr_name)

        return settings_dict

    @classmethod
    def from_django_settings(cls) -> "PipedriveConfig":
        """Create config from Django settings"""
        try:
            settings_dict = cls._get_django_settings()
        except ImportError:
            raise PipedriveConfigError("Django is not available. Use from_env() instead.")

        # Validate required settings exist
        required_settings = ['PIPEDRIVE_COMPANY_DOMAIN', 'PIPEDRIVE_API_TOKEN', 'PIPEDRIVE_CUSTOM_FIELDS', 'PIPEDRIVE_PRODUCT_MAPPINGS']
        missing = [s for s in required_settings if s not in settings_dict]
        if missing:
            raise PipedriveConfigError(f"Missing required Django settings: {missing}")

        return cls(
            domain=settings_dict['PIPEDRIVE_COMPANY_DOMAIN'],
            api_token=settings_dict['PIPEDRIVE_API_TOKEN'],
            default_pipeline_id=settings_dict.get('PIPEDRIVE_DEFAULT_PIPELINE_ID', '1'),
            default_stage_id=settings_dict.get('PIPEDRIVE_DEFAULT_STAGE_ID', '1'),
            custom_fields=settings_dict.get('PIPEDRIVE_CUSTOM_FIELDS', None),
            product_mappings=settings_dict.get('PIPEDRIVE_PRODUCT_MAPPINGS', None)
        )

    @classmethod
    def from_env(cls) -> "PipedriveConfig":
        """Create config from environment variables"""
        domain = os.getenv("PIPEDRIVE_COMPANY_DOMAIN")
        api_token = os.getenv("PIPEDRIVE_API_TOKEN")

        if not domain or not api_token:
            missing = []
            if not domain:
                missing.append("PIPEDRIVE_COMPANY_DOMAIN")
            if not api_token:
                missing.append("PIPEDRIVE_API_TOKEN")
            raise PipedriveConfigError(f"Missing required environment variables: {missing}")

        return cls(
            domain=domain,
            api_token=api_token,
            default_pipeline_id=os.getenv("PIPEDRIVE_DEFAULT_PIPELINE_ID", "1"),
            default_stage_id=os.getenv("PIPEDRIVE_DEFAULT_STAGE_ID", "1"),
            custom_fields=None,
            product_mappings=None
        )
