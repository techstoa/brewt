#!/usr/bin/env python3

"""Script for generating password possibilities"""

import argparse
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED


_active_procs = set()
_active_procs_lock = threading.Lock()


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='usage: %prog [options]')
    parser.add_argument('--passfile', '-p', required=True,
                        help="File containing password list.  One per line.")
    parser.add_argument('--minwords', default=1, type=int,
                        help="Minimum number of words to use in combinations.")
    parser.add_argument('--maxwords', type=int,
                        help="Maximum number of words to use in combinations.")
    parser.add_argument('--file', '-f',
                        help="GPG file to decrypt (enables GPG mode).")
    parser.add_argument('--verbose', '-v', action='store_true',
                        help="Verbose output (GPG mode only).")
    parser.add_argument('--mixcase', '-c', action='store_true',
                        help="Try all upper/lower case variations.")
    parser.add_argument('--workers', '-w', default=4, type=int,
                        help="Number of parallel GPG workers (default: 4).")
    return parser.parse_args()


def case_variants(word):
    """Generate all upper/lower case combinations for a word.

    For example, 'ab' yields 'ab', 'Ab', 'aB', 'AB'.
    Non-alpha characters contribute only one variant.
    """
    from itertools import product
    char_options = []
    for ch in word:
        if ch.isalpha():
            char_options.append((ch.lower(), ch.upper()))
        else:
            char_options.append((ch,))
    for combo in product(*char_options):
        yield ''.join(combo)


def generate_list(wordlist, min_words, max_words, mixcase=False):
    """Cycle through each password, then all permutations of combining two
    passwords, then 3, etc up to the length of the array."""
    from itertools import permutations
    for i in range(min_words, max_words):
        for current_option in permutations(wordlist, i):
            password = ''.join(current_option)
            if mixcase:
                yield from case_variants(password)
            else:
                yield password


def try_password(word, gpg_file):
    """Try decrypting a GPG file with the given password.

    Returns (word, True) on success, (word, False) on failure.
    """
    proc = subprocess.Popen(
        ['gpg', '--batch', '--yes', '--no-tty', '--passphrase-fd', '0',
         '--pinentry-mode', 'loopback', '--quiet', '--decrypt',
         gpg_file],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with _active_procs_lock:
        _active_procs.add(proc)
    try:
        proc.communicate(input=word.encode())
        return (word, proc.returncode == 0)
    finally:
        with _active_procs_lock:
            _active_procs.discard(proc)


def _kill_all_gpg():
    """Terminate all active GPG processes."""
    with _active_procs_lock:
        for proc in list(_active_procs):
            try:
                proc.kill()
            except ProcessLookupError:
                pass


def main():
    """Non-module logic for running as a commandline tool"""
    options = parse_args()

    with open(options.passfile) as file_handle:
        wordlist = [line.strip() for line in file_handle if line.strip()]

    maxwords = options.maxwords + 1 if options.maxwords else len(wordlist) + 1

    if options.minwords >= maxwords:
        raise ValueError(
            f"--minwords ({options.minwords}) must be less than "
            f"effective maxwords ({maxwords - 1})"
        )

    if options.file:
        password = False
        gen = generate_list(wordlist, options.minwords, maxwords,
                            options.mixcase)
        with ThreadPoolExecutor(max_workers=options.workers) as executor:
            pending = set()
            for word in gen:
                pending.add(executor.submit(try_password, word, options.file))
                if len(pending) >= options.workers:
                    break

            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    word_result, ok = future.result()
                    if options.verbose:
                        print(f"{word_result}: {ok}")
                    if ok:
                        password = word_result

                if password:
                    _kill_all_gpg()
                    for future in pending:
                        future.cancel()
                    break

                for word in gen:
                    pending.add(
                        executor.submit(try_password, word, options.file))
                    if len(pending) >= options.workers:
                        break

        if password:
            print("Password is %s" % password)
        else:
            print("Password not found")
    else:
        for word in generate_list(wordlist, options.minwords, maxwords,
                                  options.mixcase):
            print(word)


if __name__ == '__main__':
    main()
