"""Tests for brewt.py"""
import sys

import pytest

import brewt


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


def test_setup_all_args(monkeypatch):
    """All arguments are parsed when provided."""
    monkeypatch.setattr(
        sys, 'argv',
        ['brewt', '-p', 'myfile', '--minwords', '2', '--maxwords', '4']
    )
    args = brewt.setup()
    assert args.passfile == 'myfile'
    assert args.minwords == 2
    assert args.maxwords == 4


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def _make_passfile(tmp_path, words):
    """Write words (one per line) to a temp file and return its path."""
    p = tmp_path / 'words.txt'
    p.write_text('\n'.join(words) + '\n')
    return str(p)


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
