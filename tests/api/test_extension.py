"""The frozen public extension API: results, data types, and protocols."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from toon.api import (
    Command,
    CommandContext,
    CommandResult,
    ExtensionRegistry,
    RegistrationError,
    ViewHost,
)
from toon.runtime.registry import Registry


def _noop(ctx: CommandContext) -> None:
    return None


def test_command_result_ok_reflects_the_error_field() -> None:
    assert CommandResult(command="echo", output="hi").ok is True
    assert CommandResult(command="echo").ok is True
    assert CommandResult(command="bad", error="boom").ok is False


def test_command_result_is_a_frozen_value_type() -> None:
    assert CommandResult(command="a", output="b") == CommandResult(command="a", output="b")
    assert CommandResult(command="a") != CommandResult(command="b")

    result = CommandResult(command="a")
    with pytest.raises(FrozenInstanceError):
        result.command = "b"  # type: ignore[misc]


def test_command_defaults_and_equality() -> None:
    command = Command("go", _noop)

    assert command.description == ""
    assert command == Command("go", _noop)
    assert command != Command("stop", _noop)


def test_command_context_carries_args_and_host(view_host: ViewHost) -> None:
    context = CommandContext(args=("a", "b"), host=view_host)

    assert context.args == ("a", "b")
    assert context.host is view_host


def test_registration_error_is_an_exception() -> None:
    assert issubclass(RegistrationError, Exception)

    with pytest.raises(RegistrationError, match="duplicate"):
        raise RegistrationError("duplicate name")


def test_view_host_protocol_matches_a_conforming_object(view_host: ViewHost) -> None:
    assert isinstance(view_host, ViewHost)
    assert isinstance(object(), ViewHost) is False


def test_extension_registry_protocol_matches_the_real_registry() -> None:
    assert isinstance(Registry(), ExtensionRegistry)
    assert isinstance(object(), ExtensionRegistry) is False


def test_commands_can_be_registered_through_the_protocol() -> None:
    concrete = Registry()
    registry: ExtensionRegistry = concrete

    registry.register_command(Command("via-protocol", _noop))

    assert concrete.get_command("via-protocol") is not None
