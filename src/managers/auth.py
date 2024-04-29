#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Supporting objects for Karapace user and ACL management."""

import json
import logging
from dataclasses import dataclass
from typing import Literal, TypedDict

from core.cluster import ClusterContext
from core.workload import WorkloadBase
from literals import ADMIN_USER

logger = logging.getLogger(__name__)

Algorithm = Literal["sha512"]
ResourceType = Literal["Subject", "Config"]  # Represents types of resources on Karapace.
Operation = Literal["Read", "Write"]
Role = Literal["admin", "user"]


@dataclass()
class Acl:
    """Convenience object for representing a Karapace ACL."""

    username: str
    operation: Operation
    resource: str

    @property
    def acl_repr(self) -> dict[str, str]:
        """Returns the dict with an ACL representation."""
        return {
            "username": self.username,
            "operation": self.operation,
            "resource": self.resource,
        }


@dataclass
class UserCredentials:
    """Object for representing credentials of a Karapace user."""

    username: str
    algorithm: Algorithm
    salt: str
    password_hash: str

    @property
    def creds_repr(self) -> dict[str, str]:
        """Returns the dict with an credentials representation."""
        return {
            "username": self.username,
            "algorithm": self.algorithm,
            "salt": self.salt,
            "password_hash": self.password_hash,
        }


class AuthDictEntry(TypedDict):
    """Data entry for internal auth state on KarapaceAuth."""

    credentials: UserCredentials
    acls: list[Acl]


class KarapaceAuth:
    """Object for updating Karapace users and ACLs.

    The class will load authfile.json to create an internal mapping, after this, operations are
    only done internally. To persist changes, `write_authfile` has to be invoked e.g.:

    ```
        auth = KarapaceAuth(context, workload)
        auth.add_user(username, password)
        auth.add_acl()

        auth.write_authfile()
    ```
    """

    def __init__(self, context: ClusterContext, workload: WorkloadBase):
        self.context = context
        self.workload = workload

        # Load current users and ACLs to have an internal mapping of auth state.
        self._load_authfile()

    def _load_authfile(self) -> None:
        """Load current Karapace authfile."""
        # Internal state of auth to the class
        self.auth_dict: dict[str, AuthDictEntry] = {}

        raw_file = self.workload.read(self.workload.paths.registry_authfile)
        if not raw_file:
            return
        authfile = json.loads("\n".join(raw_file))

        users = [UserCredentials(**user) for user in authfile["users"]]
        acls = [Acl(**acl) for acl in authfile["permissions"]]

        for user in users:
            self.auth_dict[user.username] = AuthDictEntry(
                credentials=user,
                acls=[acl for acl in acls if acl.username == user.username],
            )

    def add_user(self, username: str, password: str, replace: bool = False) -> None:
        """Create a user for Karapace."""
        if username in self.auth_dict and not replace:
            logger.info(f"User {username} already exists, skipping creation")
            return

        user_creds = UserCredentials(
            **json.loads(self.workload.mkpasswd(username=username, password=password))
        )
        # If username doesn't exist we need to initialize the internal dictionary.
        # Maybe default dict is a more elegant solution here.
        if username not in self.auth_dict:
            self.auth_dict[username] = AuthDictEntry(credentials=user_creds, acls=[])
        else:
            self.auth_dict[username]["credentials"] = user_creds

    def add_acl(self, username: str, role: Role, subject: str | None = None) -> None:
        """Add Acls for a specific user.

        NOTE: At this point, ACLs are based on user roles. When needed, this can be extended
        to allow for custom acls.

        Args:
            username: user that the ACL will apply to
            role: role of the user
            subject: string with the subject resource the user is allowed to access
        """
        acls = []
        if role == "admin":
            acls.append(Acl(username=username, operation="Write", resource=".*"))
        elif role == "user":
            acls.append(Acl(username=username, operation="Read", resource="Config:"))
            acls.append(Acl(username=username, operation="Read", resource=f"Subject:{subject}.*"))

        self.auth_dict[username]["acls"] = acls

    def remove_user(self, username: str) -> None:
        """Remove username and ACLs."""
        del self.auth_dict[username]

    def write_authfile(self):
        """Add users or ACLs to authfile.json."""
        authfile_users = []
        authfile_permissions = []

        for user in self.auth_dict.values():
            authfile_users.append(user["credentials"].creds_repr)
            authfile_permissions += [acl.acl_repr for acl in user["acls"]]

        json_str = json.dumps(
            {"users": authfile_users, "permissions": authfile_permissions}, indent=2
        )
        self.workload.write(content=json_str, path=self.workload.paths.registry_authfile)

    def create_internal_user(self) -> None:
        """Create internal operator user."""
        admin_password = self.workload.generate_password()
        self.add_user(username=ADMIN_USER, password=admin_password, replace=True)
        self.add_acl(username=ADMIN_USER, subject=".*", role="admin")
        self.write_authfile()

        self.context.cluster.update({f"{ADMIN_USER}-password": admin_password})
