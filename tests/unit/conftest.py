#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
from collections import defaultdict
from unittest.mock import patch, Mock

import pytest
from ops.testing import Context, PeerRelation, Relation
from src.charm import KarapaceCharm
from src.literals import SNAP_NAME


@pytest.fixture()
def ctx():
    return Context(KarapaceCharm)


@pytest.fixture()
def peer_relation_no_data():
    return PeerRelation(
        endpoint="cluster",
        interface="cluster",
        local_app_data={},
    )


@pytest.fixture()
def peer_relation():
    return PeerRelation(
        endpoint="cluster",
        interface="cluster",
        local_app_data={"operator-password": "password"},
        local_unit_data={"private-address": "treebeard"},
    )


@pytest.fixture()
def peer_relation_with_provider():
    return PeerRelation(
        endpoint="cluster",
        interface="cluster",
        local_app_data={"operator-password": "password", "relation-5000": "provider-password"},
        local_unit_data={"private-address": "treebeard"},
    )


@pytest.fixture()
def kafka_relation_no_data():
    """Provide fixture for the Kafka relation without data."""
    return Relation(
        endpoint="kafka",
        interface="kafka_client",
        remote_app_name="kafka",
        local_app_data={
            "topic": "_schemas",
            "extra-user-roles": "admin",
        },
        remote_app_data={
            "topic": "",
            "username": "",
            "password": "",
            "endpoints": "",
            "consumer-group-prefix": "",
            "zookeeper-uris": "",
        },
    )


@pytest.fixture
def kafka_relation():
    """Provide fixture for the Kafka relation."""
    return Relation(
        endpoint="kafka",
        interface="kafka_client",
        remote_app_name="kafka",
        local_app_data={
            "topic": "_schemas",
            "extra-user-roles": "admin",
        },
        remote_app_data={
            "topic": "_schemas",
            "username": "karapace",
            "password": "test",
            "endpoints": "kafka.servers:9091",
            "consumer-group-prefix": "",
            "zookeeper-uris": "zk.servers:8021",
        },
    )


@pytest.fixture()
def kafka_relation_tls():
    """Provide fixture for the Kafka relation."""
    return Relation(
        endpoint="kafka",
        interface="kafka_client",
        remote_app_name="kafka",
        local_app_data={
            "topic": "_schemas",
            "extra-user-roles": "admin",
        },
        remote_app_data={
            "topic": "_schemas",
            "username": "karapace",
            "password": "test",
            "endpoints": "kafka.servers:9091",
            "consumer-group-prefix": "",
            "zookeeper-uris": "zk.servers:8021",
            "tls": "enabled",
        },
    )


@pytest.fixture()
def tls_relation():
    """Provide a fixture for TLS relation."""
    return Relation(
        endpoint="certificates",
        interface="tls-certificates",
        remote_app_name="tls-certificates-operator",
        local_app_data={},
        remote_app_data={},
    )


@pytest.fixture()
def requirer_relation():
    # Forced relation id to ease mocking in test_provider.py
    return Relation(
        endpoint="karapace",
        interface="karapace_client",
        remote_app_name="requirer-app",
        id=5000,
        remote_app_data={"subject": "test-subject", "extra-user-roles": "user"},
    )


@pytest.fixture()
def patched_restart():
    with patch("workload.KarapaceWorkload.restart") as restart:
        yield restart


@pytest.fixture()
def patched_workload_write():
    with patch("workload.KarapaceWorkload.write") as workload_write:
        yield workload_write


@pytest.fixture()
def patched_workload_read():
    with patch("workload.KarapaceWorkload.read") as workload_read:
        yield workload_read


@pytest.fixture()
def patched_exec():
    with patch("workload.KarapaceWorkload.exec") as patched_exec:
        yield patched_exec


@pytest.fixture(autouse=True)
def patched_snap(monkeypatch):
    cache = Mock()
    snap_mock = Mock()
    snap_mock.services = defaultdict(default_factory=lambda _: {"active": True})
    cache.return_value = {SNAP_NAME: snap_mock}
    with monkeypatch.context() as m:
        m.setattr("charms.operator_libs_linux.v1.snap.SnapCache", cache)
        yield
