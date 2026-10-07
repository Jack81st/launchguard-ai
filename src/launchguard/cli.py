"""Command-line interface for local operation and automation."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional, Sequence

import uvicorn

from launchguard.config import Settings
from launchguard.connectors.catalog import load_sku
from launchguard.evaluation import run_evaluation
from launchguard.models import ApprovalDecision


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="launchguard",
        description="Run durable, reviewed product-launch workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Start the API and web control room")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)

    start = subparsers.add_parser("start", help="Start a launch and pause for review")
    start.add_argument("--catalog", type=Path, required=True)
    start.add_argument("--sku", required=True)
    start.add_argument("--offline", action="store_true")

    decide = subparsers.add_parser("decide", help="Approve or reject a paused launch")
    decide.add_argument("--run-id", required=True)
    decide.add_argument("--action", choices=["approve", "reject"], required=True)
    decide.add_argument("--reviewer", required=True)
    decide.add_argument("--note", default="")
    decide.add_argument("--title")
    decide.add_argument("--description-html")

    show = subparsers.add_parser("show", help="Show one run and its audit events")
    show.add_argument("--run-id", required=True)

    subparsers.add_parser("list", help="List recent launch runs")

    evaluate = subparsers.add_parser("eval", help="Run the bundled quality evaluation")
    evaluate.add_argument("--cases", type=Path, default=Path("evals/cases.json"))

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    if args.command == "serve":
        uvicorn.run(
            "launchguard.api:create_app",
            host=args.host,
            port=args.port,
            reload=False,
            factory=True,
        )
        return 0
    if args.command == "eval":
        result = run_evaluation(settings.policy_dir, args.cases)
        _print(result)
        return 0 if result["passed"] else 1
    if getattr(args, "offline", False):
        settings = replace(settings, fx_mode="offline")

    from launchguard.workflow import LaunchWorkflow

    workflow = LaunchWorkflow(settings)
    try:
        if args.command == "start":
            result = workflow.start(load_sku(args.catalog, args.sku))
        elif args.command == "decide":
            decision = ApprovalDecision(
                action=args.action,
                reviewer=args.reviewer,
                note=args.note,
                edited_title=args.title,
                edited_description_html=args.description_html,
            )
            result = workflow.resume(args.run_id, decision)
        elif args.command == "show":
            result = workflow.get(args.run_id)
        elif args.command == "list":
            result = workflow.list()
        else:
            raise AssertionError(f"Unhandled command: {args.command}")
        _print(result)
        return 0
    finally:
        workflow.close()


if __name__ == "__main__":
    raise SystemExit(main())
