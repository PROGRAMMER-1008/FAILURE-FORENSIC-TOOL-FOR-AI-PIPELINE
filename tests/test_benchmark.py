from ffv2.benchmark import fixtures, scores, category_macro_f1
from ffv2.diagnosis import analyze


def test_all_injected_cases_and_family_isolation():
    cases = list(fixtures())
    assert len(cases) >= 60
    families = {}
    for case in cases:
        families.setdefault(case["family"], set()).add(case["split"])
        result = analyze(case["run"])
        if case["ambiguous"]:
            assert result.abstention_reason
        else:
            assert set(result.origins) == set(case["expected"]), case["id"]
    assert all(len(splits) == 1 for splits in families.values())


def test_multi_origin_scorer():
    assert scores({"a", "b"}, {"a", "c"}) == {"exact": 0, "precision": 0.5, "recall": 0.5}
    assert scores(set(), set())["exact"] == 1
    assert (
        category_macro_f1([{"expected_categories": ["a", "b"], "predicted_categories": ["a", "c"]}])
        == 1 / 3
    )
