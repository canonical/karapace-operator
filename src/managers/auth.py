#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Supporting objects for Karapace user and ACL management."""

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Literal

from core.cluster import ClusterContext
from core.workload import WorkloadBase
from literals import ADMIN_USER

logger = logging.getLogger(__name__)

Algorithm = Literal["sha512"]
ResourceType = Literal["Subject", "Config"]  # Represents types of resources on Karapace.
Operation = Literal["Read", "Write"]
Role = Literal["admin", "user"]


@dataclass
class Acl:
    """Convenience object for representing a Karapace ACL."""

    username: str
    operation: Operation
    resource: str


@dataclass
class UserCredentials:
    """Object for representing credentials of a Karapace user."""

    username: str
    algorithm: Algorithm
    salt: str
    password_hash: str


@dataclass
class AuthDictEntry:
    """Data entry for internal auth state on KarapaceAuth."""

    credentials: UserCredentials
    acls: list[Acl] = field(default_factory=list)


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
        """Load current Karapace authfile.

        Authfile has the following format:
        ```
        {
            "users": [
                {
                    "username": "example-user",
                    "algorithm": "scrypt",
                    "salt": "<salt for randomized hashing>",
                    "password_hash": "<hashed password>"
                },
            ],
            "permissions": [
                {
                    "username": "example-user",
                    "operation": "Write",
                    "resource": ".*"
                },
            ]
        }
        ```
        """
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

        # Maybe defaultdict is a more elegant solution here.
        new_entry = {username: AuthDictEntry(credentials=user_creds)}
        self.auth_dict = self.auth_dict | new_entry

    def add_acl(self, username: str, role: Role, subject: str | None = None) -> None:
        """Add Acls for a specific user.

        NOTE: At this point, ACLs are based on user roles. When needed, this can be extended
        to allow for custom acls.

        Args:
            username: user that the ACL will apply to
            role: role of the user
            subject: string with the subject resource the user is allowed to access
        """
        if username not in self.auth_dict:
            logger.warning(f"User {username} does not exist. Skipping ACL creation")
            return

        acls = []
        if role == "admin":
            acls.append(Acl(username=username, operation="Write", resource=".*"))
        elif role == "user":
            acls.append(Acl(username=username, operation="Read", resource="Config:"))
            acls.append(Acl(username=username, operation="Read", resource=f"Subject:{subject}.*"))

        self.auth_dict[username].acls = acls

    def remove_user(self, username: str) -> None:
        """Remove username and ACLs."""
        self.auth_dict.pop(username, None)

    def write_authfile(self):
        """Add users or ACLs to authfile.json.

        NOTE: for changes to be applied to Karapace, service needs to be restared.
        """
        authfile_users = []
        authfile_permissions = []

        for user in self.auth_dict.values():
            authfile_users.append(asdict(user.credentials))
            authfile_permissions += [asdict(acl) for acl in user.acls]

        json_str = json.dumps(
            {"users": authfile_users, "permissions": authfile_permissions}, indent=2
        )
        logger.debug(f"Writing new authfile:\n {json_str}\n")
        self.workload.write(content=json_str, path=self.workload.paths.registry_authfile)

    def create_internal_user(self) -> None:
        """Create internal operator user."""
        admin_password = self.workload.generate_password()
        self.add_user(username=ADMIN_USER, password=admin_password, replace=True)
        self.add_acl(username=ADMIN_USER, subject=".*", role="admin")
        self.write_authfile()

        self.context.cluster.update({f"{ADMIN_USER}-password": admin_password})

    def update_admin_user(self) -> None:
        """Updates credentials based on current charm information."""
        for user, password in self.context.cluster.internal_user_credentials.items():
            self.add_user(username=user, password=password, replace=True)
            self.add_acl(username=user, subject=".*", role="admin")

        self.write_authfile()
