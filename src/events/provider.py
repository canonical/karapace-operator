#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""KarapaceProvider class and methods."""

import logging
from typing import TYPE_CHECKING

from ops.charm import RelationBrokenEvent
from ops.framework import Object

from literals import KARAPACE_REL
from relations.karapace import KarapaceProvides, SubjectRequestedEvent

if TYPE_CHECKING:
    from charm import KarapaceCharm


logger = logging.getLogger(__name__)


class KarapaceHandler(Object):
    """Implements the provider-side logic for client applications relating to Karpace."""

    def __init__(self, charm) -> None:
        super().__init__(charm, "karapace_client")
        self.charm: "KarapaceCharm" = charm
        self.karapace_provider = KarapaceProvides(self.charm, relation_name=KARAPACE_REL)

        self.framework.observe(
            self.charm.on[KARAPACE_REL].relation_broken, self._on_relation_broken
        )
        self.framework.observe(
            getattr(self.karapace_provider.on, "subject_requested"), self.on_subject_requested
        )

    def on_subject_requested(self, event: SubjectRequestedEvent):
        """Handle a subject requested event."""
        if not self.charm.healthy:
            event.defer()
            return

        if not self.charm.unit.is_leader():
            return

        extra_user_roles = event.extra_user_roles or ""
        subject = event.subject or ""
        relation = event.relation
        username = f"relation-{relation.id}"
        password = (
            self.charm.context.cluster.client_passwords.get(username)
            or self.charm.workload.generate_password()
        )
        endpoints = self.charm.context.endpoints
        tls = "enabled" if self.charm.context.cluster.tls_enabled else "disabled"

        self.charm.auth_manager.add_user(username=username, password=password)
        self.charm.auth_manager.add_acl(username=username, subject=subject, role=extra_user_roles)
        self.charm.auth_manager.write_authfile()

        # non-leader units need cluster_config_changed event to update their super.users
        self.charm.context.cluster.update(
            {username: password, "super-users": self.charm.context.super_users}
        )

        self.karapace_provider.set_endpoint(relation.id, endpoints)
        self.karapace_provider.set_credentials(relation.id, username, password)
        self.karapace_provider.set_tls(relation.id, tls)
        self.karapace_provider.set_subject(relation.id, subject)

        # Restart needed to apply changes to auth
        self.charm.on[f"{self.charm.restart.name}"].acquire_lock.emit()

    def _on_relation_broken(self, event: RelationBrokenEvent):
        """Handle relation broken event."""
        # don't remove anything if app is going down
        if not self.charm.unit.is_leader() or self.charm.app.planned_units == 0:
            return

        if not self.charm.healthy:
            event.defer()
            return

        if event.relation.app != self.charm.app or not self.charm.app.planned_units() == 0:
            username = f"relation-{event.relation.id}"
            self.charm.auth_manager.remove_user(username=username)
            self.charm.auth_manager.write_authfile()

            # non-leader units need cluster_config_changed event to update their super.users
            # update on the peer relation data will trigger an update of server properties on all units
            self.charm.context.cluster.update({username: ""})

            # Restart needed to apply changes to auth
            self.charm.on[f"{self.charm.restart.name}"].acquire_lock.emit()
