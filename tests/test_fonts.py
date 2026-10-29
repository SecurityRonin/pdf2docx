"""Font matching: use the source font, else a metric-compatible clone, else the
closest installed face with size and tracking tuned to the measured widths."""
import pytest

from pdf2docx import fonts


def _first_installed():
    table = fonts.installed()
    if not table:
        pytest.skip("no usable fonts on this machine")
    return next(iter(table.items()))


def test_installed_fonts_have_readable_metrics():
    family, path = _first_installed()
    assert path.exists()
    meta = fonts.metrics(path)
    assert meta.units_per_em > 0
    assert meta.average_width > 0


def test_width_measures_a_string_in_points():
    family, path = _first_installed()
    w = fonts.text_width(path, "Hello world", 12.0)
    assert 20 < w < 400, w


def test_width_grows_with_size():
    family, path = _first_installed()
    a = fonts.text_width(path, "Hello world", 10.0)
    b = fonts.text_width(path, "Hello world", 20.0)
    assert b == pytest.approx(a * 2, rel=0.02)


def test_metric_compatible_clone_is_known_for_calibri():
    """Calibri is proprietary and must never be downloaded; Carlito is its
    metric-compatible open clone and is the legal substitute."""
    assert fonts.substitute_for("Calibri") == "Carlito"
    assert fonts.substitute_for("Arial") == "Liberation Sans"
    assert fonts.substitute_for("Times New Roman") == "Liberation Serif"
    assert fonts.substitute_for("Corbel") is None      # no clone known


def test_closest_falls_back_to_an_installed_face():
    family, path = _first_installed()
    pick = fonts.closest("Calibri", [family])
    assert pick == family


def test_plan_closes_the_width_gap_by_tracking():
    """Tracking is the small correction; it must reproduce the target width."""
    family, path = _first_installed()
    text = "The quick brown fox jumps over the lazy dog"
    natural = fonts.text_width(path, text, 11.0)
    target = natural * 1.03

    plan = fonts.plan(path, text, 11.0, target)
    achieved = fonts.text_width(path, text, 11.0 * plan.size_scale) + plan.tracking_pt * (len(text) - 1)
    assert achieved == pytest.approx(target, abs=1.0)


def test_plan_never_asks_for_absurd_tracking():
    family, path = _first_installed()
    text = "short"
    target = fonts.text_width(path, text, 11.0) * 1.5   # far too wide to fix by tracking
    plan = fonts.plan(path, text, 11.0, target)
    assert abs(plan.tracking_pt) <= fonts.MAX_TRACKING_PT
    assert 0.7 <= plan.size_scale <= 1.4               # size takes the rest


def test_fetch_refuses_a_font_whose_hash_does_not_match(tmp_path, monkeypatch):
    """An unverified font binary is arbitrary code the renderer will load."""
    src = tmp_path / "clone.ttf"
    src.write_bytes(b"not really a font")
    monkeypatch.setitem(fonts.CLONE_SOURCES, "Carlito",
                        {"url": src.as_uri(), "sha256": "0" * 64})
    with pytest.raises(ValueError, match="failed verification"):
        fonts.fetch_substitute("Calibri", tmp_path / "dest")
    assert not (tmp_path / "dest" / "Carlito.ttf").exists()


def test_fetch_accepts_a_matching_hash(tmp_path, monkeypatch):
    import hashlib
    src = tmp_path / "clone.ttf"
    src.write_bytes(b"pretend font bytes")
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    monkeypatch.setitem(fonts.CLONE_SOURCES, "Carlito",
                        {"url": src.as_uri(), "sha256": digest})
    got = fonts.fetch_substitute("Calibri", tmp_path / "dest")
    assert got.exists() and got.read_bytes() == src.read_bytes()


def test_fetch_refuses_a_face_outside_the_allowlist():
    with pytest.raises(ValueError, match="no known substitute"):
        fonts.fetch_substitute("Corbel")


def test_plan_reports_exact_when_the_font_is_the_source_font():
    family, path = _first_installed()
    plan = fonts.plan(path, "abc", 10.0, fonts.text_width(path, "abc", 10.0), exact=True)
    assert plan.source == "exact"
    assert abs(plan.tracking_pt) < 0.01
