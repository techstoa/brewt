#!/usr/bin/python

from itertools import permutations

wordlist = []

def setup():
    import argparse
    parser = argparse.ArgumentParser(description='usage: %prog [options]')
    parser.add_argument('--passfile', '-p', default=False, required=True,
            help="File containing password list.  One per line.")
    parser.add_argument('--minwords', default=1, type=int,
            help="Minimum number of words to use in combinations.")
    parser.add_argument('--maxwords', type=int,
            help="Maximum number of words to use in combinations.")
    args = parser.parse_args()
    return args

def generate_list(wordlist, min_words, max_words):
    """Cycle through each password, then all permutations of combining two passwords, 
    then 3, etc up to the length of the array."""
    mylist = []
    for i in xrange(min_words,max_words):
        for p in permutations(wordlist, i):
            mylist.append(''.join(p))
    return mylist

def main():
    options = setup()

    # Build an array of all known passwords
    f = open(options.passfile)
    for line in f.readlines():
        wordlist.append(line.strip('\n'))

    if options.maxwords:
        maxwords = options.maxwords
    else:
        # Add 1 since the length is 0 indexed
        maxwords = len(wordlist)

    for word in generate_list(wordlist, options.minwords, maxwords):
        print word

if __name__ == '__main__':
    main()
