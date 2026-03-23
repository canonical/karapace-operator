#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import json
from pathlib import Path

import pytest
from jubilant_adapters import JujuFixture, temp_model_fixture


def pytest_addoption(parser):
    """Defines pytest parsers."""
    parser.addoption(
        "--model",
        action="store",
        help="Juju model to use; if not provided, a new model "
        "will be created for each test which requires one",
    )
    parser.addoption(
        "--keep-models",
        action="store_true",
        help="Keep models handled by opstest, can be overridden in track_model",
    )


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest):
    """Pytest fixture that wraps :meth:`jubilant.with_model`.

    This adds command line parameter ``--keep-models`` (see help for details).
    """
    model = request.config.getoption("--model")
    keep_models = bool(request.config.getoption("--keep-models"))

    if model:
        juju = JujuFixture(model=model)
        yield juju
    else:
        with temp_model_fixture(keep=keep_models) as juju:
            yield juju


@pytest.fixture(scope="module", autouse=True)
def setup_juju(juju: JujuFixture):
    if not juju.model:
        return

    juju.wait_timeout = 600.0
    juju.cli("switch", juju.model, include_model=False)


@pytest.fixture(scope="module")
def karapace_charm(juju: JujuFixture) -> Path:
    """Kafka charm used for integration testing."""
    charm = juju.ext.build_charm(".")
    return charm


@pytest.fixture(scope="module")
def app_charm(juju: JujuFixture) -> Path:
    """Build the application charm."""
    charm_path = "tests/integration/app-charm"
    charm = juju.ext.build_charm(charm_path)
    return charm


@pytest.fixture(scope="module")
def model_uuid(juju: JujuFixture) -> str:
    ret, models_raw, _ = juju.juju("models", "--format", "json")
    assert not ret
    return next(
        iter(
            mdl["model-uuid"]
            for mdl in json.loads(models_raw)["models"]
            if mdl["short-name"] == juju.model
        )
    )
