from evaluation.evaluate import confusion, metrics, recall_at_k, select_threshold


def test_metrics_and_confusion_matrix():
    result = metrics([1, 1, 0, 0], [0.9, 0.4, 0.7, 0.1], 0.5)
    assert result["confusion_matrix"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5


def test_threshold_is_selected_only_from_given_scores():
    result = select_threshold([1, 1, 0, 0], [0.91, 0.82, 0.61, 0.2])
    assert result["threshold"] == 0.82
    assert result["f1"] == 1.0


def test_recall_at_k_uses_relevant_sets():
    result = recall_at_k([["a", "b"], ["x", "c"]], [{"a"}, {"c"}], values=(1, 2))
    assert result == {"recall@1": 0.5, "recall@2": 1.0}
