import subprocess

from straightedge import fonts


def _fake_fc_list(stdout, returncode=0):
    def run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")
    return run


def test_status_error_when_no_cjk_font(monkeypatch):
    monkeypatch.setattr(fonts.subprocess, "run", _fake_fc_list(""))
    level, message = fonts.font_status("Noto Sans CJK SC")
    assert level == "error"
    assert "fonts-noto-cjk" in message


def test_status_ok_when_requested_font_present(monkeypatch):
    monkeypatch.setattr(fonts.subprocess, "run", _fake_fc_list("Noto Sans CJK SC\nDroid Sans Fallback\n"))
    level, _ = fonts.font_status("Noto Sans CJK SC")
    assert level == "ok"


def test_status_warn_when_other_cjk_but_not_requested(monkeypatch):
    monkeypatch.setattr(fonts.subprocess, "run", _fake_fc_list("WenQuanYi Zen Hei\n"))
    level, message = fonts.font_status("Noto Sans CJK SC")
    assert level == "warn"
    assert "WenQuanYi Zen Hei" in message


def test_cannot_check_is_treated_as_ok(monkeypatch):
    def boom(cmd, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(fonts.subprocess, "run", boom)
    level, _ = fonts.font_status("Noto Sans CJK SC")
    assert level == "ok"  # no fontconfig -> don't block
