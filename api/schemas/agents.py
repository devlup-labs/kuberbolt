from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class ServiceInfo(BaseModel):
    service_name: str
    service_description: str | None = None
    category: str
    price_sats: int = Field(gt=0)
    price_unit: Literal["per_request", "per_minute", "flat"]


class LightningCredentials(BaseModel):
    node_pubkey: str
    lnurl: str | None = None
    lightning_address: str | None = None

    @model_validator(mode="after")
    def validate_lightning(self) -> "LightningCredentials":
        if not self.lnurl and not self.lightning_address:
            raise ValueError("At least one of lnurl or lightning_address must be provided.")
        return self


class RegisterAgentRequest(BaseModel):
    role: Literal["client", "merchant"]
    display_name: str
    about: str | None = None
    picture_url: str | None = None
    lightning: LightningCredentials
    service: ServiceInfo | None = None
    relays: list[str] | None = None

    @model_validator(mode="after")
    def validate_service_for_role(self) -> "RegisterAgentRequest":
        if self.role == "merchant" and self.service is None:
            raise ValueError("service is required for merchant role")
        if self.role == "client" and self.service is not None:
            raise ValueError("service must be None when role is client")
        return self


class RegisterAgentResponse(BaseModel):
    agent_pubkey: str
    agent_privkey: str  # hex-encoded Nostr secret key
    agent_nsec: str     # bech32-encoded Nostr secret key 
    role: str
    lightning: LightningCredentials | None = None
    service: ServiceInfo | None = None
    profile_event_id: str
    listing_event_id: str | None = None
    status: Literal["registered"] = "registered"
    registered_at: datetime


class UpdateField(BaseModel):
    field: Literal["display_name", "about", "picture_url", "lightning_address",
                   "service_name", "service_description", "price_sats", "price_unit"]
    value: str | int

class UpdateAgentRequest(BaseModel):
    agent_pubkey: str
    updates: list[UpdateField]
    relays: list[str] | None = None

class UpdateAgentResponse(BaseModel):
    agent_pubkey: str
    updated_fields: list[str]
    profile_event_id: str | None
    listing_event_id: str | None
    status: str
    updated_at: datetime
