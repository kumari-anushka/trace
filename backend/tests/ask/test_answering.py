import json
from unittest.mock import AsyncMock

import httpx
import pytest

from src.ask.answering import OpenAIAnswerProvider, verify_citations
from src.ask.models import AnswerClaim, AnswerDraft, RetrievalMode, RetrievedEvidence
from src.core.exceptions import OpenAIAPIError


def evidence(identifier: str = "doc:one") -> RetrievedEvidence:
    return RetrievedEvidence(
        id=identifier,
        title="Query workflow",
        content="The workflow verifies citations after answer generation.",
        score=0.5,
        modes=(RetrievalMode.VECTOR,),
        source_type="source_summary",
    )


def test_citation_verifier_removes_unknown_and_uncited_claims() -> None:
    draft = AnswerDraft(
        claims=(
            AnswerClaim("Supported", ("doc:one",)),
            AnswerClaim("Unknown", ("doc:missing",)),
            AnswerClaim("Uncited", ()),
        ),
        limitations=("Snapshot only.",),
    )

    verified = verify_citations(draft, (evidence(),))

    assert verified.claims == (AnswerClaim("Supported", ("doc:one",)),)
    assert verified.limitations == (
        "Snapshot only.",
        "2 unsupported claim(s) were removed by citation verification.",
    )


async def test_openai_answer_provider_uses_strict_grounded_schema() -> None:
    payload = {
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "claims": [
                                    {"text": "Citations are verified.", "citation_ids": ["doc:one"]}
                                ],
                                "limitations": ["Snapshot only."],
                            }
                        ),
                    }
                ],
            }
        ]
    }
    response = httpx.Response(200, json=payload, request=httpx.Request("POST", "https://api"))
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post.return_value = response
    provider = OpenAIAnswerProvider(
        http_client=client,
        api_key="test-key",
        model="gpt-5.6-sol",
        api_url="https://api.openai.com/v1",
        max_output_tokens=800,
        max_retries=0,
        max_retry_delay_seconds=1,
    )

    result = await provider.answer(question="How are citations checked?", evidence=(evidence(),))

    assert result.claims[0].citation_ids == ("doc:one",)
    request_body = client.post.call_args.kwargs["json"]
    assert request_body["store"] is False
    assert request_body["text"]["format"]["strict"] is True
    assert request_body["model"] == "gpt-5.6-sol"


async def test_openai_answer_provider_rejects_incomplete_output() -> None:
    response = httpx.Response(
        200,
        json={"status": "incomplete", "output": []},
        request=httpx.Request("POST", "https://api"),
    )
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post.return_value = response
    provider = OpenAIAnswerProvider(
        http_client=client,
        api_key="test-key",
        model="gpt-5.6-sol",
        api_url="https://api.openai.com/v1",
        max_output_tokens=800,
        max_retries=0,
        max_retry_delay_seconds=1,
    )

    with pytest.raises(OpenAIAPIError, match="incomplete"):
        await provider.answer(question="Question", evidence=(evidence(),))
