from mcrs.dashboard_paths import prediction_search_dir


def test_prediction_search_dir_matches_blindset_writer():
    assert prediction_search_dir("blindset_A") == "exp/inference/blindset_A"


def test_prediction_search_dir_matches_devset_writer():
    assert prediction_search_dir("devset") == "exp/inference/devset"
