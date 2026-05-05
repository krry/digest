from __future__ import annotations

import argparse
import json
import mimetypes
import pathlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from digest.store import DigestStore

store = DigestStore()
WEB_ROOT = pathlib.Path(__file__).resolve().parent.parent / "web"


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, indent=2).encode("utf-8")


def _serve_web_path(path: str) -> pathlib.Path | None:
    mapping = {
        "/": "index.html",
        "/styles.css": "styles.css",
        "/app.js": "app.js",
        "/db.js": "db.js",
        "/sw.js": "sw.js",
        "/manifest.webmanifest": "manifest.webmanifest",
    }
    filename = mapping.get(path)
    if not filename:
        return None
    target = WEB_ROOT / filename
    return target if target.exists() else None


def _child_type(parent_id: str) -> str:
    node = store.get_node(parent_id)
    if not node:
        raise KeyError("Parent not found")
    return {
        "goal": "idea",
        "idea": "step",
        "step": "task",
        "task": "free",
        "free": "free",
    }[node["type"]]


class DigestHandler(BaseHTTPRequestHandler):
    server_version = "DigestHTTP/0.1"

    def do_GET(self):
        store.ensure_ready()
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            return self._send_json({"ok": True})
        if parsed.path == "/api/v1/bootstrap":
            return self._send_json(store.bootstrap_payload())
        if parsed.path == "/api/v1/nodes":
            return self._send_json(store.load_goals_data())
        if parsed.path == "/api/v1/values":
            return self._send_json(store.load_values_data())
        if parsed.path == "/api/v1/checkins":
            return self._send_json(store.load_checkins_data())
        if parsed.path == "/api/v1/export/json":
            return self._send_json(
                {
                    "goals": store.load_goals_data(),
                    "values": store.load_values_data(),
                    "checkins": store.load_checkins_data(),
                }
            )
        if parsed.path == "/api/v1/sync":
            params = parse_qs(parsed.query)
            return self._send_json(
                {
                    "cursor": store.bootstrap_payload()["serverTime"],
                    "requestedSince": params.get("since", [None])[0],
                    "changes": [],
                }
            )

        asset = _serve_web_path(parsed.path)
        if asset:
            return self._send_file(asset)
        return self._send_json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self):
        store.ensure_ready()
        parsed = urlparse(self.path)
        payload = self._read_json_body()

        try:
            if parsed.path == "/api/v1/commands/add-child":
                parent_id = payload.get("parentId")
                node = store.add_node(
                    "goal" if parent_id is None else _child_type(parent_id),
                    parent_id,
                    payload["title"],
                    node_id=payload.get("nodeId"),
                )
                return self._send_json({"ok": True, "node": node})

            if parsed.path == "/api/v1/commands/add-sibling":
                sibling = store.get_node(payload.get("nodeId")) if payload.get("nodeId") else None
                node_type = sibling["type"] if sibling else "goal"
                parent_id = sibling["parentId"] if sibling else None
                node = store.add_node(
                    node_type,
                    parent_id,
                    payload["title"],
                    node_id=payload.get("newNodeId"),
                )
                return self._send_json({"ok": True, "node": node})

            if parsed.path == "/api/v1/commands/rename-node":
                node = store.rename_node(payload["nodeId"], payload["title"])
                if not node:
                    return self._send_json({"ok": False, "error": "Node not found"}, status=HTTPStatus.NOT_FOUND)
                return self._send_json({"ok": True, "node": node})

            if parsed.path == "/api/v1/commands/complete-node":
                node = store.set_node_status(payload["nodeId"], "completed")
                if not node:
                    return self._send_json({"ok": False, "error": "Node not found"}, status=HTTPStatus.NOT_FOUND)
                return self._send_json({"ok": True, "node": node})

            if parsed.path == "/api/v1/commands/archive-node":
                node = store.set_node_status(payload["nodeId"], "archived")
                if not node:
                    return self._send_json({"ok": False, "error": "Node not found"}, status=HTTPStatus.NOT_FOUND)
                return self._send_json({"ok": True, "node": node})

            if parsed.path == "/api/v1/commands/update-values":
                store.write_values_data(
                    {
                        "version": 1,
                        "establishedAt": payload.get("establishedAt"),
                        "values": payload.get("values", []),
                    }
                )
                return self._send_json({"ok": True, "values": store.load_values_data()})

            if parsed.path == "/api/v1/commands/add-checkin":
                store.append_checkin(payload)
                return self._send_json({"ok": True})

            if parsed.path == "/api/v1/sync/push":
                accepted = [mutation.get("clientMutationId") for mutation in payload.get("mutations", [])]
                return self._send_json(
                    {
                        "ok": True,
                        "acceptedMutationIds": accepted,
                        "rejectedMutations": [],
                    }
                )
        except KeyError as exc:
            return self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            return self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        return self._send_json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args):
        return

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK):
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: pathlib.Path):
        body = path.read_bytes()
        media_type, _encoding = mimetypes.guess_type(str(path))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", media_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="digest.api")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8787, type=int)
    return parser


def run_server(host: str = "127.0.0.1", port: int = 8787):
    store.ensure_ready()
    server = ThreadingHTTPServer((host, port), DigestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None):
    args = build_parser().parse_args(argv)
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
