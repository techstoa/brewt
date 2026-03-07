"""Tests for brewt.py"""
import sys
import subprocess
import unittest.mock as mock

import pytest

import brewt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_passfile(tmp_path, words):
    """Write words (one per line) to a temp file and return its path."""
    p = tmp_path / 'words.txt'
    p.write_text('\n'.join(words) + '\n')
    return str(p)


def _make_gpg_file(tmp_path, content=b'encrypted'):
    p = tmp_path / 'secret.gpg'
    p.write_bytes(content)
    return str(p)


def _make_proc(returncode):
    result = mock.MagicMock(spec=subprocess.CompletedProcess)
    result.returncode = returncode
    return result


# ---------------------------------------------------------------------------
# generate_list
# ---------------------------------------------------------------------------

def test_generate_list_single_word():
    """min=1, max=2 yields each word once (permutations of length 1)."""
    result = brewt.generate_list(['a', 'b', 'c'], 1, 2)
    assert result == ['a', 'b', 'c']


def test_generate_list_two_words():
    """min=1, max=3 yields singles then all 2-word permutations."""
    result = brewt.generate_list(['x', 'y'], 1, 3)
    assert 'x' in result
    assert 'y' in result
    assert 'xy' in result
    assert 'yx' in result
    assert len(result) == 4


def test_generate_list_empty_range():
    """min == max produces an empty list."""
    result = brewt.generate_list(['a', 'b'], 2, 2)
    assert result == []


def test_generate_list_concatenates_correctly():
    """Words are joined without a separator."""
    result = brewt.generate_list(['foo', 'bar'], 2, 3)
    assert 'foobar' in result
    assert 'barfoo' in result


# ---------------------------------------------------------------------------
# setup (argument parsing)
# ---------------------------------------------------------------------------

def test_setup_required_passfile(monkeypatch):
    """--passfile is required; missing it exits with an error."""
    monkeypatch.setattr(sys, 'argv', ['brewt'])
    with pytest.raises(SystemExit):
        brewt.setup()


def test_setup_defaults(monkeypatch):
    """Default values for optional arguments are applied correctly."""
    monkeypatch.setattr(sys, 'argv', ['brewt', '-p', 'somefile'])
    args = brewt.setup()
    assert args.passfile == 'somefile'
    assert args.minwords == 1
    assert args.maxwords is None
    assert args.file is None
    assert args.verbose is False
    assert args.debug is False


def test_setup_all_args(monkeypatch):
    """All arguments are parsed when provided."""
    monkeypatch.setattr(
        sys, 'argv',
        ['brewt', '-p', 'p.txt', '-f', 'f.gpg',
         '--minwords', '2', '--maxwords', '4', '--verbose', '--debug']
    )
    args = brewt.setup()
    assert args.passfile == 'p.txt'
    assert args.file == 'f.gpg'
    assert args.minwords == 2
    assert args.maxwords == 4
    assert args.verbose is True
    assert args.debug is True


# ---------------------------------------------------------------------------
# main — list mode (no --file)
# ---------------------------------------------------------------------------

def test_main_without_maxwords(monkeypatch, tmp_path, capsys):
    """main() uses wordlist length as maxwords when --maxwords is omitted."""
    passfile = _make_passfile(tmp_path, ['cat', 'dog'])
    monkeypatch.setattr(sys, 'argv', ['brewt', '-p', passfile])
    brewt.main()
    output = capsys.readouterr().out.splitlines()
    assert 'cat' in output
    assert 'dog' in output


def test_main_with_maxwords(monkeypatch, tmp_path, capsys):
    """main() respects an explicit --maxwords value."""
    passfile = _make_passfile(tmp_path, ['cat', 'dog', 'bird'])
    monkeypatch.setattr(
        sys, 'argv', ['brewt', '-p', passfile, '--maxwords', '2']
    )
    brewt.main()
    output = capsys.readouterr().out.splitlines()
    # maxwords=2 → range(1, 3) → single words and 2-word combos, but not 3
    assert 'cat' in output
    assert 'catdog' in output
    assert 'catdogbird' not in output


def test_main_ignores_blank_lines(monkeypatch, tmp_path, capsys):
    """Blank lines in the passfile are ignored."""
    p = tmp_path / 'words.txt'
    p.write_text('\ncat\n\ndog\n\n')
    monkeypatch.setattr(sys, 'argv', ['brewt', '-p', str(p)])
    brewt.main()
    output = capsys.readouterr().out.splitlines()
    assert 'cat' in output
    assert 'dog' in output
    assert '' not in output


def test_main_strips_whitespace(monkeypatch, tmp_path, capsys):
    """Leading/trailing whitespace and Windows line endings are stripped."""
    p = tmp_path / 'words.txt'
    p.write_bytes(b'cat\r\n dog \r\nbird\r\n')
    monkeypatch.setattr(sys, 'argv', ['brewt', '-p', str(p)])
    brewt.main()
    output = capsys.readouterr().out.splitlines()
    assert 'cat' in output
    assert 'dog' in output
    assert 'bird' in output


# ---------------------------------------------------------------------------
# main — GPG mode (--file provided)
# ---------------------------------------------------------------------------

def _setup_gpg_mock(monkeypatch, returncodes=None):
    """Mock subprocess.run; returncodes is a list of return codes per call.
    If omitted, all calls return failure (rc=1)."""
    if returncodes is None:
        run_mock = mock.MagicMock(return_value=_make_proc(1))
    else:
        run_mock = mock.MagicMock(
            side_effect=[_make_proc(rc) for rc in returncodes]
        )
    monkeypatch.setattr('brewt.subprocess.run', run_mock)
    return run_mock


def test_main_gpg_password_found(monkeypatch, tmp_path, capsys):
    """GPG mode stops on the first matching password and prints it."""
    passfile = _make_passfile(tmp_path, ['wrong', 'right'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv', ['brewt', '-p', passfile, '-f', gpg_file]
    )
    run_mock = _setup_gpg_mock(monkeypatch, returncodes=[1, 0])
    brewt.main()
    out = capsys.readouterr().out
    assert 'right' in out
    assert run_mock.call_count == 2


def test_main_gpg_uses_pinentry_loopback(monkeypatch, tmp_path):
    """subprocess.run is called with --pinentry-mode loopback."""
    passfile = _make_passfile(tmp_path, ['pw'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv', ['brewt', '-p', passfile, '-f', gpg_file]
    )
    run_mock = _setup_gpg_mock(monkeypatch, returncodes=[0])
    brewt.main()
    cmd = run_mock.call_args[0][0]
    assert '--pinentry-mode' in cmd
    assert 'loopback' in cmd


def test_main_gpg_passphrase_via_stdin(monkeypatch, tmp_path):
    """Passphrase is passed via stdin (--passphrase-fd 0), not as an arg."""
    passfile = _make_passfile(tmp_path, ['secret'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv', ['brewt', '-p', passfile, '-f', gpg_file]
    )
    run_mock = _setup_gpg_mock(monkeypatch, returncodes=[0])
    brewt.main()
    kwargs = run_mock.call_args[1]
    assert kwargs['input'] == b'secret'
    cmd = run_mock.call_args[0][0]
    assert '--passphrase-fd' in cmd
    assert 'secret' not in cmd  # must NOT appear in the command line


def test_main_gpg_password_not_found(monkeypatch, tmp_path, capsys):
    """GPG mode prints 'Password not found' when no password works."""
    passfile = _make_passfile(tmp_path, ['a', 'b'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv', ['brewt', '-p', passfile, '-f', gpg_file]
    )
    _setup_gpg_mock(monkeypatch)  # default: all calls fail
    brewt.main()
    assert 'Password not found' in capsys.readouterr().out


def test_main_gpg_verbose(monkeypatch, tmp_path, capsys):
    """GPG mode with --verbose prints each attempt."""
    passfile = _make_passfile(tmp_path, ['x', 'y'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv', ['brewt', '-p', passfile, '-f', gpg_file, '--verbose']
    )
    _setup_gpg_mock(monkeypatch, returncodes=[1, 0])
    brewt.main()
    out = capsys.readouterr().out
    assert 'x:' in out
    assert 'y:' in out


def test_main_gpg_with_maxwords(monkeypatch, tmp_path, capsys):
    """GPG mode respects --maxwords."""
    passfile = _make_passfile(tmp_path, ['a', 'b', 'c'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv',
        ['brewt', '-p', passfile, '-f', gpg_file, '--maxwords', '1']
    )
    run_mock = _setup_gpg_mock(monkeypatch, returncodes=[1, 1, 1])
    brewt.main()
    # maxwords=1 → range(1, 2) → 3 single-word attempts
    assert run_mock.call_count == 3
    assert 'Password not found' in capsys.readouterr().out


def test_main_gpg_debug(monkeypatch, tmp_path, capsys):
    """GPG mode with --debug prints each password before trying it."""
    passfile = _make_passfile(tmp_path, ['x', 'y'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv', ['brewt', '-p', passfile, '-f', gpg_file, '--debug']
    )
    _setup_gpg_mock(monkeypatch, returncodes=[1, 0])
    brewt.main()
    out = capsys.readouterr().out
    assert 'Trying: x' in out
    assert 'Trying: y' in out


# ---------------------------------------------------------------------------
# __main__ guard
# ---------------------------------------------------------------------------

def test_main_module_guard(monkeypatch, tmp_path):
    """The __name__ == '__main__' guard calls main()."""
    import runpy
    passfile = _make_passfile(tmp_path, ['hi', 'bye'])
    monkeypatch.setattr(sys, 'argv', ['brewt', '-p', passfile])
    printed = []
    monkeypatch.setattr(
        'builtins.print', lambda *args, **kwargs: printed.append(args[0])
    )
    runpy.run_path('brewt.py', run_name='__main__')
    assert 'hi' in printed
