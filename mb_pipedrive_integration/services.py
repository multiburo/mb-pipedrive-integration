import logging
import time
from typing import Optional, Dict, Any, List, Union
from urllib.parse import urlencode

import requests

from . import OrganizationData
from .dataclasses import PipedriveConfig, DealData, ProductData, PersonData
from .exceptions import PipedriveAPIError, PipedriveNetworkError, PipedriveConfigError

logger = logging.getLogger(__name__)


class PipedriveService:
    """Service class to handle all Pipedrive integrations using direct API calls"""

    def __init__(self, config: Optional[PipedriveConfig] = None):
        if config:
            self.config = config
        else:
            # Try Django settings first, fallback to env
            try:
                self.config = PipedriveConfig.from_django_settings()
            except (PipedriveConfigError, RuntimeError):
                self.config = PipedriveConfig.from_env()

        self.base_url = self.config.base_url

    def _make_request(
            self,
            method: str,
            endpoint: str,
            data: Optional[dict[str, Any]] = None,
            max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """Make a request to Pipedrive API with retry logic and proper error handling"""
        url = f"{self.base_url}/{endpoint}"
        params = {"api_token": self.config.api_token}

        for attempt in range(max_retries):
            try:
                if method == "GET":
                    response = requests.get(url, params=params, timeout=30)
                elif method == "POST":
                    response = requests.post(url, params=params, json=data, timeout=30)
                elif method == "PUT":
                    response = requests.put(url, params=params, json=data, timeout=30)
                elif method == "DELETE":
                    response = requests.delete(url, params=params, timeout=30)
                else:
                    raise PipedriveAPIError(f"Unsupported HTTP method: {method}")

                # Handle successful responses (200-299 range)
                if 200 <= response.status_code < 300:
                    result = response.json()
                    if result.get("success"):
                        return result
                    else:
                        logger.warning(f"Pipedrive API returned success=false: {result}")
                        return None

                # Handle rate limiting
                elif response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise PipedriveAPIError(
                            "Rate limit exceeded after all retries",
                            status_code=429,
                            response_data=response.json() if response.content else None
                        )

                # Handle client errors (4xx) and server errors (5xx)
                elif response.status_code >= 400:
                    error_data = None
                    try:
                        error_data = response.json()
                    except (ValueError, requests.exceptions.JSONDecodeError):
                        # Response doesn't contain valid JSON, use text instead
                        error_data = {"error": response.text[:200] if response.text else "Unknown error"}

                    raise PipedriveAPIError(
                        f"HTTP {response.status_code}: {response.reason}",
                        status_code=response.status_code,
                        response_data=error_data
                    )

                # Handle unexpected success codes (3xx redirects, etc.)
                else:
                    logger.warning(f"Unexpected response status {response.status_code}: {response.reason}")
                    return None

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Request timeout, retrying in {wait_time}s (attempt {attempt + 1})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise PipedriveNetworkError(
                        "Request timeout after all retries",
                        retry_count=max_retries
                    )

            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Connection error, retrying in {wait_time}s (attempt {attempt + 1})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise PipedriveNetworkError(
                        "Connection error after all retries",
                        original_error=e,
                        retry_count=max_retries
                    )

            except requests.exceptions.RequestException as e:
                logger.error(f"Unexpected request error: {e}")
                raise PipedriveNetworkError(
                    f"Network error: {e}",
                    original_error=e,
                    retry_count=attempt + 1
                )

        return None

    def create_person(
            self,
            name: str,
            email: Optional[str] = None,
            phone: Optional[str] = None,
            tags: Optional[Union[str, List[str]]] = None,
            custom_fields: Optional[Dict[str, any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a person in Pipedrive with optional tags and custom fields"""
        try:
            person_data = {
                "name": name,
            }

            if email:
                person_data["email"] = email
            if phone:
                person_data["phone"] = phone

            # Add tags if provided
            if tags:
                person_data["label"] = ",".join(tags)

            if custom_fields and self.config.custom_fields:
                for field_key, field_value in custom_fields.items():
                    pipedrive_field_key = self.config.custom_fields.get(f"person_{field_key}")
                    if pipedrive_field_key:
                        person_data[pipedrive_field_key] = field_value

            response = self._make_request("POST", "persons", person_data)

            if response and response.get("success"):
                person = response["data"]
                logger.info(f"Person created in Pipedrive: {name} (ID: {person['id']})")
                return person
            else:
                logger.error(f"Failed to create person in Pipedrive: {response}")
                return None

        except (PipedriveAPIError, PipedriveNetworkError) as e:
            logger.error(f"Error creating person in Pipedrive: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating person in Pipedrive: {str(e)}")
            return None

    @staticmethod
    def _normalize_email(email: Optional[str]) -> str:
        return (email or "").strip().lower()

    @staticmethod
    def _phone_key(phone: Optional[str]) -> str:
        """Comparable form of a phone: digits only, last 10 (drops +52 / the mobile 1). Empty if too short to trust."""
        digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
        return digits[-10:] if len(digits) >= 10 else ""

    @staticmethod
    def _contact_values(entries: Any) -> List[str]:
        """Values of an emails/phones field; search returns plain strings or {'value': ...} depending on the endpoint."""
        values = []
        for entry in entries or []:
            value = entry.get("value") if isinstance(entry, dict) else entry
            if value:
                values.append(str(value))
        return values

    def _search_persons(self, term: str, field: str, exact_match: bool) -> List[Dict[str, Any]]:
        query = urlencode(
            {"term": term, "fields": field, "exact_match": "true" if exact_match else "false", "limit": 20}
        )
        response = self._make_request("GET", f"persons/search?{query}")
        if response is None:
            # _make_request returns None for a 2xx with success=false or a 3xx; that is not "nobody matches"
            raise PipedriveAPIError("Person search returned no usable response")
        items = (response.get("data") or {}).get("items") or []
        return [entry["item"] for entry in items if entry.get("item")]

    def _search_person_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Person whose email list contains exactly this email. Raises on API/network errors."""
        wanted = self._normalize_email(email)
        if not wanted:
            return None
        for person in self._search_persons(wanted, "email", exact_match=True):
            if wanted in {self._normalize_email(v) for v in self._contact_values(person.get("emails"))}:
                return person
        return None

    def _search_person_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """The only person holding this normalized phone, or None if there is none or it is shared."""
        wanted = self._phone_key(phone)
        if not wanted:
            return None
        # Stored phones come in mixed formats, so search loosely and compare normalized values ourselves
        matches = {}
        for person in self._search_persons(wanted, "phone", exact_match=False):
            if wanted in {self._phone_key(v) for v in self._contact_values(person.get("phones"))}:
                matches[person["id"]] = person
        if len(matches) > 1:
            logger.warning(f"Phone {wanted} is shared by persons {sorted(matches)}; not matching by phone")
            return None
        return next(iter(matches.values()), None)

    def find_person_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Find a person by exact (case-insensitive) email in Pipedrive"""
        try:
            return self._search_person_by_email(email)
        except (PipedriveAPIError, PipedriveNetworkError) as e:
            logger.error(f"Error finding person by email in Pipedrive: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error finding person by email in Pipedrive: {e}")
            return None

    def _merge_person_contact(
            self,
            person: Dict[str, Any],
            email: Optional[str],
            phone: Optional[str],
            custom_fields: Optional[Dict[str, any]],
    ) -> Dict[str, Any]:
        """
        Add the email/phone to an existing person's lists (never replacing them) and set custom fields.
        The name and tags are left untouched. Returns the person as it stands afterwards.
        """
        person_id = person["id"]
        try:
            current = (self._make_request("GET", f"persons/{person_id}") or {}).get("data")
        except (PipedriveAPIError, PipedriveNetworkError) as e:
            logger.warning(f"Could not load person {person_id} to merge contact data, leaving it as is: {e}")
            return person
        if not current:
            return person

        update_data: Dict[str, Any] = {}
        for field, new_value, key in (
                ("email", email, self._normalize_email),
                ("phone", phone, lambda v: self._phone_key(v) or str(v).strip()),
        ):
            entries = [e for e in (current.get(field) or []) if isinstance(e, dict) and e.get("value")]
            if new_value and key(new_value) not in {key(e["value"]) for e in entries}:
                entries.append({"value": new_value, "primary": not entries, "label": "work"})
                update_data[field] = entries

        if custom_fields and self.config.custom_fields:
            for field_key, field_value in custom_fields.items():
                pipedrive_field_key = self.config.custom_fields.get(f"person_{field_key}")
                if pipedrive_field_key:
                    update_data[pipedrive_field_key] = field_value

        if not update_data:
            return current

        try:
            response = self._make_request("PUT", f"persons/{person_id}", update_data)
        except (PipedriveAPIError, PipedriveNetworkError) as e:
            logger.error(f"Failed to merge contact data into person {person_id} in Pipedrive: {e}")
            return current
        if response and response.get("success"):
            return response.get("data") or current
        logger.error(f"Failed to merge contact data into person {person_id} in Pipedrive: {response}")
        return current

    def get_or_create_person(
            self,
            name: str,
            email: Optional[str] = None,
            phone: Optional[str] = None,
            tags: Optional[Union[str, List[str]]] = None,
            custom_fields: Optional[Dict[str, any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get existing person or create new one with optional tags and custom fields.

        A person matches only on an exact email or, when no email is given, on a phone that exactly
        matches after normalization and belongs to a single person. Without a match a new person is
        created; an existing one is never renamed, and its emails/phones are appended to, not replaced.
        If the lookup itself fails, returns None rather than risk creating a duplicate.
        """
        try:
            if email:
                person = self._search_person_by_email(email)
            elif phone:
                person = self._search_person_by_phone(phone)
            else:
                person = None
        except (PipedriveAPIError, PipedriveNetworkError) as e:
            logger.error(f"Error looking up person '{name}' in Pipedrive, not creating a duplicate: {e}")
            return None

        if person:
            return self._merge_person_contact(person, email, phone, custom_fields)

        return self.create_person(name, email, phone, tags, custom_fields)

    def create_organization(self, org_data: OrganizationData) -> Optional[Dict[str, Any]]:
        """Create an organization in Pipedrive"""
        try:
            organization_data = {"name": org_data.name}

            # Add custom fields if provided
            if org_data.custom_fields and self.config.custom_fields:
                for field_key, field_value in org_data.custom_fields.items():
                    # Map field key to Pipedrive custom field hash
                    pipedrive_field_key = self.config.custom_fields.get(f"org_{field_key}")
                    if pipedrive_field_key:
                        organization_data[pipedrive_field_key] = field_value

            response = self._make_request("POST", "organizations", organization_data)

            if response and "data" in response:
                organization = response["data"]
                logger.info(f"Organization created in Pipedrive: {org_data.name} (ID: {organization['id']})")
                return organization
            else:
                logger.error(f"Failed to create organization in Pipedrive: {response}")
                return None

        except Exception as e:
            logger.error(f"Error creating organization in Pipedrive: {str(e)}")
            return None

    def find_organization_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find an organization by name in Pipedrive"""
        try:
            response = self._make_request("GET", f"organizations/search?term={name}")
            if response and response.get("data", {}).get("items"):
                # Pipedrive search returns items wrapped in 'item' objects
                return response["data"]["items"][0]["item"]
            return None
        except Exception as e:
            logger.error(f"Error finding organization by name in Pipedrive: {e}")
            return None

    def find_organization_by_custom_field(self, field_key: str, field_value: str) -> Optional[Dict[str, Any]]:
        """
        Find an organization by any custom field value.

        Args:
            field_key: The custom field key (e.g., 'mb_id', 'external_id', 'uuid')
            field_value: The value to search for

        Returns:
            Organization dict if found, None otherwise
        """
        try:
            if not self.config.custom_fields:
                logger.warning("No custom fields configured")
                return None

            # Map the field key to Pipedrive's custom field hash
            pipedrive_field_key = self.config.custom_fields.get(f"org_{field_key}")
            if not pipedrive_field_key:
                logger.warning(f"No mapping found for custom field 'org_{field_key}'")
                return None

            # Use pagination for better performance
            start = 0
            limit = 100  # Pipedrive's recommended limit

            while True:
                response = self._make_request("GET", f"organizations?start={start}&limit={limit}")
                if not response or "data" not in response:
                    break

                organizations = response["data"]
                if not organizations:  # No more data
                    break

                # Search through this batch
                for org in organizations:
                    if org.get(pipedrive_field_key) == field_value:
                        logger.info(
                            f"Found organization by {field_key}={field_value}: {org.get('name')} (ID: {org.get('id')})")
                        return org

                # Check if there are more pages
                additional_data = response.get("additional_data", {})
                pagination = additional_data.get("pagination", {})
                if not pagination.get("more_items_in_collection", False):
                    break

                start += limit

            logger.info(f"No organization found with {field_key}={field_value}")
            return None

        except Exception as e:
            logger.error(f"Error finding organization by {field_key}={field_value}: {e}")
            return None

    def find_organization_by_mb_id(self, mb_id: str) -> Optional[Dict[str, Any]]:
        """Find organization by Multiburo ID"""
        return self.find_organization_by_custom_field("mb_id", mb_id)

    def get_or_create_organization(self, org_data: OrganizationData) -> Optional[Dict[str, Any]]:
        """Get existing organization or create new one"""

        if org_data.custom_fields and "mb_id" in org_data.custom_fields:
            mb_id = org_data.custom_fields["mb_id"]
            existing_org = self.find_organization_by_mb_id(mb_id)
            if existing_org:
                return existing_org

        return self.create_organization(org_data)

    def create_deal(self, deal_data: DealData) -> Optional[Dict[str, Any]]:
        """Create a deal in Pipedrive based on deal data"""
        try:
            # Create or get persons with appropriate tags
            tenant_person = self._person_for_deal("tenant", deal_data.tenant)
            advisor_person = self._person_for_deal("advisor", deal_data.advisor)
            landlord_person = self._person_for_deal("landlord", deal_data.landlord)
            guarantor_person = self._person_for_deal("guarantor", deal_data.guarantor)

            # Create or get organization
            organization = None
            if deal_data.organization:
                organization = self.get_or_create_organization(deal_data.organization)

            if advisor_person and organization:
                self.link_person_to_organization(advisor_person["id"], organization["id"])

            # Prepare deal data
            pipedrive_deal_data = {
                "title": deal_data.title,
                "pipeline_id": int(deal_data.pipeline_id or self.config.default_pipeline_id),
                "stage_id": int(deal_data.stage_id or self.config.default_stage_id),
                "status": "open",
            }

            # Add person and organization if available
            if advisor_person:
                pipedrive_deal_data["person_id"] = advisor_person["id"]

            if organization:
                pipedrive_deal_data["org_id"] = organization["id"]

            # Add custom fields if configured
            custom_fields = self.config.custom_fields or {}

            if custom_fields.get("folder_number"):
                pipedrive_deal_data[custom_fields["folder_number"]] = deal_data.folder_number

            if custom_fields.get("folder_id"):
                pipedrive_deal_data[custom_fields["folder_id"]] = deal_data.folder_id

            if custom_fields.get("property_owner_person") and landlord_person:
                pipedrive_deal_data[custom_fields["property_owner_person"]] = landlord_person["id"]

            if custom_fields.get("tenant_person") and tenant_person:
                pipedrive_deal_data[custom_fields["tenant_person"]] = tenant_person["id"]

            if custom_fields.get("guarantor_person") and guarantor_person:
                pipedrive_deal_data[custom_fields["guarantor_person"]] = guarantor_person["id"]

            if custom_fields.get("multiexpediente_url") and deal_data.multiexpediente_url:
                pipedrive_deal_data[custom_fields["multiexpediente_url"]] = deal_data.multiexpediente_url

            # Create the deal
            response = self._make_request("POST", "deals", pipedrive_deal_data)

            if response and response.get("success"):
                created_deal = response["data"]
                logger.info(f"Deal created in Pipedrive: {deal_data.title} (ID: {created_deal['id']})")

                # Add notes with additional information
                self._add_deal_notes(created_deal["id"], deal_data)

                return created_deal
            else:
                logger.error(f"Failed to create deal in Pipedrive: {response}")
                return None

        except (PipedriveAPIError, PipedriveNetworkError) as e:
            logger.error(f"Error creating deal in Pipedrive: {str(e)}")
            return None

    def _person_for_deal(self, role: str, contact: Optional[PersonData]) -> Optional[Dict[str, Any]]:
        """Resolve a deal participant; raises when it cannot, so a deal is never created missing one."""
        if not contact:
            return None
        person = self.get_or_create_person(
            name=contact.name,
            email=contact.email,
            phone=contact.phone,
            tags=contact.tags,
            custom_fields=contact.custom_fields,
        )
        if not person:
            raise PipedriveAPIError(f"Could not find or create the {role} in Pipedrive; deal not created")
        return person

    def _add_deal_notes(self, deal_id: int, deal_data: DealData) -> bool:
        """Add notes to the deal with additional information"""
        try:
            notes_content = f"""
            Información del Expediente:
            - Folder Number: {deal_data.folder_number}
            - Folder ID: {deal_data.folder_id}
            """

            if deal_data.tenant:
                notes_content += f"\n- Tenant: {deal_data.tenant.name}"
                if deal_data.tenant.email:
                    notes_content += f" ({deal_data.tenant.email})"

            if deal_data.property_address:
                notes_content += f"\n- Property Address: {deal_data.property_address}"

            if deal_data.multiexpediente_url:
                notes_content += f"\n- Multiexpediente URL: {deal_data.multiexpediente_url}"

            note_data = {"content": notes_content.strip(), "deal_id": deal_id}
            response = self._make_request("POST", "notes", note_data)

            return response and response.get("success", False)

        except Exception as e:
            logger.error(f"Error adding notes to deal {deal_id}: {str(e)}")
            return False

    def update_deal_stage(self, deal_id: int, stage_id: str) -> bool:
        """Update deal stage in Pipedrive"""
        try:
            update_data = {"stage_id": int(stage_id)}
            response = self._make_request("PUT", f"deals/{deal_id}", update_data)

            if response and response.get("success"):
                logger.info(f"Deal {deal_id} stage updated to {stage_id}")
                return True
            else:
                logger.error(f"Failed to update deal {deal_id} stage: {response}")
                return False

        except Exception as e:
            logger.error(f"Error updating deal {deal_id} stage: {str(e)}")
            return False

    def close_deal(self, deal_id: int, status: str = "won") -> bool:
        """Close a deal in Pipedrive"""
        try:
            if status not in ["won", "lost"]:
                raise PipedriveAPIError(f"Invalid deal status: {status}. Must be 'won' or 'lost'")

            update_data = {"status": status}
            response = self._make_request("PUT", f"deals/{deal_id}", update_data)

            if response and response.get("success"):
                logger.info(f"Deal {deal_id} closed as {status}")
                return True
            else:
                logger.error(f"Failed to close deal {deal_id}: {response}")
                return False

        except Exception as e:
            logger.error(f"Error closing deal {deal_id}: {str(e)}")
            return False

    def find_deal_by_folder_number(self, folder_number: int) -> Optional[Dict[str, Any]]:
        """Find a deal by folder number using custom field"""
        try:
            # This would require iterating through deals and checking custom fields
            # Implementation depends on your custom field configuration
            response = self._make_request("GET", "deals")

            if response and response.get("data"):
                custom_field_key = self.config.custom_fields.get("folder_number") if self.config.custom_fields else None

                if custom_field_key:
                    for deal in response["data"]:
                        if deal.get(custom_field_key) == folder_number:
                            return deal

            return None

        except Exception as e:
            logger.error(f"Error finding deal by folder number {folder_number}: {str(e)}")
            return None

    def add_deal_tags(self, deal_id: int, tags: List[str]) -> bool:
        """Add tags to a deal in Pipedrive"""
        try:
            if not tags:
                logger.info(f"No tags provided for deal {deal_id}")
                return True

            logger.info(f"Adding {len(tags)} tags to deal {deal_id}: {tags}")

            # First, get the current deal to see existing tags
            current_deal_response = self._make_request("GET", f"deals/{deal_id}")
            if not current_deal_response or not current_deal_response.get("success"):
                logger.error(f"❌ Failed to get current deal {deal_id} for tag update")
                return False

            current_deal = current_deal_response["data"]
            existing_labels = current_deal.get("label", [])

            # Convert existing labels to list if it's a string
            if isinstance(existing_labels, str):
                existing_labels = [label.strip() for label in existing_labels.split(",") if label.strip()]
            elif existing_labels is None:
                existing_labels = []

            # Combine existing and new tags, removing duplicates
            all_tags = list(set(existing_labels + tags))

            # Update the deal with combined tags
            update_data = {
                "label": ",".join(all_tags)
            }

            response = self._make_request("PUT", f"deals/{deal_id}", update_data)
            if response and response.get("success"):
                logger.info(f"✅ Successfully added tags to deal {deal_id}")
                return True
            else:
                logger.error(f"❌ Failed to add tags to deal {deal_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Error adding tags to deal {deal_id}: {e}")
            return False

    def link_person_to_organization(self, person_id: int, organization_id: int) -> bool:
        """Link a person to an organization in Pipedrive."""
        try:
            update_data = {"org_id": organization_id}
            response = self._make_request("PUT", f"persons/{person_id}", update_data)

            if response and "data" in response:
                logger.info(f"✅ Linked person {person_id} to organization {organization_id}")
                return True

            logger.error(f"❌ Failed to link person {person_id} to organization {organization_id}")
            return False

        except Exception as e:
            logger.error(f"❌ Error linking person to organization: {e}")
            return False

    def attach_product_to_deal(
            self,
            deal_id: int,
            product_id: int,
            quantity: int = 1,
            item_price: Optional[float] = None,
            comments: Optional[str] = None,
            tax: float = 0,
            discount: float = 0,
            discount_type: str = "percentage"
    ) -> bool:
        """
        Attach a product to a deal
        If item_price is None, will fetch the product's default price
        """
        try:
            # If no price provided, get product's default price
            if item_price is None:
                item_price = self._get_product_default_price(product_id)
                if item_price is None:
                    logger.error(f"Could not determine price for product {product_id}")
                    return False

            product_data = {
                "product_id": product_id,
                "item_price": item_price,
                "quantity": quantity,
                "tax": tax,
                "discount": discount,
                "discount_type": discount_type
            }

            if comments:
                product_data["comments"] = comments

            response = self._make_request("POST", f"deals/{deal_id}/products", product_data)

            if response and "data" in response:
                logger.info(f"✅ Attached product {product_id} to deal {deal_id} at price {item_price}")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ Error attaching product {product_id} to deal {deal_id}: {e}")
            return False

    def attach_multiple_products_to_deal(
            self,
            deal_id: int,
            products: List[ProductData]
    ) -> Dict[str, Any]:
        """
        Attach multiple products to a deal
        Returns summary of success/failure for each product
        """
        results = {
            "successful": [],
            "failed": [],
            "total_attempted": len(products),
            "success_count": 0,
            "failure_count": 0
        }

        for product_attachment in products:
            success = self.attach_product_to_deal(
                deal_id=deal_id,
                product_id=product_attachment.product_id,
                quantity=product_attachment.quantity,
                item_price=product_attachment.item_price,
                comments=product_attachment.comments,
                tax=product_attachment.tax,
                discount=product_attachment.discount,
                discount_type=product_attachment.discount_type
            )

            if success:
                results["successful"].append(product_attachment.product_id)
                results["success_count"] += 1
            else:
                results["failed"].append(product_attachment.product_id)
                results["failure_count"] += 1

        logger.info(
            f"📊 Batch attachment to deal {deal_id}: {results['success_count']}/{results['total_attempted']} successful")
        return results

    def _get_product_default_price(self, product_id: int) -> Optional[float]:
        """Get the default price for a product"""
        try:
            response = self._make_request("GET", f"products/{product_id}")
            if response and "data" in response:
                product_data = response["data"]
                prices = product_data.get("prices", [])
                if prices and len(prices) > 0:
                    return float(prices[0].get("price", 0))
            return None
        except Exception as e:
            logger.error(f"Error fetching product {product_id} default price: {e}")
            return None

    def update_person(self, person_id: int, person_data: PersonData) -> Optional[Dict[str, Any]]:
        """
        Update an existing person in Pipedrive

        Args:
            person_id: The Pipedrive person ID to update
            person_data: PersonData containing the updated information

        Returns:
            Updated person data from Pipedrive API, or None if failed
        """
        try:
            # Prepare update data
            update_data = {
                "name": person_data.name
            }

            if person_data.email:
                update_data["email"] = person_data.email

            if person_data.phone:
                update_data["phone"] = person_data.phone

            if person_data.tags:
                # Convert tags to comma-separated string
                if isinstance(person_data.tags, list):
                    update_data["label"] = ",".join(person_data.tags)
                else:
                    update_data["label"] = person_data.tags

            # Add custom fields if provided
            if person_data.custom_fields and self.config.custom_fields:
                for field_key, field_value in person_data.custom_fields.items():
                    pipedrive_field_key = self.config.custom_fields.get(f"person_{field_key}")
                    if pipedrive_field_key:
                        update_data[pipedrive_field_key] = field_value

            # Make the update request
            response = self._make_request("PUT", f"persons/{person_id}", update_data)

            if response and response.get("success"):
                logger.info(f"Successfully updated person {person_id} in Pipedrive")
                return response.get("data")
            else:
                logger.error(f"Failed to update person {person_id} in Pipedrive: {response}")
                return None

        except Exception as e:
            logger.error(f"Error updating person {person_id} in Pipedrive: {e}")
            return None

    def get_users(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get all Pipedrive users

        Returns:
            List of user dicts from Pipedrive API, or None if failed
        """
        try:
            response = self._make_request("GET", "users")

            if response and response.get("success"):
                users = response.get("data", [])
                logger.info(f"Retrieved {len(users)} Pipedrive users")
                return users
            else:
                logger.error(f"Failed to get Pipedrive users: {response}")
                return None

        except Exception as e:
            logger.error(f"Error getting Pipedrive users: {str(e)}")
            return None

    def find_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Find a Pipedrive user by email address

        Args:
            email: The email address to search for

        Returns:
            User dict if found, None otherwise
        """
        try:
            if not email:
                return None

            users = self.get_users()
            if not users:
                return None

            # Search for user with matching email
            email_lower = email.lower().strip()
            for user in users:
                user_email = user.get("email", "").lower().strip()
                if user_email == email_lower:
                    logger.info(f"Found Pipedrive user: {user.get('name')} (ID: {user.get('id')}) for email {email}")
                    return user

            logger.warning(f"No Pipedrive user found with email: {email}")
            return None

        except Exception as e:
            logger.error(f"Error finding user by email {email}: {str(e)}")
            return None

    def create_activity(
            self,
            subject: str,
            activity_type: str,
            due_date: Optional[str] = None,
            due_time: Optional[str] = None,
            duration: Optional[str] = None,
            deal_id: Optional[int] = None,
            person_id: Optional[int] = None,
            user_id: Optional[int] = None,
            note: Optional[str] = None,
            **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Create an activity (task, call, meeting, etc.) in Pipedrive

        Args:
            subject: The subject/title of the activity
            activity_type: The type of activity (e.g., 'task', 'call', 'meeting')
            due_date: Due date in YYYY-MM-DD format
            due_time: Due time in HH:MM format
            duration: Duration in HH:MM format
            deal_id: ID of the deal this activity is related to
            person_id: ID of the person this activity is related to
            user_id: ID of the Pipedrive user this activity is assigned to
            note: Additional notes for the activity
            **kwargs: Additional fields to include in the activity

        Returns:
            Created activity data from Pipedrive API, or None if failed
        """
        try:
            activity_data = {
                "subject": subject,
                "type": activity_type,
            }

            if due_date:
                activity_data["due_date"] = due_date

            if due_time:
                activity_data["due_time"] = due_time

            if duration:
                activity_data["duration"] = duration

            if deal_id:
                activity_data["deal_id"] = deal_id

            if person_id:
                activity_data["person_id"] = person_id

            if user_id:
                activity_data["user_id"] = user_id

            if note:
                activity_data["note"] = note

            # Add any additional fields from kwargs
            activity_data.update(kwargs)

            response = self._make_request("POST", "activities", activity_data)

            if response and response.get("success"):
                activity = response["data"]
                logger.info(f"Activity created in Pipedrive: {subject} (ID: {activity['id']})")
                return activity
            else:
                logger.error(f"Failed to create activity in Pipedrive: {response}")
                return None

        except Exception as e:
            logger.error(f"Error creating activity in Pipedrive: {str(e)}")
            return None
