"""Validated administrative configuration. Never accept SSH targets from clients."""
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SCOPES = {"read", "terminal:connect", "t3:pair"}
TARGET = re.compile(r"(?:[a-zA-Z0-9_][a-zA-Z0-9_.-]*@)?[a-zA-Z0-9_][a-zA-Z0-9_.:-]*\Z")
DNS = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9.-]*\Z")


class Host(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    address: str = Field(min_length=1, max_length=253)
    ssh_target: str
    source: str = "configured"
    port: int = Field(default=22, ge=1, le=65535)
    is_t3: bool = True
    enabled: bool = True
    magic_dns: str | None = None
    collector: Literal["ssh", "mounted_linux"] = "ssh"

    @field_validator("ssh_target")
    @classmethod
    def validate_target(cls, value):
        if not TARGET.fullmatch(value):
            raise ValueError("invalid configured SSH target")
        return value

    @field_validator("magic_dns")
    @classmethod
    def validate_dns(cls, value):
        if value is not None and not DNS.fullmatch(value):
            raise ValueError("invalid configured MagicDNS name")
        return value


class Config(BaseModel):
    state_dir: Path = Path("/var/lib/bleetd")
    gateway_name: str = "ZORAK"
    hosts: list[Host] = Field(default_factory=list)
    repositories: dict[str, str] = Field(default_factory=dict)
    known_hosts: str = "/etc/bleetd/known_hosts"
    identity_file: str | None = None
    ssh_config: str | None = None
    cache_seconds: float = Field(default=5, ge=0, le=300)
    collection_timeout: float = Field(default=15, ge=1, le=120)
    pairing_timeout: float = Field(default=90, ge=1, le=180)
    max_parallel_collectors: int = Field(default=4, ge=1, le=32)
    public_origin: str = "https://bleet.zorak.blusa.cloud"
    history_samples_per_host: int = Field(default=720, ge=1, le=10000)
    max_terminal_sessions: int = Field(default=8, ge=1, le=64)

    @model_validator(mode="after")
    def unique_hosts(self):
        if len({h.id for h in self.hosts}) != len(self.hosts):
            raise ValueError("duplicate host ID")
        if sum(host.collector == "mounted_linux" for host in self.hosts) > 1:
            raise ValueError("only one host can use the local host proc/sys mounts")
        return self

    @classmethod
    def load(cls, path):
        return cls.model_validate(json.loads(Path(path).read_text()))
