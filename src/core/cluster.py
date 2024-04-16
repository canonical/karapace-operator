#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Objects representing the context and state of KarapaceCharm."""

from charms.data_platform_libs.v0.data_interfaces import (
    DataPeerData,
    DataPeerOtherUnitData,
    DataPeerUnitData,
    KafkaRequiresData,
)
from ops import Framework, Object, Relation, Unit

from core.models import Kafka, KarapaceCluster, KarapaceServer
from literals import (
    KAFKA_CONSUMER_GROUP,
    KAFKA_REL,
    KAFKA_TOPIC,
    PEER,
    SECRETS_UNIT,
    Status,
    Substrate,
)


class ClusterContext(Object):
    """Properties and relations of the charm."""

    def __init__(self, charm: Framework | Object, substrate: Substrate):
        super().__init__(parent=charm, key="charm_context")
        self.substrate: Substrate = substrate

        self.peer_app_interface = DataPeerData(self.model, relation_name=PEER)
        self.peer_unit_interface = DataPeerUnitData(
            self.model, relation_name=PEER, additional_secret_fields=SECRETS_UNIT
        )

        self.kafka_requirer_interface = KafkaRequiresData(
            model=self.model,
            relation_name=KAFKA_REL,
            topic=KAFKA_TOPIC,
            extra_user_roles="admin",
            consumer_group_prefix=KAFKA_CONSUMER_GROUP,
        )

        self._servers_data = {}

    # --- RELATIONS ---

    @property
    def peer_relation(self) -> Relation:
        """The cluster peer relation."""
        if not (peer_relation := self.model.get_relation(PEER)):
            raise AttributeError(f"No peer relation {PEER} found.")
        return peer_relation

    @property
    def kafka_relation(self) -> Relation:
        """The relations of all client applications."""
        if not (kafka_relation := self.model.get_relation(KAFKA_REL)):
            raise AttributeError(f"No {KAFKA_REL} found.")
        return kafka_relation

    # --- CORE COMPONENTS ---

    @property
    def peer_units_data_interfaces(self) -> dict[Unit, DataPeerOtherUnitData]:
        """The cluster peer relation."""
        if not self.peer_relation or not self.peer_relation.units:
            return {}

        for unit in self.peer_relation.units:
            if unit not in self._servers_data:
                self._servers_data[unit] = DataPeerOtherUnitData(
                    model=self.model, unit=unit, relation_name=PEER
                )
        return self._servers_data

    @property
    def server(self) -> KarapaceServer:
        """The server state of the current running Unit."""
        return KarapaceServer(
            relation=self.peer_relation,
            data_interface=self.peer_unit_interface,
            component=self.model.unit,
            substrate=self.substrate,
        )

    @property
    def servers(self) -> set[KarapaceServer]:
        """Grabs all servers in the current peer relation, including the running unit server.

        Returns:
            Set of KarapaceServer in the current peer relation, including the running unit server.
        """
        if not self.peer_relation:
            return set()

        servers = set()
        for unit, data_interface in self.peer_units_data_interfaces.items():
            servers.add(
                KarapaceServer(
                    relation=self.peer_relation,
                    data_interface=data_interface,
                    component=unit,
                    substrate=self.substrate,
                )
            )

        return servers

    @property
    def cluster(self) -> KarapaceCluster:
        """The cluster state of the current running App."""
        return KarapaceCluster(
            relation=self.peer_relation,
            data_interface=self.peer_app_interface,
            component=self.model.app,
            substrate=self.substrate,
        )

    @property
    def kafka(self) -> Kafka:
        """The Kafka relation state."""
        return Kafka(
            relation=self.peer_relation,
            data_interface=self.kafka_requirer_interface,
            component=self.model.app,
            substrate=self.substrate,
        )

    # --- ADDITIONAL METHODS ---

    @property
    def ready_to_start(self) -> Status:
        """Check for active Kafka relation and adding of internal username.

        Returns:
            True if kafka is related and `admin` user has been added. False otherwise.
        """
        if not self.has_peer_relation():
            return Status.NO_PEER_RELATION

        # TODO: Uncomment after relation is added
        # if not self.kafka.kafka_related:
        #     return Status.KAFKA_NOT_RELATED

        # if not self.kafka.kafka_ready:
        #     return Status.KAFKA_NO_DATA

        # TLS must be enabled for Kafka and karapace or disabled for both
        # if self.cluster.tls_enabled ^ self.kafka.tls:
        #     return Status.KAFKA_TLS_MISMATCH

        if not self.cluster.internal_user_credentials:
            return Status.NO_CREDS

        return Status.ACTIVE

    def has_peer_relation(self) -> bool:
        """The cluster has a peer relation."""
        try:
            return bool(self.peer_relation)
        except AttributeError:
            return False
