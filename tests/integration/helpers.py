#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import socket
from contextlib import closing
from pathlib import Path
from subprocess import PIPE, check_output

import yaml
from jubilant_adapters import JujuFixture

from literals import PORT

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./metadata.yaml").read_text())
APP_NAME = METADATA["name"]

KAFKA = "kafka"
ZOOKEEPER = "zookeeper"
TLS_CERTIFICATES_OPERATOR = "tls-certificates-operator"
DUMMY_NAME = "app"
SERIES = "noble"

CA_FILE = "/tmp/ca-cert.pem"


def get_admin_credentials(juju: JujuFixture, num_unit=0) -> str:
    """Use the charm action to retrieve the password for admin user.

    Return:
        String with the password stored on the peer relation databag.
    """
    action = juju.ext.model.units.get(f"{APP_NAME}/{num_unit}").run_action("get-password")
    password = action.wait()
    return password.results["password"]


def set_password(juju: JujuFixture, username="operator", password=None, num_unit=0) -> dict:
    """Use the charm action to start a password rotation."""
    params = {"username": username}
    if password:
        params["password"] = password

    action = juju.ext.model.units.get(f"{APP_NAME}/{num_unit}").run_action(
        "set-password", **params
    )
    password = action.wait()
    return password.results


def get_application_credentials(juju: JujuFixture, role="user") -> tuple[str, str]:
    action = juju.ext.model.units.get(f"{DUMMY_NAME}/0").run_action(
        "get-credentials", **{"username": role}
    )
    credentials = action.wait()
    return credentials.results["username"], credentials.results["password"]


def set_tls_private_key(juju: JujuFixture, key: str | None = None, num_unit=0):
    """Use the charm action to start a password rotation."""
    params = {"internal-key": key} if key else {}

    action = juju.ext.model.units.get(f"{APP_NAME}/{num_unit}").run_action(
        "set-tls-private-key", **params
    )
    return (action.wait()).results


def get_address(juju: JujuFixture, app_name=APP_NAME, unit_num=0) -> str:
    """Get the address for a unit."""
    status = juju.ext.model.get_status()  # noqa: F821
    address = status["applications"][app_name]["units"][f"{app_name}/{unit_num}"]["public-address"]
    return address


def check_socket(host: str, port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex((host, port)) == 0


def assert_list_schemas(juju: JujuFixture, expected_schemas: str = "[]", units: int = 1) -> None:
    """Assert schemas can be listed."""
    operator_password = get_admin_credentials(juju)
    for i in range(units):
        address = get_address(juju=juju, unit_num=i)
        command = " ".join(
            [
                "curl",
                "-u",
                f"operator:{operator_password}",
                "-X",
                "GET",
                f"http://{address}:{PORT}/subjects",
            ]
        )

        logger.info("Requesting schemas")
        result = check_output(command, stderr=PIPE, shell=True, universal_newlines=True)
        assert expected_schemas in result
