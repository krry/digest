from __future__ import annotations

import argparse
import datetime
import json
import sys

from digest.store import DigestStore, badge_for


def _store() -> DigestStore:
    store = DigestStore()
    store.ensure_ready()
    return store


def cmd_init(_args: argparse.Namespace) -> int:
    store = _store()
    store.export_json_mirror()
    print("initialized")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    print(_store().render_tree(show_all=args.show_all))
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    parent_id = None if args.parent_id == "null" else args.parent_id
    node = _store().add_node(args.type, parent_id, args.title)
    print(node["id"])
    return 0


def cmd_done(args: argparse.Namespace) -> int:
    query = " ".join(args.search_terms)
    matches = _store().find_active_matches(query)
    if not matches:
        print("NONE")
        return 1
    if len(matches) > 1:
        print("MATCHES:")
        for node in matches:
            print(f"  [{node['id']}] {badge_for(node['type'])}  {node['title']}")
        return 0
    node = _store().set_node_status(matches[0]["id"], "completed")
    print(f"DONE: {node['title']}")
    return 0


def cmd_write_values(args: argparse.Namespace) -> int:
    values = json.loads(sys.stdin.read())
    data = {
        "version": 1,
        "establishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "values": values,
    }
    _store().write_values_data(data)
    print(f"Saved {len(values)} value(s)")
    return 0


def cmd_checkin_status(args: argparse.Namespace) -> int:
    store = _store()
    if not args.force:
        last = store.recent_checkin_date()
        if last:
            today = datetime.date.today()
            days = (today - datetime.date.fromisoformat(last)).days
            if days < 20:
                print(f"RECENT: {last}")
                return 0
    print("READY")
    print("=== VALUES ===")
    values = store.load_values_data()["values"]
    if values:
        for item in values:
            print(f"• {item['phrase']} — {item.get('pinnedMoment')}")
    else:
        print("(none)")
    print("=== ACTIVE GOALS ===")
    active = store.active_nodes()
    if active:
        for node in active:
            print(f"[{node['type']}] {node['title']}")
    else:
        print("(none)")
    return 0


def cmd_log_checkin(args: argparse.Namespace) -> int:
    _store().append_checkin(
        {
            "date": args.date or datetime.date.today().isoformat(),
            "question": args.question,
            "response": args.response,
            "adjustment": args.adjustment,
        }
    )
    print("logged")
    return 0


def cmd_export_json(_args: argparse.Namespace) -> int:
    _store().export_json_mirror()
    print("exported")
    return 0


def cmd_bootstrap(_args: argparse.Namespace) -> int:
    print(json.dumps(_store().bootstrap_payload(), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="digest")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init")
    init_parser.set_defaults(func=cmd_init)

    show_parser = sub.add_parser("show")
    show_parser.add_argument("--all", action="store_true", dest="show_all")
    show_parser.set_defaults(func=cmd_show)

    add_parser = sub.add_parser("add")
    add_parser.add_argument("type")
    add_parser.add_argument("parent_id")
    add_parser.add_argument("title")
    add_parser.set_defaults(func=cmd_add)

    done_parser = sub.add_parser("done")
    done_parser.add_argument("search_terms", nargs="+")
    done_parser.set_defaults(func=cmd_done)

    values_parser = sub.add_parser("write-values")
    values_parser.set_defaults(func=cmd_write_values)

    checkin_parser = sub.add_parser("checkin-status")
    checkin_parser.add_argument("force", nargs="?", default="")
    checkin_parser.set_defaults(func=cmd_checkin_status)

    log_checkin_parser = sub.add_parser("log-checkin")
    log_checkin_parser.add_argument("--date", default="")
    log_checkin_parser.add_argument("--question", required=True)
    log_checkin_parser.add_argument("--response", required=True)
    log_checkin_parser.add_argument("--adjustment", required=True)
    log_checkin_parser.set_defaults(func=cmd_log_checkin)

    export_parser = sub.add_parser("export-json")
    export_parser.set_defaults(func=cmd_export_json)

    bootstrap_parser = sub.add_parser("bootstrap")
    bootstrap_parser.set_defaults(func=cmd_bootstrap)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
