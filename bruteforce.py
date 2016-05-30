#!/usr/bin/python

from itertools import permutations

wordlist = []

def setup():
    import argparse
    parser = argparse.ArgumentParser(description='usage: %prog [options]')
    parser.add_argument('--passfile', '-p', default=False, required=True,
            help="File containing password list.  One per line.")
    args = parser.parse_args()
    return args

def main():
    options = setup()

    # Build an array of all known passwords
    f = open(options.passfile)
    for line in f.readlines():
        wordlist.append(line.strip('\n'))

    # Cycle through each password, then all permutations of
    # combining two passwords, then 3, etc up to the length of the array.
    for i in xrange(1,len(wordlist)+1):
        for p in permutations(wordlist, i):
            print ''.join(p)

if __name__ == '__main__':
    main()
