#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Application charm that connects to database charms.

This charm is meant to be used only for testing
of the libraries in this repository.
"""

import logging

from charms.data_platform_libs.v0.data_interfaces import KarapaceRequires, SubjectAllowedEvent
from ops import ActionEvent, ActiveStatus, CharmBase
from ops.main import main

logger = logging.getLogger(__name__)

CHARM_KEY = "app"
PEER = "cluster"
REL_NAME_USER = "karapace-client-user"
REL_NAME_ADMIN = "karapace-client-admin"


class ApplicationCharm(CharmBase):
    """Application charm that connects to database charms."""

    def __init__(self, *args):
        super().__init__(*args)
        self.name = CHARM_KEY

        self.karapace_requirer_user = KarapaceRequires(
            self, relation_name=REL_NAME_USER, subject="test-topic", extra_user_roles="user"
        )
        self.karapace_requirer_admin = KarapaceRequires(
            self, relation_name=REL_NAME_ADMIN, subject="test-topic", extra_user_roles="admin"
        )

        self.framework.observe(getattr(self.on, "start"), self._on_start)
        self.framework.observe(
            self.karapace_requirer_user.on.subject_allowed, self.on_subject_allowed_user
        )
        self.framework.observe(
            self.karapace_requirer_admin.on.subject_allowed, self.on_subject_allowed_admin
        )
        self.framework.observe(
            getattr(self.on, "get_credentials_action"), self._get_credentials_action
        )

    def _on_start(self, _) -> None:
        self.unit.status = ActiveStatus()

    def on_subject_allowed_user(self, event: SubjectAllowedEvent):
        logger.info(f"{event.username} {event.password} {event.endpoints} {event.tls}")
        return

    def on_subject_allowed_admin(self, event: SubjectAllowedEvent):
        logger.info(f"{event.username} {event.password} {event.endpoints} {event.tls}")
        return

    def _get_credentials_action(self, event: ActionEvent) -> None:
        """Handler for get-credentials action."""
        user = event.params.get("username")
        username = ""
        password = ""
        relation = self.model.get_relation(
            relation_name=REL_NAME_USER if user == "user" else REL_NAME_ADMIN
        )
        if not relation:
            return

        if user == "user":
            username = self.karapace_requirer_user.fetch_relation_field(
                relation_id=relation.id, field="username"
            )
            password = self.karapace_requirer_user.fetch_relation_field(
                relation_id=relation.id, field="password"
            )
        else:
            username = self.karapace_requirer_admin.fetch_relation_field(
                relation_id=relation.id, field="username"
            )
            password = self.karapace_requirer_admin.fetch_relation_field(
                relation_id=relation.id, field="password"
            )

        event.set_results({"username": username, "password": password})


if __name__ == "__main__":
    main(ApplicationCharm)
