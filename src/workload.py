#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Karapace workload class and methods."""

import logging
import os
import re
import subprocess

from charms.operator_libs_linux.v1 import snap
from tenacity import retry, retry_if_result, stop_after_attempt, wait_fixed
from typing_extensions import override

from core.workload import WorkloadBase
from literals import CHARMED_KARAPACE_SNAP_REVISION, GROUP, SALT, SNAP_NAME, USER

logger = logging.getLogger(__name__)


class KarapaceWorkload(WorkloadBase):
    """Wrapper for performing common operations specific to the Karapace Snap."""

    SNAP_SERVICE = "daemon"

    def __init__(self) -> None:
        self.karapace = snap.SnapCache()[SNAP_NAME]

    @override
    def start(self) -> None:
        try:
            self.karapace.start(services=[self.SNAP_SERVICE])
        except snap.SnapError as e:
            logger.exception(str(e))

    @override
    def stop(self) -> None:
        try:
            self.karapace.stop(services=[self.SNAP_SERVICE])
        except snap.SnapError as e:
            logger.exception(str(e))

    @override
    def restart(self) -> None:
        try:
            self.karapace.restart(services=[self.SNAP_SERVICE])
        except snap.SnapError as e:
            logger.exception(str(e))

    @override
    def read(self, path: str) -> list[str]:
        if not os.path.exists(path):
            return []
        else:
            with open(path) as f:
                content = f.read().split("\n")

        return content

    @override
    def write(self, content: str, path: str, mode: str = "w") -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode) as f:
            f.write(content)

        self.exec(f"chown -R {USER}:{GROUP} {path}")

    @override
    def exec(
        self, command: str, env: dict[str, str] | None = None, working_dir: str | None = None
    ) -> str:
        try:
            output = subprocess.check_output(
                command,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                shell=True,
                cwd=working_dir,
            )
            logger.debug(f"{output=}")
            return output
        except subprocess.CalledProcessError as e:
            logger.debug(f"cmd failed - cmd={e.cmd}, stdout={e.stdout}, stderr={e.stderr}")
            raise e

    @retry(
        wait=wait_fixed(1),
        stop=stop_after_attempt(5),
        retry=retry_if_result(lambda result: result is False),
        retry_error_callback=lambda _: False,
    )
    @override
    def active(self) -> bool:
        try:
            return bool(self.karapace.services[self.SNAP_SERVICE]["active"])
        except KeyError:
            return False

    def install(self) -> bool:
        """Install charmed-karapace snap.

        Returns:
            True if successfully installed. False otherwise.
        """
        try:
            self.karapace.ensure(snap.SnapState.Present, revision=CHARMED_KARAPACE_SNAP_REVISION)
            self.karapace.hold()

            return True
        except (snap.SnapError) as e:
            logger.error(str(e))
            return False

    @override
    def get_version(self) -> str:
        if not self.active:
            return ""
        try:
            version = re.split(r"[\s\-]", self.exec(command=f"{SNAP_NAME}.version"))[0]
        except:  # noqa: E722
            version = ""
        return version

    @override
    def mkpasswd(self, username: str, password: str) -> str:
        return self.exec(command=f"{SNAP_NAME}.mkpasswd -u {username} -a sha512 {password} {SALT}")
