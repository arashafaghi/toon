"""Behavior of the command/screen/widget registry."""

from __future__ import annotations

import pytest
from textual.screen import Screen
from textual.widget import Widget

from toon.api import Command, RegistrationError
from toon.runtime.registry import BarItem, Registry


def _command(name: str, description: str = "") -> Command:
    return Command(name, lambda ctx: None, description)


def _widget() -> Widget:
    return Widget()


def _screen() -> Screen[None]:
    return Screen()


@pytest.mark.parametrize("name", ["", "1cmd", "with space", "with.dot", "-dash", "cmd!"])
def test_invalid_names_are_rejected(name: str) -> None:
    registry = Registry()

    with pytest.raises(RegistrationError):
        registry.register_command(_command(name))
    with pytest.raises(RegistrationError):
        registry.register_screen(name, _screen)
    with pytest.raises(RegistrationError):
        registry.register_widget(name, _widget)
    with pytest.raises(RegistrationError):
        registry.register_header_item(name, _widget)
    with pytest.raises(RegistrationError):
        registry.register_footer_item(name, _widget)


def test_duplicate_registrations_raise() -> None:
    registry = Registry()
    registry.register_command(_command("go"))
    registry.register_screen("main", _screen)
    registry.register_widget("panel", _widget)
    registry.register_header_item("clock", _widget)
    registry.register_footer_item("status", _widget)

    with pytest.raises(RegistrationError):
        registry.register_command(_command("go"))
    with pytest.raises(RegistrationError):
        registry.register_screen("main", _screen)
    with pytest.raises(RegistrationError):
        registry.register_widget("panel", _widget)
    with pytest.raises(RegistrationError):
        registry.register_header_item("clock", _widget)
    with pytest.raises(RegistrationError):
        registry.register_footer_item("status", _widget)


def test_namespaces_are_independent() -> None:
    registry = Registry()
    registry.register_command(_command("shared"))
    registry.register_screen("shared", _screen)
    registry.register_widget("shared", _widget)

    assert [info.name for info in registry.command_infos()] == ["shared"]
    assert [info.name for info in registry.screen_infos()] == ["shared"]
    assert [info.name for info in registry.widget_infos()] == ["shared"]


def test_insertion_order_is_preserved_per_namespace() -> None:
    registry = Registry()
    for name in ("zeta", "alpha", "mid"):
        registry.register_command(_command(name))
        registry.register_screen(name, _screen)
        registry.register_widget(name, _widget)

    assert [info.name for info in registry.command_infos()] == ["zeta", "alpha", "mid"]
    assert [info.name for info in registry.screen_infos()] == ["zeta", "alpha", "mid"]
    assert [info.name for info in registry.widget_infos()] == ["zeta", "alpha", "mid"]


def test_command_infos_and_lookup() -> None:
    registry = Registry()
    go = _command("go", "Start moving.")
    registry.register_command(go)

    (info,) = registry.command_infos()
    assert (info.name, info.description) == ("go", "Start moving.")
    assert registry.get_command("go") is go
    assert registry.get_command("missing") is None
    assert registry.commands == (go,)


def test_widget_title_defaults_to_name_and_can_be_overridden() -> None:
    registry = Registry()
    registry.register_widget("plain", _widget, description="Plain.")
    registry.register_widget("fancy", _widget, description="Fancy.", title="Fancy Panel")

    plain, fancy = registry.widget_infos()
    assert (plain.name, plain.description, plain.title) == ("plain", "Plain.", "plain")
    assert (fancy.name, fancy.description, fancy.title) == ("fancy", "Fancy.", "Fancy Panel")

    _, plain_title = registry.create_view("plain")
    _, fancy_title = registry.create_view("fancy")
    assert (plain_title, fancy_title) == ("plain", "Fancy Panel")


def test_bar_items_are_ordered_by_order_then_insertion_and_carry_view() -> None:
    registry = Registry()
    registry.register_header_item("late", _widget, order=10, view="main")
    registry.register_header_item("first", _widget, order=-1)
    registry.register_header_item("second", _widget, order=0)
    registry.register_footer_item("hint", _widget, order=5, view="panel")

    header = registry.header_items()
    assert [item.name for item in header] == ["first", "second", "late"]
    assert header == (
        BarItem("first", _widget, None),
        BarItem("second", _widget, None),
        BarItem("late", _widget, "main"),
    )
    assert [item.name for item in registry.footer_items()] == ["hint"]
    assert registry.footer_items()[0].view == "panel"


def test_create_view_returns_a_fresh_widget_each_time() -> None:
    registry = Registry()
    registry.register_widget("panel", _widget)

    first, first_title = registry.create_view("panel")
    second, second_title = registry.create_view("panel")

    assert isinstance(first, Widget)
    assert first is not second
    assert first_title == second_title == "panel"


def test_create_screen_returns_a_fresh_screen_each_time() -> None:
    registry = Registry()
    registry.register_screen("main", _screen)

    first = registry.create_screen("main")
    second = registry.create_screen("main")

    assert isinstance(first, Screen)
    assert first is not second


def test_unknown_view_and_screen_names_raise_key_error() -> None:
    registry = Registry()

    with pytest.raises(KeyError):
        registry.create_view("missing")
    with pytest.raises(KeyError):
        registry.create_screen("missing")


def test_has_screen_and_has_widget_report_registration() -> None:
    registry = Registry()
    registry.register_screen("main", _screen)
    registry.register_widget("panel", _widget)

    assert registry.has_screen("main") is True
    assert registry.has_screen("panel") is False
    assert registry.has_widget("panel") is True
    assert registry.has_widget("main") is False
