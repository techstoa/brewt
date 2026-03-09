"""End-to-end tests for brewt using real GPG encryption."""
import subprocess
import sys

import pytest

import brewt

pytestmark = pytest.mark.e2e

PLAINTEXT = b"The quick brown fox jumps over the lazy dog.\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolated_gpg(tmp_path, monkeypatch):
    """Run every test with a throwaway GNUPGHOME so we never touch
    the user's real keyring."""
    gpg_home = tmp_path / "gnupg"
    gpg_home.mkdir(mode=0o700)
    monkeypatch.setenv("GNUPGHOME", str(gpg_home))


def _encrypt_file(tmp_path, passphrase, plaintext=PLAINTEXT):
    """Symmetrically encrypt *plaintext* with *passphrase*.

    Returns the path to the .gpg file.
    """
    plain = tmp_path / "secret.txt"
    plain.write_bytes(plaintext)
    encrypted = tmp_path / "secret.txt.gpg"
    subprocess.run(
        ["gpg", "--batch", "--yes", "--passphrase-fd", "0",
         "--pinentry-mode", "loopback", "--symmetric",
         "--cipher-algo", "AES256",
         "--output", str(encrypted), str(plain)],
        input=passphrase.encode(),
        capture_output=True,
        check=True,
    )
    return str(encrypted)


def _make_passfile(tmp_path, words):
    p = tmp_path / "words.txt"
    p.write_text("\n".join(words) + "\n")
    return str(p)


def _run_brewt(argv):
    """Run brewt.main() with the given argv and return captured stdout."""
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    old_argv = sys.argv
    try:
        sys.argv = ["brewt"] + argv
        with redirect_stdout(buf):
            brewt.main()
    finally:
        sys.argv = old_argv
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_finds_correct_password(tmp_path):
    """brewt finds the password used to encrypt the file."""
    gpg_file = _encrypt_file(tmp_path, "cherry")
    passfile = _make_passfile(
        tmp_path, ["apple", "banana", "cherry", "date"])
    out = _run_brewt(
        ["-p", passfile, "-f", gpg_file, "-w", "1"])
    assert "Password is cherry" in out


def test_password_not_found(tmp_path):
    """brewt reports failure when no candidate matches."""
    gpg_file = _encrypt_file(tmp_path, "secret")
    passfile = _make_passfile(tmp_path, ["wrong1", "wrong2"])
    out = _run_brewt(
        ["-p", passfile, "-f", gpg_file, "-w", "1"])
    assert "Password not found" in out


def test_finds_combined_password(tmp_path):
    """brewt finds a password that is a combination of words."""
    gpg_file = _encrypt_file(tmp_path, "catdog")
    passfile = _make_passfile(tmp_path, ["cat", "dog", "bird"])
    out = _run_brewt(
        ["-p", passfile, "-f", gpg_file,
         "--maxwords", "2", "-w", "1"])
    assert "Password is catdog" in out


def test_finds_password_with_mixcase(tmp_path):
    """brewt finds a mixed-case variant of a candidate word."""
    gpg_file = _encrypt_file(tmp_path, "Hello")
    passfile = _make_passfile(tmp_path, ["hello"])
    out = _run_brewt(
        ["-p", passfile, "-f", gpg_file,
         "--maxwords", "1", "--mixcase", "-w", "1"])
    assert "Password is Hello" in out


def test_verbose_output(tmp_path):
    """Verbose mode prints each attempt with its result."""
    gpg_file = _encrypt_file(tmp_path, "banana")
    passfile = _make_passfile(tmp_path, ["apple", "banana"])
    out = _run_brewt(
        ["-p", passfile, "-f", gpg_file, "--verbose", "-w", "1"])
    assert "apple: False" in out
    assert "banana: True" in out
    assert "Password is banana" in out


def test_parallel_workers_find_password(tmp_path):
    """Multiple workers still converge on the correct password."""
    gpg_file = _encrypt_file(tmp_path, "needle")
    words = [f"hay{i}" for i in range(20)] + ["needle"]
    passfile = _make_passfile(tmp_path, words)
    out = _run_brewt(
        ["-p", passfile, "-f", gpg_file, "-w", "4"])
    assert "Password is needle" in out


def test_list_mode_no_gpg(tmp_path):
    """Without --file, brewt just prints candidate passwords."""
    passfile = _make_passfile(tmp_path, ["cat", "dog"])
    out = _run_brewt(
        ["-p", passfile, "--maxwords", "1"])
    lines = out.strip().splitlines()
    assert "cat" in lines
    assert "dog" in lines
