"""Tests for brewt_gpg"""
import sys
import types
import unittest.mock as mock

import pytest

import brewt_gpg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_passfile(tmp_path, words):
    p = tmp_path / 'words.txt'
    p.write_text('\n'.join(words) + '\n')
    return str(p)


def _make_gpg_file(tmp_path, content=b'encrypted'):
    p = tmp_path / 'secret.gpg'
    p.write_bytes(content)
    return str(p)


def _make_status(ok):
    status = mock.MagicMock()
    status.ok = ok
    return status


# ---------------------------------------------------------------------------
# setup()
# ---------------------------------------------------------------------------

def test_setup_required_file_missing(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['brewt_gpg', '-p', 'words.txt'])
    with pytest.raises(SystemExit):
        brewt_gpg.setup()


def test_setup_required_passfile_missing(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['brewt_gpg', '-f', 'secret.gpg'])
    with pytest.raises(SystemExit):
        brewt_gpg.setup()


def test_setup_defaults(monkeypatch):
    monkeypatch.setattr(
        sys, 'argv', ['brewt_gpg', '-f', 'f.gpg', '-p', 'p.txt']
    )
    args = brewt_gpg.setup()
    assert args.file == 'f.gpg'
    assert args.passfile == 'p.txt'
    assert args.minwords == 1
    assert args.maxwords is None
    assert args.verbose is False


def test_setup_all_args(monkeypatch):
    monkeypatch.setattr(
        sys, 'argv',
        ['brewt_gpg', '-f', 'f.gpg', '-p', 'p.txt',
         '--minwords', '2', '--maxwords', '3', '--verbose']
    )
    args = brewt_gpg.setup()
    assert args.minwords == 2
    assert args.maxwords == 3
    assert args.verbose is True


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def _run_main(monkeypatch, tmp_path, words, gpg_file, argv_extra=None,
              decrypt_results=None):
    """Helper: run brewt_gpg.main() with mocked gnupg."""
    passfile = _make_passfile(tmp_path, words)
    argv = ['brewt_gpg', '-f', gpg_file, '-p', passfile]
    if argv_extra:
        argv += argv_extra
    monkeypatch.setattr(sys, 'argv', argv)

    gpg_mock = mock.MagicMock()
    if decrypt_results is not None:
        gpg_mock.decrypt_file.side_effect = decrypt_results
    else:
        gpg_mock.decrypt_file.return_value = _make_status(False)

    gnupg_mod = types.ModuleType('gnupg')
    gnupg_mod.GPG = mock.MagicMock(return_value=gpg_mock)
    monkeypatch.setitem(sys.modules, 'gnupg', gnupg_mod)

    return gpg_mock


def test_main_password_found(monkeypatch, tmp_path, capsys):
    """Stops on the first matching password and prints it."""
    gpg_file = _make_gpg_file(tmp_path)
    gpg_mock = _run_main(
        monkeypatch, tmp_path, ['wrong', 'right'], gpg_file,
        decrypt_results=[_make_status(False), _make_status(True)]
    )
    brewt_gpg.main()
    out = capsys.readouterr().out
    assert 'right' in out
    assert gpg_mock.decrypt_file.call_count == 2


def test_main_password_not_found(monkeypatch, tmp_path, capsys):
    """Prints 'Password not found' when no password works."""
    gpg_file = _make_gpg_file(tmp_path)
    _run_main(monkeypatch, tmp_path, ['a', 'b'], gpg_file)
    brewt_gpg.main()
    out = capsys.readouterr().out
    assert 'Password not found' in out


def test_main_verbose(monkeypatch, tmp_path, capsys):
    """With --verbose each attempt is printed."""
    gpg_file = _make_gpg_file(tmp_path)
    _run_main(
        monkeypatch, tmp_path, ['x', 'y'], gpg_file,
        argv_extra=['--verbose'],
        decrypt_results=[_make_status(False), _make_status(True)]
    )
    brewt_gpg.main()
    out = capsys.readouterr().out
    assert 'x:' in out
    assert 'y:' in out


def test_main_with_maxwords(monkeypatch, tmp_path, capsys):
    """--maxwords limits the search space."""
    gpg_file = _make_gpg_file(tmp_path)
    gpg_mock = _run_main(
        monkeypatch, tmp_path, ['a', 'b', 'c'], gpg_file,
        argv_extra=['--maxwords', '1']
    )
    brewt_gpg.main()
    # maxwords=1 → range(1, 2) → 3 single-word attempts
    assert gpg_mock.decrypt_file.call_count == 3
    out = capsys.readouterr().out
    assert 'Password not found' in out


def test_main_module_guard(monkeypatch, tmp_path):
    """The __name__ == '__main__' guard calls main()."""
    import runpy
    passfile = _make_passfile(tmp_path, ['hi', 'bye'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv', ['brewt_gpg', '-f', gpg_file, '-p', passfile]
    )
    gpg_mock = mock.MagicMock()
    gpg_mock.decrypt_file.return_value = _make_status(False)
    gnupg_mod = types.ModuleType('gnupg')
    gnupg_mod.GPG = mock.MagicMock(return_value=gpg_mock)
    monkeypatch.setitem(sys.modules, 'gnupg', gnupg_mod)

    printed = []
    monkeypatch.setattr(
        'builtins.print', lambda *args, **kwargs: printed.append(args[0])
    )
    runpy.run_path('brewt_gpg.py', run_name='__main__')
    assert 'Password not found' in printed
