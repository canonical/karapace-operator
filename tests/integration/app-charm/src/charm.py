#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Application charm that connects to database charms.

This charm is meant to be used only for testing
of the libraries in this repository.
"""

import logging

from ops.charm import CharmBase
from ops.main import main
from ops.model import ActiveStatus

from relations.karapace import KarapaceRequires, SubjectAllowedEvent

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
        self.kafka_requirer_admin = KarapaceRequires(
            self, relation_name=REL_NAME_ADMIN, subject="test-topic", extra_user_roles="admin"
        )

        self.framework.observe(getattr(self.on, "start"), self._on_start)

        self.framework.observe(
            self.karapace_requirer_user.on.subject_allowed, self.on_subject_allowed_user
        )
        self.framework.observe(
            self.kafka_requirer_admin.on.subject_allowed, self.on_subject_allowed_admin
        )

    def _on_start(self, _) -> None:
        self.unit.status = ActiveStatus()

    def on_subject_allowed_user(self, event: SubjectAllowedEvent):
        logger.info(f"{event.username} {event.password} {event.endpoints} {event.tls}")
        return

    def on_subject_allowed_admin(self, event: SubjectAllowedEvent):
        logger.info(f"{event.username} {event.password} {event.endpoints} {event.tls}")
        return


if __name__ == "__main__":
    main(ApplicationCharm)
