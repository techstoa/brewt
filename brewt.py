#!/usr/bin/env python3

"""Script for generating password possibilities"""


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
    args = parser.parse_args()
    return args


def generate_list(wordlist, min_words, max_words):
    """Cycle through each password, then all permutations of combining two
    passwords, then 3, etc up to the length of the array."""
    from itertools import permutations
    mylist = []
    for i in range(min_words, max_words):
        for current_option in permutations(wordlist, i):
            mylist.append(''.join(current_option))
    return mylist


def main():
    """Non-module logic for running as a commandline tool"""
    options = setup()

    with open(options.passfile) as file_handle:
        wordlist = [line.strip() for line in file_handle if line.strip()]

    maxwords = options.maxwords + 1 if options.maxwords else len(wordlist) + 1

    if options.file:
        import gnupg
        gpg = gnupg.GPG()
        with open(options.file) as file_handle:
            password = False
            for word in generate_list(wordlist, options.minwords, maxwords):
                file_handle.seek(0, 0)
                status = gpg.decrypt_file(file_handle, passphrase=word)
                if options.verbose:
                    print("%s: %s" % (word, status.ok))
                if status.ok:
                    password = word
                    break
        if password:
            print("Password is %s" % password)
        else:
            print("Password not found")
    else:
        for word in generate_list(wordlist, options.minwords, maxwords):
            print(word)


if __name__ == '__main__':
    main()
