"""Durable LangGraph workflow with a real review-and-resume boundary."""

from __future__ import annotations

import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from launchguard.config import Settings
from launchguard.connectors.fx import FxClient
from launchguard.connectors.shopify import DryRunPublisher, ShopifyGraphQLPublisher
from launchguard.models import (
    ApprovalDecision,
    Citation,
    ComplianceFinding,
    DeliveryReceipt,
    FxQuote,
    ListingDraft,
    PricingDecision,
    RunEvent,
    SkuEvidence,
)
from launchguard.services.compliance import ComplianceEngine, has_blockers
from launchguard.services.generation import (
    DeterministicListingGenerator,
    ListingGenerator,
    OpenAICompatibleListingGenerator,
)
from launchguard.services.policies import PolicyIndex
from launchguard.services.pricing import PricingEngine
from launchguard.store import RunStore


class LaunchState(TypedDict, total=False):
    run_id: str
    status: str
    sku: Dict[str, Any]
    fx: Dict[str, Any]
    citations: List[Dict[str, Any]]
    pricing: Dict[str, Any]
    listing: Dict[str, Any]
    findings: List[Dict[str, Any]]
    approval: Dict[str, Any]
    delivery: Dict[str, Any]
    error: str


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


class LaunchWorkflow:
    def __init__(
        self,
        settings: Settings,
        store: Optional[RunStore] = None,
        fx_client: Optional[FxClient] = None,
        policy_index: Optional[PolicyIndex] = None,
        generator: Optional[ListingGenerator] = None,
    ) -> None:
        self.settings = settings
        self.settings.ensure_directories()
        self.store = store or RunStore(settings.database_path)
        self.fx_client = fx_client or FxClient(mode=settings.fx_mode)
        policy_database = settings.database_path.with_name("policies.sqlite")
        self.policy_index = policy_index or PolicyIndex(policy_database)
        self.policy_index.rebuild(settings.policy_dir)
        self.pricing_engine = PricingEngine()
        self.compliance_engine = ComplianceEngine()
        self.generator = generator or self._build_generator()
        self.publisher = self._build_publisher()
        self.checkpoint_connection = sqlite3.connect(
            str(settings.checkpoint_path), check_same_thread=False
        )
        self.checkpointer = SqliteSaver(self.checkpoint_connection)
        self.graph = self._build_graph()

    def _build_generator(self) -> ListingGenerator:
        if self.settings.generator == "deterministic":
            return DeterministicListingGenerator()
        if self.settings.generator == "openai-compatible":
            return OpenAICompatibleListingGenerator(
                base_url=self.settings.llm_base_url,
                api_key=self.settings.llm_api_key,
                model=self.settings.llm_model,
            )
        raise ValueError(f"Unsupported generator mode: {self.settings.generator}")

    def _build_publisher(self) -> Any:
        if self.settings.shopify_mode == "dry-run":
            return DryRunPublisher(self.store)
        if self.settings.shopify_mode == "live":
            return ShopifyGraphQLPublisher(
                store=self.store,
                shop=self.settings.shopify_store,
                token=self.settings.shopify_token,
                api_version=self.settings.shopify_api_version,
            )
        raise ValueError(f"Unsupported Shopify mode: {self.settings.shopify_mode}")

    def _record(
        self,
        run_id: str,
        node: str,
        started: float,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.store.add_event(
            run_id,
            RunEvent(
                node=node,
                status="completed",
                duration_ms=_elapsed_ms(started),
                detail=detail or {},
            ),
        )

    def _build_graph(self) -> Any:
        def validate_node(state: LaunchState) -> LaunchState:
            started = time.perf_counter()
            sku = SkuEvidence.model_validate(state["sku"])
            self._record(state["run_id"], "validate_evidence", started, {"sku": sku.sku})
            return {"sku": sku.model_dump(mode="json"), "status": "running"}

        def fx_node(state: LaunchState) -> LaunchState:
            started = time.perf_counter()
            sku = SkuEvidence.model_validate(state["sku"])
            quote = self.fx_client.quote(sku.source_currency, sku.target_currency)
            self._record(
                state["run_id"],
                "resolve_fx",
                started,
                {"provider": quote.provider, "mode": quote.mode},
            )
            return {"fx": quote.model_dump(mode="json")}

        def retrieve_node(state: LaunchState) -> LaunchState:
            started = time.perf_counter()
            sku = SkuEvidence.model_validate(state["sku"])
            query = (
                f"{sku.title} {sku.description} pricing claims returns shipping "
                "marketplace compliance product launch"
            )
            citations = self.policy_index.search(query, sku.market, limit=6)
            self._record(
                state["run_id"],
                "retrieve_policies",
                started,
                {"citations": len(citations)},
            )
            return {"citations": [item.model_dump(mode="json") for item in citations]}

        def pricing_node(state: LaunchState) -> LaunchState:
            started = time.perf_counter()
            sku = SkuEvidence.model_validate(state["sku"])
            fx = FxQuote.model_validate(state["fx"])
            pricing = self.pricing_engine.price(sku, fx)
            self._record(
                state["run_id"],
                "calculate_pricing",
                started,
                {
                    "minimum_price": str(pricing.minimum_price),
                    "recommended_price": str(pricing.recommended_price),
                    "scenarios": len(pricing.scenarios),
                },
            )
            return {"pricing": pricing.model_dump(mode="json")}

        def generation_node(state: LaunchState) -> LaunchState:
            started = time.perf_counter()
            sku = SkuEvidence.model_validate(state["sku"])
            pricing = PricingDecision.model_validate(state["pricing"])
            citations = [Citation.model_validate(item) for item in state["citations"]]
            listing = self.generator.generate(sku, pricing, citations)
            self._record(
                state["run_id"],
                "generate_listing",
                started,
                {"generator": listing.generator},
            )
            return {"listing": listing.model_dump(mode="json")}

        def compliance_node(state: LaunchState) -> LaunchState:
            started = time.perf_counter()
            sku = SkuEvidence.model_validate(state["sku"])
            fx = FxQuote.model_validate(state["fx"])
            pricing = PricingDecision.model_validate(state["pricing"])
            listing = ListingDraft.model_validate(state["listing"])
            citations = [Citation.model_validate(item) for item in state["citations"]]
            findings = self.compliance_engine.evaluate(
                sku, fx, pricing, listing, citations
            )
            blockers = sum(item.severity == "blocker" for item in findings)
            self._record(
                state["run_id"],
                "run_compliance",
                started,
                {"findings": len(findings), "blockers": blockers},
            )
            return {"findings": [item.model_dump(mode="json") for item in findings]}

        def compliance_route(state: LaunchState) -> str:
            findings = [ComplianceFinding.model_validate(item) for item in state["findings"]]
            return "blocked" if has_blockers(findings) else "approval"

        def blocked_node(state: LaunchState) -> LaunchState:
            started = time.perf_counter()
            receipt = DeliveryReceipt(
                mode="skipped",
                status="blocked",
                run_id=state["run_id"],
                idempotency_key=state["run_id"],
                detail="Compliance blockers prevented human approval and external delivery.",
            )
            self._record(state["run_id"], "block_delivery", started)
            return {
                "status": "blocked",
                "delivery": receipt.model_dump(mode="json"),
            }

        def approval_node(state: LaunchState) -> LaunchState:
            payload = {
                "instruction": "Review the evidence, economics, listing, and findings.",
                "run_id": state["run_id"],
                "sku": state["sku"],
                "fx": state["fx"],
                "pricing": state["pricing"],
                "listing": state["listing"],
                "findings": state["findings"],
                "citations": state["citations"],
                "allowed_actions": ["approve", "reject"],
            }
            raw_decision = interrupt(payload)
            started = time.perf_counter()
            decision = ApprovalDecision.model_validate(raw_decision)
            listing = ListingDraft.model_validate(state["listing"])
            updates: Dict[str, Any] = {}
            if decision.edited_title:
                updates["title"] = decision.edited_title
            if decision.edited_description_html:
                updates["description_html"] = decision.edited_description_html
            if updates:
                listing = listing.model_copy(update=updates)
            decision_json = decision.model_dump(mode="json")
            self.store.save_approval(state["run_id"], decision_json)
            self._record(
                state["run_id"],
                "human_approval",
                started,
                {"action": decision.action, "reviewer": decision.reviewer},
            )
            return {
                "approval": decision_json,
                "listing": listing.model_dump(mode="json"),
                "status": "approved" if decision.action == "approve" else "rejected",
            }

        def approval_route(state: LaunchState) -> str:
            return "publish" if state["approval"]["action"] == "approve" else "reject"

        def reject_node(state: LaunchState) -> LaunchState:
            started = time.perf_counter()
            receipt = DeliveryReceipt(
                mode="skipped",
                status="rejected",
                run_id=state["run_id"],
                idempotency_key=state["run_id"],
                detail="The reviewer rejected the launch package.",
            )
            self._record(state["run_id"], "reject_delivery", started)
            return {"status": "rejected", "delivery": receipt.model_dump(mode="json")}

        def publish_node(state: LaunchState) -> LaunchState:
            started = time.perf_counter()
            sku = SkuEvidence.model_validate(state["sku"])
            listing = ListingDraft.model_validate(state["listing"])
            receipt = self.publisher.publish(state["run_id"], sku, listing)
            self._record(
                state["run_id"],
                "deliver_shopify_draft",
                started,
                {"mode": receipt.mode, "status": receipt.status},
            )
            return {"status": "completed", "delivery": receipt.model_dump(mode="json")}

        builder = StateGraph(LaunchState)
        builder.add_node("validate_evidence", validate_node)
        builder.add_node("resolve_fx", fx_node)
        builder.add_node("retrieve_policies", retrieve_node)
        builder.add_node("calculate_pricing", pricing_node)
        builder.add_node("generate_listing", generation_node)
        builder.add_node("run_compliance", compliance_node)
        builder.add_node("approval", approval_node)
        builder.add_node("blocked", blocked_node)
        builder.add_node("reject", reject_node)
        builder.add_node("publish", publish_node)

        builder.add_edge(START, "validate_evidence")
        builder.add_edge("validate_evidence", "resolve_fx")
        builder.add_edge("resolve_fx", "retrieve_policies")
        builder.add_edge("retrieve_policies", "calculate_pricing")
        builder.add_edge("calculate_pricing", "generate_listing")
        builder.add_edge("generate_listing", "run_compliance")
        builder.add_conditional_edges(
            "run_compliance",
            compliance_route,
            {"blocked": "blocked", "approval": "approval"},
        )
        builder.add_conditional_edges(
            "approval",
            approval_route,
            {"publish": "publish", "reject": "reject"},
        )
        builder.add_edge("blocked", END)
        builder.add_edge("reject", END)
        builder.add_edge("publish", END)
        return builder.compile(checkpointer=self.checkpointer)

    @staticmethod
    def _clean_state(result: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in result.items() if not key.startswith("__")}

    @staticmethod
    def _interrupt_payload(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        interrupts = result.get("__interrupt__", ())
        if not interrupts:
            return None
        value = getattr(interrupts[0], "value", None)
        return value if isinstance(value, dict) else {"value": value}

    def start(self, sku: SkuEvidence, run_id: Optional[str] = None) -> Dict[str, Any]:
        run_id = run_id or f"lg_{uuid.uuid4().hex}"
        initial: LaunchState = {
            "run_id": run_id,
            "status": "running",
            "sku": sku.model_dump(mode="json"),
        }
        self.store.create_run(run_id, sku.sku, dict(initial))
        config = {"configurable": {"thread_id": run_id}}
        try:
            result = self.graph.invoke(initial, config=config)
            clean = self._clean_state(result)
            pending = self._interrupt_payload(result)
            status = clean.get("status", "running")
            if pending:
                status = "pending_approval"
                clean["status"] = status
                self.store.add_event(
                    run_id,
                    RunEvent(
                        node="human_approval",
                        status="paused",
                        detail={"reason": "review_required"},
                    ),
                )
            self.store.update_run(run_id, status, clean)
            return {"run": clean, "interrupt": pending, "events": self.store.events(run_id)}
        except Exception as exc:
            failed = dict(initial)
            failed.update({"status": "failed", "error": str(exc)})
            self.store.update_run(run_id, "failed", failed)
            raise

    def resume(self, run_id: str, decision: ApprovalDecision) -> Dict[str, Any]:
        record = self.store.get_run(run_id)
        if record is None:
            raise KeyError(f"Unknown run: {run_id}")
        if record.status != "pending_approval":
            raise ValueError(
                f"Run {run_id} is {record.status}; only pending_approval can be resumed"
            )
        config = {"configurable": {"thread_id": run_id}}
        self.store.add_event(
            run_id,
            RunEvent(
                node="human_approval",
                status="resumed",
                detail={"reviewer": decision.reviewer},
            ),
        )
        try:
            result = self.graph.invoke(
                Command(resume=decision.model_dump(mode="json")), config=config
            )
            clean = self._clean_state(result)
            status = clean.get("status", "completed")
            self.store.update_run(run_id, status, clean)
            return {"run": clean, "interrupt": None, "events": self.store.events(run_id)}
        except Exception as exc:
            failed = dict(record.state)
            failed.update({"status": "failed", "error": str(exc)})
            self.store.update_run(run_id, "failed", failed)
            raise

    def get(self, run_id: str) -> Dict[str, Any]:
        record = self.store.get_run(run_id)
        if record is None:
            raise KeyError(f"Unknown run: {run_id}")
        return {"run": record.model_dump(mode="json"), "events": self.store.events(run_id)}

    def list(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [record.model_dump(mode="json") for record in self.store.list_runs(limit)]

    def close(self) -> None:
        self.policy_index.close()
        self.checkpoint_connection.close()
        self.store.close()


def build_workflow(settings: Optional[Settings] = None) -> LaunchWorkflow:
    return LaunchWorkflow(settings or Settings.from_env())
