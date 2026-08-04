from src.graph.references import extract_artifact_references, reference_excerpt


def test_extracts_local_references_and_resolution_keywords() -> None:
    result = extract_artifact_references(
        "Fixes #12, follows #13, and does not claim owner/other#14.",
        supports_resolution=True,
    )

    assert result.resolved == frozenset({12})
    assert result.referenced == frozenset({13})


def test_resolution_is_disabled_for_non_closing_artifacts() -> None:
    result = extract_artifact_references("Fixes #12", supports_resolution=False)

    assert result.resolved == frozenset()
    assert result.referenced == frozenset({12})
    assert "#12" in reference_excerpt("prefix Fixes #12 suffix", 12)
