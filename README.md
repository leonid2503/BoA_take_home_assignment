# Anagrams

Given a list of dictionary words (`words.txt`), find every word in it that is an anagram of a given word.

```python
>>> from anagrams import Anagrams
>>> anagrams = Anagrams()
>>> anagrams.get_anagrams('plates')
['palest', 'pastel', 'petals', 'plates', 'staple']
>>> anagrams.get_anagrams('Tea')
['ate', 'eat', 'tea']
```

The original task is in [anagrams.txt](anagrams.txt). It asks for a working `get_anagrams()`, plus three bonus goals: fast retrieval, more tests, and thread safety. The solution and its tests are in [anagrams.py](anagrams.py).

## Running it

You need Python 3 (tested with 3.12). It uses only the standard library.

```sh
python3 anagrams.py                 # run all tests
python3 -m unittest anagrams -v     # run all tests, listing each one
```

## How it works

### The idea

Two words are anagrams if they use the same letters the same number of times. If you sort the letters of each word, all anagrams end up as the same string:

```
plates  →  aelpst
staple  →  aelpst
petals  →  aelpst
```

This sorted string is the word's **signature**. To find a word's anagrams, compute its signature and return every word with the same signature.

### Build the index once

When an `Anagrams` object is created, it reads `words.txt` once and groups every word by its signature in a dictionary:

```
"aelpst" → ("palest", "pastel", "petals", "plates", "staple")
"aet"    → ("ate", "eat", "tea")
...
```

Building the index for the 45,402 words takes about 35 ms.

### Fast lookups

`get_anagrams(word)` then only needs a dictionary lookup:

1. **If the word is in the list**, a second dictionary maps it straight to its group, so the letters don't need sorting. This takes about 0.07 µs.
2. **If it isn't** (e.g. `'setlap'`), the method strips spaces, ignores case, sorts the letters, and looks up the signature. This takes about 0.3 µs.
3. **If nothing matches**, it returns `[]`.

The method searches no part of the word list at query time. The work depends only on the length of the query, not on the size of the dictionary.

### Thread safety without locks

The index is built entirely in `__init__` and is **only read** afterwards. Groups are stored as tuples, so they can't be changed. Each call returns a **new list**, so a caller who modifies the result can't affect the index or anyone else's result.

Because no shared state is ever written after construction, any number of threads can call `get_anagrams()` at once without locks.

## Behaviour

| Case | Example | Result |
|---|---|---|
| Case is ignored | `'EAT'` | `['ate', 'eat', 'tea']` |
| Surrounding whitespace is ignored | `'  tae '` | `['ate', 'eat', 'tea']` |
| The query is included if it's in the list | `'eat'` | `['ate', 'eat', 'tea']` |
| The query doesn't have to be in the list | `'setlap'` | `['palest', 'pastel', ...]` |
| Letter counts must match, not just letters | `'teat'` | `['Tate']` |
| A word with no other anagrams | `'rhythm'` | `['rhythm']` |
| No match | `'xyz'` | `[]` |
| Not a string | `None`, `42` | raises `TypeError` |

## Tests

There are 28 tests in `TestAnagrams`, including the two from the original task.

- **Behaviour:** each row of the table above, plus result ordering, spelling and copies.
- **Every word in the dictionary:** every word, and a scrambled re-cased copy of every word, is checked against a separate, simpler definition of an anagram (counting letters with `Counter`). This checks the solution with a second method instead of with itself.
- **Random queries and near misses:** 5,000 generated queries, including words with one letter added, removed or changed. Near misses should *not* match.
- **Reading the word file:** different line endings, padding, blank lines, duplicates, an empty file, a byte-order mark, a missing file, and non-English characters.
- **Thread safety:** up to 32 threads query the same object at once and must get the same answers as a single thread. The thread switch interval is shortened so the threads really interleave instead of running one after another.

## Files

| File | What it is |
|---|---|
| [anagrams.py](anagrams.py) | The solution (`Anagrams` class) and its tests |
| [anagrams.txt](anagrams.txt) | The original task and starter code |
| [words.txt](words.txt) | The word list (45,402 words) |
