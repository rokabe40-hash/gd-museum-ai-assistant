from museum_rag.evaluate import _metrics, calibrate_threshold


def test_metrics() -> None:
    metrics = _metrics(
        [
            {"answerable": True, "rank": 1, "predicted_insufficient": False},
            {"answerable": True, "rank": None, "predicted_insufficient": False},
            {"answerable": False, "rank": None, "predicted_insufficient": True},
        ]
    )

    assert metrics["recall_at_k"] == 0.5
    assert metrics["mrr"] == 0.5
    assert metrics["abstention_f1"] == 1.0


def test_calibrate_threshold_uses_dev_labels() -> None:
    threshold = calibrate_threshold(
        [
            {"answerable": True, "top_score": 0.8},
            {"answerable": True, "top_score": 0.7},
            {"answerable": False, "top_score": 0.2},
            {"answerable": False, "top_score": 0.1},
        ]
    )

    assert 0.2 < threshold < 0.7
