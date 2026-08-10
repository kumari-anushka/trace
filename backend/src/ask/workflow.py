from __future__ import annotations

from collections.abc import Sequence
from typing import NotRequired, TypedDict, cast
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from src.ask.answering import AnswerProvider, verify_citations
from src.ask.models import AnswerDraft, QueryPlan, QueryResult, RetrievedEvidence
from src.ask.retrieval import AdaptiveQueryPlanner, HybridRetriever


class AskState(TypedDict):
    repository_id: UUID
    repository_version_id: UUID
    question: str
    plan: NotRequired[QueryPlan]
    evidence: NotRequired[tuple[RetrievedEvidence, ...]]
    draft: NotRequired[AnswerDraft]
    verified: NotRequired[AnswerDraft]


class AskWorkflow:
    def __init__(
        self,
        *,
        planner: AdaptiveQueryPlanner,
        retriever: HybridRetriever,
        answer_provider: AnswerProvider,
    ) -> None:
        self.planner = planner
        self.retriever = retriever
        self.answer_provider = answer_provider
        graph = StateGraph(AskState)
        graph.add_node("plan", self._plan)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("answer", self._answer)
        graph.add_node("verify", self._verify)
        graph.add_edge(START, "plan")
        graph.add_edge("plan", "retrieve")
        graph.add_edge("retrieve", "answer")
        graph.add_edge("answer", "verify")
        graph.add_edge("verify", END)
        self.graph = graph.compile()

    async def run(
        self, *, repository_id: UUID, repository_version_id: UUID, question: str
    ) -> QueryResult:
        state = cast(
            AskState,
            await self.graph.ainvoke(
                AskState(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    question=question,
                )
            ),
        )
        plan = state["plan"]
        evidence = state.get("evidence", ())
        verified = state["verified"]
        cited_ids = {citation_id for claim in verified.claims for citation_id in claim.citation_ids}
        citations = tuple(item for item in evidence if item.id in cited_ids)
        answer = "\n\n".join(claim.text for claim in verified.claims)
        if not answer:
            answer = (
                "The current snapshot does not contain enough cited evidence "
                "to answer this question."
            )
        return QueryResult(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            question=question,
            answer=answer,
            claims=verified.claims,
            citations=citations,
            limitations=verified.limitations,
            retrieval_modes=plan.modes,
            grounded=bool(verified.claims),
        )

    async def _plan(self, state: AskState) -> dict[str, QueryPlan]:
        return {"plan": self.planner.plan(state["question"])}

    async def _retrieve(self, state: AskState) -> dict[str, tuple[RetrievedEvidence, ...]]:
        evidence = await self.retriever.retrieve(
            repository_id=state["repository_id"],
            repository_version_id=state["repository_version_id"],
            question=state["question"],
            plan=state["plan"],
        )
        return {"evidence": evidence}

    async def _answer(self, state: AskState) -> dict[str, AnswerDraft]:
        return {
            "draft": await self.answer_provider.answer(
                question=state["question"], evidence=state.get("evidence", ())
            )
        }

    async def _verify(self, state: AskState) -> dict[str, AnswerDraft]:
        return {"verified": verify_citations(state["draft"], state.get("evidence", ()))}


def cited_evidence(
    evidence: Sequence[RetrievedEvidence], citation_ids: Sequence[str]
) -> tuple[RetrievedEvidence, ...]:
    selected = set(citation_ids)
    return tuple(item for item in evidence if item.id in selected)
