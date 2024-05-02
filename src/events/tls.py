#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Manager for handling Karapace TLS configuration."""

import base64
import logging
import re
import socket
from typing import TYPE_CHECKING

from charms.tls_certificates_interface.v1.tls_certificates import (
    CertificateAvailableEvent,
    TLSCertificatesRequiresV1,
    generate_csr,
    generate_private_key,
)
from ops.charm import ActionEvent
from ops.framework import Object

from literals import TLS_RELATION

if TYPE_CHECKING:
    from charm import KarapaceCharm

logger = logging.getLogger(__name__)


class TLSHandler(Object):
    """Handler for managing the client and unit TLS keys/certs."""

    def __init__(self, charm):
        super().__init__(charm, "tls")
        self.charm: "KarapaceCharm" = charm

        self.certificates = TLSCertificatesRequiresV1(self.charm, TLS_RELATION)

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
            getattr(self.certificates.on, "certificate_expiring"), self._on_certificate_expiring
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
            self.charm.context.server.update(
                {"private-key": generate_private_key().decode("utf-8")}
            )

        self._request_certificate()

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

        # avoid setting tls files and restarting
        if event.certificate_signing_request != self.charm.context.server.csr:
            logger.error("Can't use certificate, found unknown CSR")
            return

        self.charm.context.server.update({"certificate": event.certificate})
        self.charm.context.server.update({"ca-cert": event.ca})

        self.charm.tls_manager.set_server_key()
        self.charm.tls_manager.set_ca()
        self.charm.tls_manager.set_certificate()

    def _on_certificate_expiring(self, _) -> None:
        """Handler for `certificate_expiring` event."""
        if (
            not self.charm.context.server.private_key
            or not self.charm.context.server.csr
            or not self.charm.context.peer_relation
        ):
            logger.error("Missing unit private key and/or old csr")
            return
        new_csr = generate_csr(
            private_key=self.charm.context.server.private_key.encode("utf-8"),
            subject=self.charm.context.server.relation_data.get("private-address", ""),
            sans_ip=self._sans["sans_ip"],
            sans_dns=self._sans["sans_dns"],
        )

        self.certificates.request_certificate_renewal(
            old_certificate_signing_request=self.charm.context.server.csr.encode("utf-8"),
            new_certificate_signing_request=new_csr,
        )

        self.charm.context.server.update({"csr": new_csr.decode("utf-8").strip()})

    def _set_tls_private_key(self, event: ActionEvent) -> None:
        """Handler for `set_tls_private_key` action."""
        key = event.params.get("internal-key") or generate_private_key().decode("utf-8")
        private_key = (
            key
            if re.match(r"(-+(BEGIN|END) [A-Z ]+-+)", key)
            else base64.b64decode(key).decode("utf-8")
        )

        self.charm.context.server.update({"private-key": private_key})
        self._on_certificate_expiring(event)

    def _request_certificate(self):
        """Generates and submits CSR to provider."""
        if not self.charm.context.server.private_key or not self.charm.context.peer_relation:
            logger.error("Can't request certificate, missing private key")
            return

        csr = generate_csr(
            private_key=self.charm.context.server.private_key.encode("utf-8"),
            subject=self.charm.context.server.relation_data.get("private-address", ""),
            sans_ip=self._sans["sans_ip"],
            sans_dns=self._sans["sans_dns"],
        )
        self.charm.context.server.update({"csr": csr.decode("utf-8").strip()})

        self.certificates.request_certificate_creation(certificate_signing_request=csr)

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
