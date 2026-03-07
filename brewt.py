#!/usr/bin/env python3

"""Script for generating password possibilities"""

import subprocess


def setup():
    """parse arguments"""
    import argparse
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
    parser.add_argument('--debug', '-d', action='store_true',
                        help="Print each password before using it.")
    parser.add_argument('--mixcase', '-c', action='store_true',
                        help="Try all upper/lower case variations.")
    args = parser.parse_args()
    return args


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


def main():
    """Non-module logic for running as a commandline tool"""
    options = setup()

    with open(options.passfile) as file_handle:
        wordlist = [line.strip() for line in file_handle if line.strip()]

    maxwords = options.maxwords + 1 if options.maxwords else len(wordlist) + 1

    if options.file:
        password = False
        for word in generate_list(wordlist, options.minwords, maxwords,
                                  options.mixcase):
            if options.debug:
                print("Trying: %s" % word)
            result = subprocess.run(
                ['gpg', '--batch', '--passphrase-fd', '0',
                 '--pinentry-mode', 'loopback', '--quiet', '--decrypt',
                 options.file],
                input=word.encode(),
                capture_output=True,
            )
            ok = result.returncode == 0
            if options.verbose:
                print(f"{word}: {ok}")
            if ok:
                password = word
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
