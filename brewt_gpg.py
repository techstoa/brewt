#!/usr/bin/env python3

def setup():
    """parse arguments"""
    import argparse
    parser = argparse.ArgumentParser(description='usage: %prog [options]')
    parser.add_argument('--file', '-f', required=True,
                        help="File to decrypt")
    parser.add_argument('--passfile', '-p', default=False, required=True,
                        help="File containing password list.  One per line.")
    parser.add_argument('--minwords', default=1, type=int,
                        help="Minimum number of words to use in combinations.")
    parser.add_argument('--maxwords', type=int,
                        help="Maximum number of words to use in combinations.")
    parser.add_argument('--verbose', '-v', action="store_true",
                        help="Verbose Output")
    args = parser.parse_args()
    return args


def main():
    """Non-module logic for running as a commandline tool"""
    from brewt import generate_list
    import gnupg

    options = setup()

    wordlist = []
    # Build an array of all known passwords
    with open(options.passfile) as file_handle:
        for line in file_handle.readlines():
            wordlist.append(line.strip('\n'))

    if options.maxwords:
        maxwords = options.maxwords + 1
    else:
        # Add 1 since range() is exclusive at the upper bound
        maxwords = len(wordlist) + 1

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


if __name__ == '__main__':
    main()
