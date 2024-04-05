#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Collection of state objects for the Karapace relations, apps and units."""

import logging
from collections.abc import MutableMapping

from charms.data_platform_libs.v0.data_interfaces import Data, DataPeerData, KafkaRequiresData, DataPeerUnitData
from ops.model import Application, Relation, Unit
from typing_extensions import override

from literals import INTERNAL_USERS, SECRETS_APP, Substrate

logger = logging.getLogger(__name__)


class StateBase:
    """Base state object."""

    def __init__(
        self,
        relation: Relation | None,
        data_interface: Data,
        component: Unit | Application,
        substrate: Substrate,
    ):
        self.relation = relation
        self.data_interface = data_interface
        self.component = component
        self.substrate = substrate

    def update(self, items: dict[str, str]) -> None:
        """Changes the state."""
        raise NotImplementedError

    def data(self) -> MutableMapping:
        """Data representing the state."""
        raise NotImplementedError


class RelationState(StateBase):
    """Base state object."""

    def __init__(
        self,
        relation: Relation,
        data_interface: Data,
        component: Unit | Application,
        substrate: Substrate,
    ):
        super().__init__(relation, data_interface, component, substrate)
        # Redundant definition as lint can't resolve that super's relation may be None
        self.relation = relation
        self.relation_data = self.data_interface.as_dict(self.relation.id)

    @property
    def data(self) -> MutableMapping:
        """Data representing the state."""
        return self.relation_data

    def update(self, items: dict[str, str]) -> None:
        """Writes to relation_data."""
        delete_fields = [key for key in items if not items[key]]
        update_content = {k: items[k] for k in items if k not in delete_fields}

        self.relation_data.update(update_content)

        for field in delete_fields:
            del self.relation_data[field]


class KarapaceServer(RelationState):
    """State collection metadata for a charm unit."""

    def __init__(
        self,
        relation: Relation,
        data_interface: DataPeerUnitData,
        component: Unit,
        substrate: Substrate,
    ):
        super().__init__(relation, data_interface, component, substrate)
        self.unit = component

    @property
    def unit_id(self) -> int:
        """The id of the unit from the unit name.

        e.g karapace/1 --> 1
        """
        return int(self.component.name.split("/")[1])

    # -- Cluster Init --

    @property
    def hostname(self) -> str:
        """The hostname for the unit."""
        return self.data.get("hostname", "")  # pyright: ignore reportGeneralTypeIssues

    @property
    def fqdn(self) -> str:
        """The Fully Qualified Domain Name for the unit."""
        return self.data.get("fqdn", "")  # pyright: ignore reportGeneralTypeIssues

    @property
    def ip(self) -> str:
        """The IP for the unit."""
        return self.data.get("ip", "")  # pyright: ignore reportGeneralTypeIssues

    @property
    def host(self) -> str:
        """The hostname for the unit."""
        host = ""
        if self.substrate == "vm":
            for key in ["hostname", "ip", "private-address"]:
                if host := self.data.get(key, ""):
                    break

        if self.substrate == "k8s":
            host = f"{self.component.name.split('/')[0]}-{self.unit_id}.{self.component.name.split('/')[0]}-endpoints"

        return host  # pyright: ignore reportGeneralTypeIssues

    # -- TLS --

    @property
    def private_key(self) -> str:
        """The private-key contents for the unit to use for TLS."""
        return self.data.get("private-key", "")

    @property
    def csr(self) -> str:
        """The current certificate signing request contents for the unit."""
        return self.data.get("csr", "")

    @property
    def certificate(self) -> str:
        """The certificate contents for the unit to use for TLS."""
        return self.data.get("certificate", "")

    @property
    def ca(self) -> str:
        """The root CA contents for the unit to use for TLS."""
        return self.data.get("ca-cert", "")


class KarapaceCluster(RelationState):
    """State collection metadata for the peer relation."""

    def __init__(
        self,
        relation: Relation,
        data_interface: DataPeerData,
        component: Application,
        substrate: Substrate,
    ):
        super().__init__(relation, data_interface, component, substrate)
        self.data_interface = data_interface  # Allow linter to solve DataPeerData API
        self.app = component

    @override
    def update(self, items: dict[str, str]) -> None:
        """Overridden update to allow for same interface, but writing to local app bag."""
        if not self.relation:
            return

        for key, value in items.items():
            if key in SECRETS_APP or key.startswith("relation-"):
                if value:
                    self.data_interface.set_secret(self.relation.id, key, value)
                else:
                    self.data_interface.delete_secret(self.relation.id, key)
            else:
                self.data_interface.update_relation_data(self.relation.id, {key: value})

    @property
    def internal_user_credentials(self) -> dict[str, str]:
        """The charm internal usernames and passwords, e.g `operator`

        Returns:
            Dict of usernames and passwords
        """
        credentials = {
            user: password
            for user in INTERNAL_USERS
            if (password := self.relation_data.get(f"{user}-password"))
        }

        if not len(credentials) == len(INTERNAL_USERS):
            return {}

        return credentials

    # --- TLS ---

    @property
    def tls_enabled(self) -> bool:
        """Flag to check if the cluster should run with TLS.

        Returns:
            True if TLS encryption should be active. Otherwise False
        """
        self.data_interface.fetch_my_relation_data
        return self.relation_data.get("tls", "disabled") == "enabled"

    @property
    def security_protocol(self) -> str:
        """Return the security protocol."""
        return "SASL_PLAINTEXT" if not self.tls_enabled else "SASL_SSL"


class Kafka(RelationState):
    """State collection metadata for a single related client application."""

    def __init__(
        self,
        relation: Relation,
        data_interface: KafkaRequiresData,
        component: Application,
        substrate: Substrate,
    ):
        super().__init__(relation, data_interface, component, substrate)
        self.app = component

    @property
    def topic(self) -> str:
        """Get the topic if it has been created."""
        return self.data.get("topic", "")

    @property
    def username(self) -> str:
        """Username to connect to Kafka."""
        return self.data.get("username", "")

    @property
    def password(self) -> str:
        """Password of the Kafka user."""
        return self.data.get("password", "")

    @property
    def bootstrap_servers(self) -> str:
        """IP/host where Kafka is located."""
        return self.data.get("endpoints", "")

    @property
    def tls(self) -> bool:
        """Check if TLS is enabled on Kafka."""
        return self.data.get("tls", "")

    @property
    def kafka_related(self) -> bool:
        """Checks if there is a relation with Kafka.

        Returns:
            True if there is a Kafka relation. Otherwise False
        """
        return bool(self.relation)

    @property
    def kafka_ready(self) -> bool:
        """Checks if there is an active Kafka relation with all necessary data.

        Returns:
            True if Kafka is currently related with sufficient relation data for Karapace to
                connect with. Otherwise False
        """
        if not all([self.topic, self.username, self.password, self.bootstrap_servers]):
            return False

        return True
