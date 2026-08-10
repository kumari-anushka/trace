from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.ask.models import QueryResult, RetrievalMode


class RepositoryQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=2000)


class QueryClaimResponse(BaseModel):
    text: str
    citation_ids: list[str]


class QueryCitationResponse(BaseModel):
    id: str
    title: str
    source_type: str
    source_url: str | None
    excerpt: str
    retrieval_modes: list[RetrievalMode]


class RepositoryQueryResponse(BaseModel):
    repository_id: UUID
    repository_version_id: UUID
    question: str
    answer: str
    claims: list[QueryClaimResponse]
    citations: list[QueryCitationResponse]
    limitations: list[str]
    retrieval_modes: list[RetrievalMode]
    grounded: bool

    @classmethod
    def from_result(cls, result: QueryResult) -> "RepositoryQueryResponse":
        return cls(
            repository_id=result.repository_id,
            repository_version_id=result.repository_version_id,
            question=result.question,
            answer=result.answer,
            claims=[
                QueryClaimResponse(text=claim.text, citation_ids=list(claim.citation_ids))
                for claim in result.claims
            ],
            citations=[
                QueryCitationResponse(
                    id=item.id,
                    title=item.title,
                    source_type=item.source_type,
                    source_url=item.source_url,
                    excerpt=item.content[:600],
                    retrieval_modes=list(item.modes),
                )
                for item in result.citations
            ],
            limitations=list(result.limitations),
            retrieval_modes=list(result.retrieval_modes),
            grounded=result.grounded,
        )
