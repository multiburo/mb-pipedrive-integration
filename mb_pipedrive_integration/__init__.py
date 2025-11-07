"""
Multiburo Pipedrive Integration Package

A Django-compatible library for integrating with Pipedrive CRM.
Provides clean abstractions for creating deals, managing persons,
and synchronizing data between Django applications and Pipedrive.
"""

from .dataclasses import PersonData, OrganizationData, DealData, ProductData, PipedriveConfig
from .services import PipedriveService
from .exceptions import (
    PipedriveError,
    PipedriveAPIError,
    PipedriveConfigError,
    PipedriveNetworkError,
    PipedriveValidationError,
)

__version__ = "1.2.2"
__author__ = "Multiburo"
__email__ = "gerardo.gornes@multiburo.com"

__all__ = [
    # Core classes
    "PipedriveService",
    "PipedriveConfig",
    # Data classes
    "PersonData",
    "OrganizationData",
    "DealData",
    "ProductData",
    # Exceptions
    "PipedriveError",
    "PipedriveAPIError",
    "PipedriveConfigError",
    "PipedriveNetworkError",
    "PipedriveValidationError",
]
