#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Supporting objects for Karapace user and ACL management."""

import json
import logging
from dataclasses import dataclass
from typing import Literal

from core.cluster import ClusterContext
from core.workload import WorkloadBase
from literals import ADMIN_USER, SNAP_NAME

logger = logging.getLogger(__name__)

Resource = Literal["Subject", "Config"]  # Represents types of resources on Karapace.
Operation = Literal["Write", "Read"]


@dataclass()
class Acl:
    """Convenience object for representing a Karapace ACL."""

    username: str
    operation: Operation
    resource_type: Resource
    resource_name: str

    @property
    def resource_str(self) -> str:
        """Returns the full resource string."""
        return f"{self.resource_type}:{self.resource_name}"

    @property
    def full_acl_repr(self) -> dict:
        """Returns the dict with an ACL representation."""
        return {
            "username": self.username,
            "operation": self.operation,
            "resource": self.resource_str,
        }


class KarapaceAuth:
    """Object for updating Karapace users and ACLs."""

    def __init__(self, context: ClusterContext, workload: WorkloadBase):
        self.context = context
        self.workload = workload

    @property
    def parsed_authfile(self) -> dict:
        """Return authfile parsed as a dict."""
        return json.loads("\n".join(self.workload.read(self.workload.paths.registry_authfile)))

    @property
    def users(self) -> list[str]:
        """Return existing users on karapace authfile."""
        full_users = self.parsed_authfile.get("users", [])
        return [user["username"] for user in full_users]

    @property
    def permissions(self) -> list[dict[str, str]] | None:
        """Return existing permissions on karapace authfile."""
        return self.parsed_authfile.get("permissions")

    def add_user(self, username: str, password: str, replace: bool = False) -> None:
        """Create a user for Karapace."""
        if username in self.users and not replace:
            return logger.info(f"User {username} already exists, skipping creation")

        user_credentials = json.loads(self.workload.mkpasswd(username=username, password=password))

        current_auth = self.parsed_authfile["users"]
        if replace:
            current_auth = [
                current_auth.remove(u) for u in current_auth if u["username"] == username
            ]
        current_auth.append(user_credentials)

        # self._write_authfile(values=new_auth)

    def add_acl(self, alcs: list[Acl]) -> None:
        """Add Acls for a specific user."""
        pass

    def remove_user(self, username: str) -> None:
        """Remove username and ACLs from authfile."""
        pass

    def _write_authfile(self, values: dict):
        """Add users or ACLs to authfile.json."""
        json_str = json.dumps(values, indent=2)
        self.workload.write(content=json_str, path=self.workload.paths.registry_authfile)

    def _create_internal_user(self) -> None:
        """Create internal operator user."""
        admin_password = self.workload.generate_password()
        user = json.loads(self.workload.mkpasswd(username=ADMIN_USER, password=admin_password))
        permissions = {
            "username": ADMIN_USER,
            "operation": "Write",
            "resource": ".*",
        }
        self._write_authfile(values={"users": [user], "permissions": [permissions]})

        self.context.cluster.update({f"{ADMIN_USER}-password": admin_password})
