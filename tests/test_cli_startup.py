import pytest
from pwnpet_cli.cli import build_parser


class TestCliStartup:
    def test_parser_builds(self):
        parser = build_parser()
        assert parser is not None

    def test_subcommands_registered(self):
        parser = build_parser()
        expected = [
            "session",
            "scan",
            "target",
            "status",
            "read",
            "write",
            "feed",
            "pet",
            "play",
            "passkey",
            "rename",
            "owner",
            "missions",
            "flag",
            "oled",
            "addon",
            "clock",
        ]
        subparsers_action = [a for a in parser._actions if a.dest == "cmd"][0]
        for cmd in expected:
            assert cmd in subparsers_action.choices

    def test_addon_subcommand_args(self):
        parser = build_parser()
        args = parser.parse_args(["addon", "anim", "3"])
        assert args.cmd == "addon"
        assert args.addon_cmd == "anim"
        assert args.mode == 3

        args = parser.parse_args(["addon", "set", "eyes", "1"])
        assert args.addon_cmd == "set"
        assert args.led == "eyes"
        assert args.state == 1

        args = parser.parse_args(["addon", "blink", "all", "5"])
        assert args.addon_cmd == "blink"
        assert args.led == "all"
        assert args.period == 5

        args = parser.parse_args(["addon", "off"])
        assert args.addon_cmd == "off"

        args = parser.parse_args(["addon", "ping"])
        assert args.addon_cmd == "ping"

    def test_feed_args(self):
        parser = build_parser()
        args = parser.parse_args(["feed", "100"])
        assert args.cmd == "feed"
        assert args.amount == 100

    def test_owner_args(self):
        parser = build_parser()
        args = parser.parse_args(["owner", "Alice"])
        assert args.cmd == "owner"
        assert args.name == "Alice"
