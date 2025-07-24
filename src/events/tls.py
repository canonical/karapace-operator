#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manager for handling Karapace TLS configuration."""

import base64
import logging
import re
import socket
from typing import TYPE_CHECKING

from charms.tls_certificates_interface.v4.tls_certificates import (
    CertificateAvailableEvent,
    CertificateRequestAttributes,
    PrivateKey,
    TLSCertificatesRequiresV4,
    generate_private_key,
)
from ops.charm import ActionEvent
from ops.framework import EventBase, EventSource, Object

from literals import TLS_RELATION

if TYPE_CHECKING:
    from charm import KarapaceCharm

logger = logging.getLogger(__name__)


class RefreshTLSCertificatesEvent(EventBase):
    """Event for refreshing TLS certificates."""


class TLSHandler(Object):
    """Handler for managing the client and unit TLS keys/certs."""

    refresh_tls_certificates = EventSource(RefreshTLSCertificatesEvent)

    def __init__(self, charm):
        super().__init__(charm, "tls")
        self.charm: "KarapaceCharm" = charm

        self.common_name = f"{self.charm.unit.name}-{self.charm.model.uuid}"

        private_key = None

        if key := self.charm.context.server.private_key:
            private_key = PrivateKey.from_string(key)

        sans_ip = self._sans["sans_ip"] or []
        sans_dns = self._sans["sans_dns"] or []

        self.certificates = TLSCertificatesRequiresV4(
            self.charm,
            TLS_RELATION,
            certificate_requests=[
                CertificateRequestAttributes(
                    common_name=self.common_name,
                    sans_ip=frozenset(sans_ip),
                    sans_dns=frozenset(sans_dns),
                ),
            ],
            refresh_events=[self.refresh_tls_certificates],
            private_key=private_key,
        )

        # Own certificates handlers
        self.framework.observe(
            self.charm.on[TLS_RELATION].relation_created, self._tls_relation_created
        )
        self.framework.observe(
            self.charm.on[TLS_RELATION].relation_joined, self._tls_relation_joined
        )
        self.framework.observe(
            self.charm.on[TLS_RELATION].relation_broken, self._tls_relation_broken
        )
        self.framework.observe(
            getattr(self.certificates.on, "certificate_available"), self._on_certificate_available
        )
        self.framework.observe(
            getattr(self.charm.on, "set_tls_private_key_action"), self._set_tls_private_key
        )

    def _tls_relation_created(self, _) -> None:
        """Handler for `certificates_relation_created` event."""
        if not self.charm.unit.is_leader() or not self.charm.context.peer_relation:
            return

        self.charm.context.cluster.update({"tls": "enabled"})

    def _tls_relation_joined(self, _) -> None:
        """Handler for `certificates_relation_joined` event."""
        # generate unit private key if not already created by action
        if not self.charm.context.server.private_key:
            self.charm.context.server.update({"private-key": generate_private_key().raw})

    def _tls_relation_broken(self, _) -> None:
        """Handler for `certificates_relation_broken` event."""
        self.charm.context.server.update({"csr": ""})
        self.charm.context.server.update({"certificate": ""})
        self.charm.context.server.update({"ca-cert": ""})

        # remove all existing keystores from the unit so we don't preserve certs
        self.charm.tls_manager.remove_stores()

        if not self.charm.unit.is_leader():
            return

        self.charm.context.cluster.update({"tls": ""})

    def _on_certificate_available(self, event: CertificateAvailableEvent) -> None:
        """Handler for `certificates_available` event after provider updates signed certs."""
        if not self.charm.context.peer_relation:
            logger.warning("No peer relation on certificate available")
            event.defer()
            return

        self.charm.context.server.update({"certificate": event.certificate.raw})
        self.charm.context.server.update({"ca-cert": event.ca.raw})
        # Update private key if required.
        private_key = self.certificates.private_key
        if private_key and private_key.raw != self.charm.context.server.private_key:
            self.charm.context.server.update({"private-key": private_key.raw})

        self.charm.tls_manager.set_server_key()
        self.charm.tls_manager.set_ca()
        self.charm.tls_manager.set_certificate()

    def _set_tls_private_key(self, event: ActionEvent) -> None:
        """Handler for `set_tls_private_key` action."""
        key = event.params.get("internal-key") or generate_private_key().raw
        private_key = (
            key
            if re.match(r"(-+(BEGIN|END) [A-Z ]+-+)", key)
            else base64.b64decode(key).decode("utf-8")
        )

        self.charm.context.server.update({"private-key": private_key})
        self.certificates._private_key = PrivateKey.from_string(private_key)
        self.refresh_tls_certificates.emit()

    @property
    def _sans(self) -> dict[str, list[str] | None]:
        """Builds a SAN dict of DNS names and IPs for the unit."""
        if self.charm.substrate == "vm":
            return {
                "sans_ip": [self.charm.context.server.host],
                "sans_dns": [self.model.unit.name, socket.getfqdn()],
            }
        else:
            bind_address = ""
            if self.charm.context.peer_relation:
                if binding := self.charm.model.get_binding(self.charm.context.peer_relation):
                    bind_address = binding.network.bind_address
            return {
                "sans_ip": [str(bind_address)],
                "sans_dns": [
                    self.charm.context.server.host.split(".")[0],
                    self.charm.context.server.host,
                    socket.getfqdn(),
                ],
            }
