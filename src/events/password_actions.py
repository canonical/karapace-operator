#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Event handlers for password-related Juju Actions."""
import logging
from typing import TYPE_CHECKING

from ops.charm import ActionEvent
from ops.framework import Object

from literals import ADMIN_USER, INTERNAL_USERS

if TYPE_CHECKING:
    from charm import KarapaceCharm

logger = logging.getLogger(__name__)


class PasswordActionEvents(Object):
    """Event handlers for password-related Juju Actions."""

    def __init__(self, charm):
        super().__init__(charm, "password_events")
        self.charm: "KarapaceCharm" = charm

        self.framework.observe(
            getattr(self.charm.on, "set_password_action"), self._set_password_action
        )
        self.framework.observe(
            getattr(self.charm.on, "get_password_action"), self._get_password_action
        )

    def _set_password_action(self, event: ActionEvent) -> None:
        """Handler for set-password action.

        Set the password for a specific user, if no passwords are passed, generate them.
        """
        if not self.model.unit.is_leader():
            msg = "Password rotation must be called on leader unit"
            logger.error(msg)
            event.fail(msg)
            return

        if not self.charm.healthy:
            msg = "Unit is not healthy"
            logger.error(msg)
            event.fail(msg)
            return

        username = event.params["username"]
        if username not in INTERNAL_USERS:
            msg = f"Can only update internal charm users: {INTERNAL_USERS}, not {username}."
            logger.error(msg)
            event.fail(msg)
            return

        new_password = event.params.get("password", self.charm.workload.generate_password())

        if new_password in self.charm.context.cluster.internal_user_credentials.values():
            msg = "Password already exists, please choose a different password."
            logger.error(msg)
            event.fail(msg)
            return

        self.charm.auth_manager.add_user(username=username, password=new_password, replace=True)
        self.charm.auth_manager.add_acl(username=username, role="admin")
        self.charm.auth_manager.write_authfile()

        # Store the password on application databag
        self.charm.context.cluster.relation_data.update({f"{username}-password": new_password})
        event.set_results({f"{username}-password": new_password})

    def _get_password_action(self, event: ActionEvent) -> None:
        """Handler for get-password action.

        Get credentials for internal `operator` user.
        """
        authfile = self.charm.workload.read(self.charm.workload.paths.registry_authfile)

        if not authfile:
            msg = "authfile not found on target unit."
            logger.error(msg)
            event.fail(msg)
            return

        event.set_results(
            {
                "username": ADMIN_USER,
                "password": self.charm.context.cluster.internal_user_credentials[ADMIN_USER],
            }
        )
