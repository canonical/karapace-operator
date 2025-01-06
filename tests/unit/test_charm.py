#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import json
from typing import cast
from unittest.mock import patch

from ops.testing import Context, State
from src.charm import KarapaceCharm
from src.literals import Status

CHARM_KEY = "karapace"
KAFKA = "kafka"


def patched_exec_side_effects(*args, **kwargs):
    if "charmed-karapace.mkpasswd -u operator" in kwargs.get("command", ""):
        return json.dumps(
            {
                "username": "operator",
                "algorithm": "sha512",
                "salt": "test",
                "password_hash": "test",
            }
        )


def patched_write_side_effects(*args, **kwargs):
    initial_expected_file = json.dumps(
        {
            "users": [
                {
                    "username": "operator",
                    "algorithm": "sha512",
                    "salt": "test",
                    "password_hash": "test",
                }
            ],
            "permissions": [
                {
                    "username": "operator",
                    "operation": "Write",
                    "resource": ".*",
                }
            ],
        },
        indent=2,
    )

    if initial_expected_file in kwargs.get("content", ""):
        return
    else:
        raise AssertionError


def test_install_blocks_snap_install_failure(ctx: Context):
    state_in = State()
    with patch("workload.KarapaceWorkload.install", return_value=False):
        state_out: State = ctx.run(ctx.on.install(), state_in)

    assert state_out.unit_status == Status.SNAP_NOT_INSTALLED.value.status


def test_install_snap(ctx: Context):
    state_in = State()
    with patch("workload.KarapaceWorkload.install", return_value=True):
        state_out: State = ctx.run(ctx.on.install(), state_in)

    assert state_out.unit_status != Status.SNAP_NOT_INSTALLED.value.status


def test_start_no_peer_relation(ctx: Context):
    state_in = State()
    state_out: State = ctx.run(ctx.on.start(), state_in)

    assert state_out.unit_status == Status.NO_PEER_RELATION.value.status


def test_start_defers_if_no_credentials_and_no_leader(ctx: Context, peer_relation_no_data):
    state_in = State(relations=[peer_relation_no_data])
    state_out: State = ctx.run(ctx.on.start(), state_in)

    assert len(state_out.deferred) == 1
    assert state_out.deferred[0].name == "start"


def test_start_creates_credentials(
    ctx: Context, peer_relation_no_data, patched_exec, patched_workload_write
):
    patched_exec.side_effect = patched_exec_side_effects
    patched_workload_write.side_effect = patched_write_side_effects
    state_in = State(relations=[peer_relation_no_data], leader=True)

    with ctx(ctx.on.start(), state_in) as manager:
        charm: KarapaceCharm = cast(KarapaceCharm, manager.charm)
        manager.run()

        # NOTE side_effect of patched write will already assert expected output as well
        assert "operator" in charm.context.cluster.internal_user_credentials


def test_start_updates_credentials_when_no_leader(
    ctx: Context, peer_relation, patched_exec, patched_workload_write
):
    patched_exec.side_effect = patched_exec_side_effects
    patched_workload_write.side_effect = patched_write_side_effects
    state_in = State(relations=[peer_relation])
    ctx.run(ctx.on.start(), state_in)

    # NOTE side_effect of patched write will already assert expected output as well
    patched_workload_write.assert_called_once()


def test_ready_to_start_no_peer_relation(ctx: Context):
    state_in = State(leader=True)
    state_out: State = ctx.run(ctx.on.config_changed(), state_in)

    assert state_out.unit_status == Status.NO_PEER_RELATION.value.status


def test_ready_to_start_kafka_not_related(ctx: Context, peer_relation_no_data):
    state_in = State(relations=[peer_relation_no_data], leader=True)
    state_out: State = ctx.run(ctx.on.config_changed(), state_in)

    assert state_out.unit_status == Status.KAFKA_NOT_RELATED.value.status


def test_ready_to_start_kafka_no_data(ctx: Context, peer_relation_no_data, kafka_relation_no_data):
    state_in = State(relations=[peer_relation_no_data, kafka_relation_no_data], leader=True)
    state_out: State = ctx.run(ctx.on.config_changed(), state_in)

    assert state_out.unit_status == Status.KAFKA_NO_DATA.value.status


def test_ready_to_start_no_internal_credentials(
    ctx: Context, peer_relation_no_data, kafka_relation
):
    state_in = State(relations=[peer_relation_no_data, kafka_relation], leader=True)
    state_out: State = ctx.run(ctx.on.config_changed(), state_in)

    assert state_out.unit_status == Status.NO_CREDS.value.status


def test_config_changed_succeeds(
    ctx: Context,
    peer_relation,
    kafka_relation,
    patched_workload_write,
    patched_restart,
    patched_exec,
):
    patched_exec.side_effect = patched_exec_side_effects
    state_in = State(relations=[peer_relation, kafka_relation], leader=True)
    state_out = ctx.run(ctx.on.config_changed(), state_in)

    patched_restart.assert_called_once()
    assert state_out.unit_status == Status.ACTIVE.value.status


def test_update_status_blocks_if_not_healthy(ctx: Context, peer_relation, kafka_relation):
    state_in = State(relations=[peer_relation, kafka_relation], leader=True)
    with patch("workload.KarapaceWorkload.active", return_value=False):
        state_out = ctx.run(ctx.on.update_status(), state_in)

    assert state_out.unit_status == Status.SERVICE_NOT_RUNNING.value.status


def test_update_status_blocks_if_kafka_not_connected(ctx: Context, peer_relation, kafka_relation):
    state_in = State(relations=[peer_relation, kafka_relation], leader=True)
    with (
        patch("managers.kafka.KafkaManager.brokers_active", return_value=False),
        patch("workload.KarapaceWorkload.active", return_value=True),
    ):
        state_out = ctx.run(ctx.on.update_status(), state_in)

    assert state_out.unit_status == Status.KAFKA_NOT_CONNECTED.value.status


def test_update_status_succeeds(
    ctx: Context,
    peer_relation,
    kafka_relation,
    patched_workload_write,
    patched_restart,
    patched_exec,
):
    patched_exec.side_effect = patched_exec_side_effects
    state_in = State(relations=[peer_relation, kafka_relation], leader=True)
    with (
        patch("managers.kafka.KafkaManager.brokers_active", return_value=True),
        patch("workload.KarapaceWorkload.active", return_value=True),
    ):
        state_out = ctx.run(ctx.on.update_status(), state_in)

    assert state_out.unit_status == Status.ACTIVE.value.status
