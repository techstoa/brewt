#!/usr/bin/python

from itertools import permutations

wordlist = []

f = open('test.txt')
for line in f.readlines():
    wordlist.append(line.strip('\n'))

print wordlist
