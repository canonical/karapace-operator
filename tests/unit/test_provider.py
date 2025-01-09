#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import json
from unittest.mock import patch

from ops.testing import Context, Secret, State

CHARM_KEY = "karapace"
KAFKA = "kafka"


def patched_exec_side_effects(*args, **kwargs):
    # Relation number depends on the number of relations created so far on tests
    if "charmed-karapace.mkpasswd -u relation-5000" in kwargs.get("command", ""):
        return json.dumps(
            {
                "username": "relation-5000",
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
                    "username": "relation-5000",
                    "algorithm": "sha512",
                    "salt": "test",
                    "password_hash": "test",
                }
            ],
            "permissions": [
                {
                    "username": "relation-5000",
                    "operation": "Read",
                    "resource": "Config:",
                },
                {
                    "username": "relation-5000",
                    "operation": "Read",
                    "resource": "Subject:test-subject.*",
                },
            ],
        },
        indent=2,
    )

    if initial_expected_file in kwargs.get("content", ""):
        return
    else:
        raise AssertionError


def test_subject_requested_defers_if_not_healthy(
    ctx: Context, peer_relation, kafka_relation, requirer_relation
):
    state_in = State(relations=[peer_relation, kafka_relation, requirer_relation], leader=True)
    with patch("workload.KarapaceWorkload.active", return_value=False):
        state_out = ctx.run(ctx.on.relation_changed(requirer_relation), state_in)

    assert len(state_out.deferred) == 1
    assert state_out.deferred[0].name == "subject_requested"


def test_subject_requested_returns_if_not_leader(
    ctx: Context,
    peer_relation,
    kafka_relation,
    requirer_relation,
    patched_workload_write,
    patched_exec,
):
    state_in = State(relations=[peer_relation, kafka_relation, requirer_relation])
    with patch("workload.KarapaceWorkload.active", return_value=True):
        ctx.run(ctx.on.relation_changed(requirer_relation), state_in)

    patched_exec.assert_not_called()
    patched_workload_write.assert_not_called()


def test_subject_requested(
    ctx: Context,
    peer_relation,
    kafka_relation,
    requirer_relation,
    patched_workload_write,
    patched_exec,
):
    patched_exec.side_effect = patched_exec_side_effects
    patched_workload_write.side_effect = patched_write_side_effects
    state_in = State(relations=[peer_relation, kafka_relation, requirer_relation], leader=True)
    with patch("workload.KarapaceWorkload.active", return_value=True):
        state_out = ctx.run(ctx.on.relation_changed(requirer_relation), state_in)

    # NOTE side_effect of patched write will already assert expected output as well
    patched_workload_write.assert_called_once()

    assert (secret := next(iter(state_out.secrets)))
    assert "relation-5000" in secret.tracked_content


def test_relation_broken_defers_if_not_healty(
    ctx: Context,
    peer_relation,
    kafka_relation,
    requirer_relation,
):
    state_in = State(relations=[peer_relation, kafka_relation, requirer_relation], leader=True)
    with patch("workload.KarapaceWorkload.active", return_value=False):
        state_out = ctx.run(ctx.on.relation_broken(requirer_relation), state_in)

    assert len(state_out.deferred) == 1
    assert state_out.deferred[0].name == "karapace_relation_broken"


def test_relation_broken(
    ctx: Context,
    peer_relation_with_provider,
    kafka_relation,
    requirer_relation,
    patched_workload_write,
):
    secret = Secret(
        tracked_content={"relation-5000": "provider-password"}, label="cluster.karapace.app"
    )
    state_in = State(
        relations=[peer_relation_with_provider, kafka_relation, requirer_relation],
        leader=True,
        secrets=[secret],
    )
    with patch("workload.KarapaceWorkload.active", return_value=True):
        state_out = ctx.run(ctx.on.relation_broken(requirer_relation), state_in)

    patched_workload_write.assert_called_once()

    # Assert user gets removed from databag as well
    assert not state_out.get_relations("cluster")[0].local_app_data.get("relation-5000")
