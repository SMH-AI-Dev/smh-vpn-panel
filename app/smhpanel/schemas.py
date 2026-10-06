"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=256)


class InboundIn(BaseModel):
    protocol: Literal["vless", "vmess", "trojan", "shadowsocks", "wireguard"]
    port: int = Field(ge=1, le=65535)
    listen: str = "0.0.0.0"
    enabled: bool = True
    network: Literal["tcp", "ws", "grpc"] = "tcp"
    security: Literal["none", "tls", "reality"] = "none"
    flow: str = ""
    ws_path: str = ""
    grpc_service: str = ""
    sni_list: list[str] = Field(default_factory=list)
    dest: str = ""
    ss_method: str = ""
    tag: str = ""
    address_override: str = ""
    host_override: str = ""
    sni_override: str = ""
    fingerprint: str = "chrome"


class InboundUpdate(BaseModel):
    port: int | None = Field(default=None, ge=1, le=65535)
    listen: str | None = None
    enabled: bool | None = None
    tag: str | None = None
    network: Literal["tcp", "ws", "grpc"] | None = None
    security: Literal["none", "tls", "reality"] | None = None
    flow: str | None = None
    ws_path: str | None = None
    grpc_service: str | None = None
    sni_list: list[str] | None = None
    dest: str | None = None
    address_override: str | None = None
    host_override: str | None = None
    sni_override: str | None = None
    fingerprint: str | None = None


class EnableIn(BaseModel):
    enabled: bool


class ClientIn(BaseModel):
    inbound_id: int
    name: str = Field(min_length=1, max_length=64)
    quota_gb: float | None = Field(default=None, ge=0)
    expiry: str | None = None
    note: str = ""

    @field_validator("expiry")
    @classmethod
    def _parse_expiry(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        # Accept YYYY-MM-DD and validate early.
        datetime.strptime(value, "%Y-%m-%d")
        return value


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    quota_gb: float | None = Field(default=None, ge=0)
    expiry: str | None = None
    note: str | None = None

    @field_validator("expiry")
    @classmethod
    def _parse_expiry(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        datetime.strptime(value, "%Y-%m-%d")
        return value


class SettingsPatch(BaseModel):
    patch: dict


class CertRequest(BaseModel):
    domain: str = Field(min_length=3, max_length=253)
