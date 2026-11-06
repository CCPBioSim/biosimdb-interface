from biosimdb_interface.core.progress_state import ProgressReporter, read_progress


def test_reporter_round_trip(tmp_path):
    reporter = ProgressReporter(str(tmp_path))
    reporter.set_steps([{"id": "a", "label": "A"}])
    reporter.update("a", 0.5, "half")
    state = read_progress(str(tmp_path))
    assert state["steps"] == [{"id": "a", "label": "A"}]
    assert (state["current"], state["pct"], state["detail"]) == ("a", 0.5, "half")


def test_read_progress_missing(tmp_path):
    assert read_progress(str(tmp_path))["current"] is None
