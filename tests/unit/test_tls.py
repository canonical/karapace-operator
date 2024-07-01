#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import socket
from pathlib import Path
from unittest.mock import patch

import yaml
from scenario import Context, State
from src.charm import KarapaceCharm
from src.literals import SUBSTRATE, Status

ACTIONS = str(yaml.safe_load(Path("./actions.yaml").read_text()))
METADATA = str(yaml.safe_load(Path("./metadata.yaml").read_text()))
CHARM_KEY = "karapace"
KAFKA = "kafka"


def test_blocked_before_tls_relation(ctx: Context, peer_relation_no_data, kafka_relation_tls):
    state_in = State(relations=[peer_relation_no_data, kafka_relation_tls], leader=True)
    state_out: State = ctx.run("config_changed", state_in)

    assert state_out.unit_status == Status.KAFKA_TLS_MISMATCH.value.status


def test_sans_config(ctx: Context, peer_relation, kafka_relation_tls, tls_relation):
    state_in = State(relations=[peer_relation, kafka_relation_tls, tls_relation], leader=True)

    with ctx.manager("config_changed", state_in) as manager:
        # This is your charm instance, after ops has set it up:
        charm: KarapaceCharm = manager.charm
        manager.run()

        sock_dns = socket.getfqdn()
        if SUBSTRATE == "vm":
            assert charm.tls._sans == {
                "sans_ip": ["treebeard"],
                "sans_dns": [f"{CHARM_KEY}/0", sock_dns],
            }
        elif SUBSTRATE == "k8s":
            # NOTE previous k8s sans_ip like karapace-k8s-0.karapace-k8s-endpoints or binding pod address
            with patch("ops.model.Model.get_binding"):
                assert charm.tls._sans["sans_dns"] == [
                    "karapace-k8s-0",
                    "karapace-k8s-0.karapace-k8s-endpoints",
                    sock_dns,
                ]
