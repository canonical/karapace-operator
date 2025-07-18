#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Objects representing the context and state of KarapaceCharm."""

from charms.data_platform_libs.v0.data_interfaces import (
    DataPeerData,
    DataPeerOtherUnitData,
    DataPeerUnitData,
    KafkaRequirerData,
)
from ops import Framework, Object, Relation, Unit

from core.models import Kafka, KarapaceClient, KarapaceCluster, KarapaceServer
from literals import (
    INTERNAL_USERS,
    KAFKA_CONSUMER_GROUP,
    KAFKA_REL,
    KAFKA_TOPIC,
    KARAPACE_REL,
    PEER,
    PORT,
    SECRETS_UNIT,
    Status,
    Substrate,
)
from relations.karapace import KarapaceProvidesData


class ClusterContext(Object):
    """Properties and relations of the charm."""

    def __init__(self, charm: Framework | Object, substrate: Substrate):
        super().__init__(parent=charm, key="charm_context")
        self.substrate: Substrate = substrate

        self.peer_app_interface = DataPeerData(self.model, relation_name=PEER)
        self.peer_unit_interface = DataPeerUnitData(
            self.model, relation_name=PEER, additional_secret_fields=SECRETS_UNIT
        )

        self.kafka_requirer_interface = KafkaRequirerData(
            model=self.model,
            relation_name=KAFKA_REL,
            topic=KAFKA_TOPIC,
            extra_user_roles="admin",
            consumer_group_prefix=KAFKA_CONSUMER_GROUP,
        )

        self.client_provider_interface = KarapaceProvidesData(
            self.model, relation_name=KARAPACE_REL
        )

        self._servers_data = {}

    # --- RELATIONS ---

    @property
    def peer_relation(self) -> Relation | None:
        """The cluster peer relation."""
        return self.model.get_relation(PEER)

    @property
    def kafka_relation(self) -> Relation | None:
        """The relation with Kafka."""
        return self.model.get_relation(KAFKA_REL)

    @property
    def karapace_relations(self) -> set[Relation]:
        """The relations of all client applications."""
        return set(self.model.relations[KARAPACE_REL])

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
        servers.add(self.server)

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
            relation=self.kafka_relation,
            data_interface=self.kafka_requirer_interface,
            component=self.model.app,
            substrate=self.substrate,
        )

    @property
    def clients(self) -> set[KarapaceClient]:
        """All connected client applications."""
        clients = set()

        for relation in self.karapace_relations:
            if not relation.app:
                continue

            clients.add(
                KarapaceClient(
                    relation=relation,
                    data_interface=self.client_provider_interface,
                    component=relation.app,
                )
            )

        return clients

    # --- ADDITIONAL METHODS ---

    @property
    def super_users(self) -> set[str]:
        """Generates all users with super/admin permissions for the cluster from relations.

        Returns:
            Set of current super users
        """
        super_users = set(INTERNAL_USERS)
        for relation in self.karapace_relations:
            if not relation or not relation.app:
                continue

            extra_user_roles = relation.data[relation.app].get("extra-user-roles", "")
            password = self.cluster.relation_data.get(f"relation-{relation.id}", None)
            # if passwords are set for client admins, they're good to load
            if "admin" in extra_user_roles and password:
                super_users.add(f"relation-{relation.id}")

        return super_users

    @property
    def endpoints(self) -> str:
        """The current Karapace uris.

        Returns:
            List of servers
        """
        if not self.peer_relation:
            return ""

        return ",".join(sorted([f"{server.host}:{PORT}" for server in self.servers]))

    @property
    def ready_to_start(self) -> Status:
        """Check for active Kafka relation and adding of internal username.

        Returns:
            True if kafka is related and `admin` user has been added. False otherwise.
        """
        if not self.peer_relation:
            return Status.NO_PEER_RELATION

        if not self.kafka:
            return Status.KAFKA_NOT_RELATED

        if not self.kafka.kafka_ready:
            return Status.KAFKA_NO_DATA

        # TLS must be enabled for Kafka and Karapace or disabled for both
        if self.cluster.tls_enabled ^ self.kafka.tls:
            return Status.KAFKA_TLS_MISMATCH

        if not self.cluster.internal_user_credentials:
            return Status.NO_CREDS

        return Status.ACTIVE
