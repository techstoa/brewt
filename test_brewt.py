"""Tests for brewt.py"""
import sys
import unittest.mock as mock

import pytest

import brewt


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_active_procs():
    brewt._active_procs.clear()
    yield


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


def _make_popen_mock(returncode):
    proc = mock.MagicMock()
    proc.communicate.return_value = (b'', b'')
    proc.returncode = returncode
    return proc


def _setup_gpg_mock(monkeypatch, returncodes=None):
    """Mock subprocess.Popen; returncodes is a list of return codes per call.
    If omitted, all calls return failure (rc=1).
    The created proc mocks are available via ``popen_mock._mocks``."""
    mocks = []
    codes = list(returncodes) if returncodes else None

    def side_effect(*args, **kwargs):
        rc = codes.pop(0) if codes else 1
        proc = _make_popen_mock(rc)
        mocks.append(proc)
        return proc

    popen_mock = mock.MagicMock(side_effect=side_effect)
    popen_mock._mocks = mocks
    monkeypatch.setattr('brewt.subprocess.Popen', popen_mock)
    return popen_mock


# ---------------------------------------------------------------------------
# case_variants
# ---------------------------------------------------------------------------

def test_case_variants_all_alpha():
    """All alpha chars produce 2^n variants."""
    result = list(brewt.case_variants('ab'))
    assert sorted(result) == sorted(['ab', 'Ab', 'aB', 'AB'])


def test_case_variants_with_digits():
    """Non-alpha characters contribute only one variant."""
    result = list(brewt.case_variants('a1'))
    assert sorted(result) == sorted(['a1', 'A1'])


def test_case_variants_no_alpha():
    """All non-alpha returns a single variant."""
    result = list(brewt.case_variants('123'))
    assert result == ['123']


def test_case_variants_empty_string():
    """Empty string returns a single empty variant."""
    result = list(brewt.case_variants(''))
    assert result == ['']


# ---------------------------------------------------------------------------
# generate_list
# ---------------------------------------------------------------------------

def test_generate_list_single_word():
    """min=1, max=2 yields each word once (permutations of length 1)."""
    result = list(brewt.generate_list(['a', 'b', 'c'], 1, 2))
    assert result == ['a', 'b', 'c']


def test_generate_list_two_words():
    """min=1, max=3 yields singles then all 2-word permutations."""
    result = list(brewt.generate_list(['x', 'y'], 1, 3))
    assert 'x' in result
    assert 'y' in result
    assert 'xy' in result
    assert 'yx' in result
    assert len(result) == 4


def test_generate_list_empty_range():
    """min == max produces an empty list."""
    result = list(brewt.generate_list(['a', 'b'], 2, 2))
    assert result == []


def test_generate_list_concatenates_correctly():
    """Words are joined without a separator."""
    result = list(brewt.generate_list(['foo', 'bar'], 2, 3))
    assert 'foobar' in result
    assert 'barfoo' in result


def test_generate_list_mixcase():
    """mixcase=True expands each password into all case variants."""
    result = list(brewt.generate_list(['ab'], 1, 2, mixcase=True))
    assert sorted(result) == sorted(['ab', 'Ab', 'aB', 'AB'])


# ---------------------------------------------------------------------------
# parse_args (argument parsing)
# ---------------------------------------------------------------------------

def test_parse_args_required_passfile(monkeypatch):
    """--passfile is required; missing it exits with an error."""
    monkeypatch.setattr(sys, 'argv', ['brewt'])
    with pytest.raises(SystemExit):
        brewt.parse_args()


def test_parse_args_defaults(monkeypatch):
    """Default values for optional arguments are applied correctly."""
    monkeypatch.setattr(sys, 'argv', ['brewt', '-p', 'somefile'])
    args = brewt.parse_args()
    assert args.passfile == 'somefile'
    assert args.minwords == 1
    assert args.maxwords is None
    assert args.file is None
    assert args.verbose is False
    assert args.mixcase is False
    assert args.workers == 4


def test_parse_args_all_args(monkeypatch):
    """All arguments are parsed when provided."""
    monkeypatch.setattr(
        sys, 'argv',
        ['brewt', '-p', 'p.txt', '-f', 'f.gpg',
         '--minwords', '2', '--maxwords', '4', '--verbose',
         '--mixcase', '--workers', '2']
    )
    args = brewt.parse_args()
    assert args.passfile == 'p.txt'
    assert args.file == 'f.gpg'
    assert args.minwords == 2
    assert args.maxwords == 4
    assert args.verbose is True
    assert args.mixcase is True
    assert args.workers == 2


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
    assert 'catdog' in output
    assert 'dogcat' in output


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


def test_main_list_mixcase(monkeypatch, tmp_path, capsys):
    """--mixcase in list mode outputs all case variants."""
    passfile = _make_passfile(tmp_path, ['ab'])
    monkeypatch.setattr(
        sys, 'argv',
        ['brewt', '-p', passfile, '--maxwords', '1', '--mixcase']
    )
    brewt.main()
    output = capsys.readouterr().out.splitlines()
    assert sorted(output) == sorted(['ab', 'Ab', 'aB', 'AB'])


def test_main_minwords_greater_than_maxwords(monkeypatch, tmp_path):
    """main() raises ValueError when minwords >= effective maxwords."""
    passfile = _make_passfile(tmp_path, ['a', 'b'])
    monkeypatch.setattr(
        sys, 'argv',
        ['brewt', '-p', passfile, '--minwords', '3', '--maxwords', '2']
    )
    with pytest.raises(ValueError, match='minwords'):
        brewt.main()


# ---------------------------------------------------------------------------
# main — GPG mode (--file provided)
# ---------------------------------------------------------------------------

def test_main_gpg_password_found(monkeypatch, tmp_path, capsys):
    """GPG mode stops on the first matching password and prints it."""
    passfile = _make_passfile(tmp_path, ['wrong', 'right'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv', ['brewt', '-p', passfile, '-f', gpg_file, '-w', '1']
    )
    popen_mock = _setup_gpg_mock(monkeypatch, returncodes=[1, 0])
    brewt.main()
    out = capsys.readouterr().out
    assert 'right' in out
    assert popen_mock.call_count == 2


def test_main_gpg_uses_pinentry_loopback(monkeypatch, tmp_path):
    """subprocess.Popen is called with --pinentry-mode loopback."""
    passfile = _make_passfile(tmp_path, ['pw'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv', ['brewt', '-p', passfile, '-f', gpg_file, '-w', '1']
    )
    popen_mock = _setup_gpg_mock(monkeypatch, returncodes=[0])
    brewt.main()
    cmd = popen_mock.call_args[0][0]
    assert '--pinentry-mode' in cmd
    assert 'loopback' in cmd
    assert '--no-tty' in cmd
    assert '--yes' in cmd


def test_main_gpg_passphrase_via_stdin(monkeypatch, tmp_path):
    """Passphrase is passed via stdin (--passphrase-fd 0), not as an arg."""
    passfile = _make_passfile(tmp_path, ['secret'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv', ['brewt', '-p', passfile, '-f', gpg_file, '-w', '1']
    )
    popen_mock = _setup_gpg_mock(monkeypatch, returncodes=[0])
    brewt.main()
    # The actual proc mocks are stored on the mock by _setup_gpg_mock.
    proc_mock = popen_mock._mocks[0]
    kwargs = proc_mock.communicate.call_args[1]
    assert kwargs['input'] == b'secret'
    cmd = popen_mock.call_args[0][0]
    assert '--passphrase-fd' in cmd
    assert 'secret' not in cmd  # must NOT appear in the command line


def test_main_gpg_password_not_found(monkeypatch, tmp_path, capsys):
    """GPG mode prints 'Password not found' when no password works."""
    passfile = _make_passfile(tmp_path, ['a', 'b'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv', ['brewt', '-p', passfile, '-f', gpg_file, '-w', '1']
    )
    _setup_gpg_mock(monkeypatch)  # default: all calls fail
    brewt.main()
    assert 'Password not found' in capsys.readouterr().out


def test_main_gpg_verbose(monkeypatch, tmp_path, capsys):
    """GPG mode with --verbose prints each attempt."""
    passfile = _make_passfile(tmp_path, ['x', 'y'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv', ['brewt', '-p', passfile, '-f', gpg_file, '--verbose',
                      '-w', '1']
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
        ['brewt', '-p', passfile, '-f', gpg_file, '--maxwords', '1',
         '-w', '1']
    )
    popen_mock = _setup_gpg_mock(monkeypatch, returncodes=[1, 1, 1])
    brewt.main()
    # maxwords=1 → range(1, 2) → 3 single-word attempts
    assert popen_mock.call_count == 3
    assert 'Password not found' in capsys.readouterr().out


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


# ---------------------------------------------------------------------------
# try_password
# ---------------------------------------------------------------------------

def test_try_password_success(monkeypatch):
    """try_password returns (word, True) when gpg succeeds."""
    popen_mock = mock.MagicMock(return_value=_make_popen_mock(0))
    monkeypatch.setattr('brewt.subprocess.Popen', popen_mock)
    word, ok = brewt.try_password('secret', 'file.gpg')
    assert word == 'secret'
    assert ok is True


def test_try_password_failure(monkeypatch):
    """try_password returns (word, False) when gpg fails."""
    popen_mock = mock.MagicMock(return_value=_make_popen_mock(1))
    monkeypatch.setattr('brewt.subprocess.Popen', popen_mock)
    word, ok = brewt.try_password('wrong', 'file.gpg')
    assert word == 'wrong'
    assert ok is False


# ---------------------------------------------------------------------------
# main — parallel workers
# ---------------------------------------------------------------------------

def test_main_gpg_parallel_finds_password(monkeypatch, tmp_path, capsys):
    """GPG mode with multiple workers finds the correct password."""
    passfile = _make_passfile(
        tmp_path, ['wrong1', 'wrong2', 'right', 'wrong3'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv',
        ['brewt', '-p', passfile, '-f', gpg_file, '-w', '2']
    )

    def popen_side_effect(cmd, **kwargs):
        proc = mock.MagicMock()

        def communicate(input=None, timeout=None):
            word = input.decode() if input else ''
            proc.returncode = 0 if word == 'right' else 1
            return (b'', b'')

        proc.communicate = communicate
        return proc

    monkeypatch.setattr('brewt.subprocess.Popen',
                        mock.MagicMock(side_effect=popen_side_effect))
    brewt.main()
    assert 'right' in capsys.readouterr().out


def test_main_gpg_parallel_not_found(monkeypatch, tmp_path, capsys):
    """GPG mode with multiple workers reports not found."""
    passfile = _make_passfile(tmp_path, ['a', 'b', 'c'])
    gpg_file = _make_gpg_file(tmp_path)
    monkeypatch.setattr(
        sys, 'argv',
        ['brewt', '-p', passfile, '-f', gpg_file, '-w', '3']
    )

    def popen_side_effect(cmd, **kwargs):
        proc = mock.MagicMock()
        proc.communicate.return_value = (b'', b'')
        proc.returncode = 1
        return proc

    monkeypatch.setattr('brewt.subprocess.Popen',
                        mock.MagicMock(side_effect=popen_side_effect))
    brewt.main()
    assert 'Password not found' in capsys.readouterr().out
