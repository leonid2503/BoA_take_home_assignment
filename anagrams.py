
import os
import random
import sys
import tempfile
import threading
import unittest
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor


try:
    MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:  # run with exec()
    MODULE_DIR = os.getcwd()


def default_words_path():
    """words.txt in the working directory, else the one next to this file."""
    if os.path.isfile('words.txt'):
        return 'words.txt'
    return os.path.join(MODULE_DIR, 'words.txt')


class Anagrams:
    """Finds anagrams in a fixed word list.

    Matching ignores case (via casefold) and surrounding whitespace. Results
    keep the word list's spelling, include the query itself when listed, and
    are sorted case-insensitively.

    The index is built once in __init__ and only read afterwards, so instances
    are thread safe without locks.
    """

    def __init__(self, path=None):
        if path is None:
            path = default_words_path()
        
        with open(path, encoding='utf-8-sig') as f:
            words = {line.strip() for line in f.read().split('\n')}
        words.discard('')

        groups = defaultdict(list)
        for word in words:
            groups[''.join(sorted(word.casefold()))].append(word)

        by_signature = {}
        by_word = {}
        for signature, members in groups.items():
            if len(members) > 1:
                members.sort(key=lambda w: (w.casefold(), w))
            group = tuple(members)
            by_signature[signature] = group
            for word in group:
                by_word[word] = group
                by_word[word.casefold()] = group
        self._by_signature = by_signature
        self._by_word = by_word

    def get_anagrams(self, word):
        group = self._by_word.get(word)
        if group is None:
            if not isinstance(word, str):
                raise TypeError(f'word must be a str, not {type(word).__name__}')
            key = word.strip().casefold()
            group = self._by_word.get(key)
            if group is None:
                group = self._by_signature.get(''.join(sorted(key)), ())
        return [*group] 

class TestAnagrams(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.anagrams = Anagrams()  
        with open(default_words_path(), 'rb') as f:
            lines = f.read().decode('utf-8-sig').split('\n')
        cls.words = sorted({line.strip() for line in lines} - {''})
        groups = defaultdict(list)
        for word in cls.words:
            groups[cls.letter_counts(word)].append(word)
        cls.oracle = {key: sorted(group, key=lambda w: (w.casefold(), w))
                      for key, group in groups.items()}


    def test_anagrams(self):
        anagrams = Anagrams()
        self.assertEqual(anagrams.get_anagrams('plates'), ['palest', 'pastel', 'petals', 'plates', 'staple'])
        self.assertEqual(anagrams.get_anagrams('eat'), ['ate', 'eat', 'tea'])

    def test_query_does_not_have_to_be_listed(self):
        self.assertEqual(self.anagrams.get_anagrams('tae'), ['ate', 'eat', 'tea'])
        self.assertEqual(self.anagrams.get_anagrams('setlap'),
                         ['palest', 'pastel', 'petals', 'plates', 'staple'])

    def test_word_without_other_anagrams_returns_only_itself(self):
        self.assertEqual(self.anagrams.get_anagrams('rhythm'), ['rhythm'])

    def test_letters_must_match_in_number_not_just_in_kind(self):
        self.assertEqual(self.anagrams.get_anagrams('teat'), ['Tate'])
        self.assertEqual(self.anagrams.get_anagrams('eeat'), [])

    def test_no_match_returns_empty_list(self):
        for query in ('xyzzyq', 'ea', '', '   '):
            with self.subTest(query=query):
                self.assertEqual(self.anagrams.get_anagrams(query), [])

    def test_matching_ignores_case(self):
        for query in ('EAT', 'Tea', 'aTe', 'TAE'):
            with self.subTest(query=query):
                self.assertEqual(self.anagrams.get_anagrams(query), ['ate', 'eat', 'tea'])

    def test_results_keep_listed_spelling_and_are_sorted_ignoring_case(self):
        self.assertEqual(self.anagrams.get_anagrams('able'),
                         ['Abel', 'able', 'bale', 'Bela', 'Elba'])
        self.assertEqual(self.anagrams.get_anagrams('pascal'), ['PASCAL', 'Pascal'])

    def test_surrounding_whitespace_is_ignored(self):
        for query in ('  eat\n', '\tEAT\r\n', ' tae ', '　tea\xa0'):
            with self.subTest(query=query):
                self.assertEqual(self.anagrams.get_anagrams(query), ['ate', 'eat', 'tea'])

    def test_punctuation_and_digits_count_as_characters(self):
        self.assertEqual(self.anagrams.get_anagrams("neirB'o"), ["O'Brien"])
        self.assertEqual(self.anagrams.get_anagrams('OBrien'), [])
        self.assertEqual(self.anagrams.get_anagrams('2-aludoM'), ['Modula-2'])

    def test_crlf_line_endings_are_stripped(self):
        with open(default_words_path(), 'rb') as f:
            if b'\r\n' not in f.read():
                self.skipTest('this copy of words.txt does not use CRLF line endings')
        self.assertEqual(self.anagrams.get_anagrams('Aarhus'), ['Aarhus'])
        self.assertEqual(self.anagrams.get_anagrams('Zurich'), ['Zurich'])

    def test_non_string_query_raises_type_error(self):
        for query in (None, 42, b'eat', ['eat']):
            with self.subTest(query=query), self.assertRaises(TypeError):
                self.anagrams.get_anagrams(query)

    def test_every_listed_word(self):
        self.assertMatchesOracle((word, group) for group in self.oracle.values() for word in group)

    def test_scrambled_copy_of_every_listed_word(self):
        self.assertMatchesOracle((word[::-1].swapcase(), group)
                                 for group in self.oracle.values() for word in group)

    def test_random_queries_and_near_misses(self):
        queries = self.make_queries(self.words, 1000, seed=1)
        self.assertMatchesOracle((query, self.oracle.get(self.letter_counts(query.strip()), []))
                                 for query in queries)

    def test_line_endings_blank_lines_and_padding(self):
        path = self.write_word_file(b'listen\r\nsilent\n\r\n  enlist\t\r\n\n \nTinsel\rinlets')
        anagrams = Anagrams(path)
        self.assertEqual(anagrams.get_anagrams('inlets'),
                         ['enlist', 'inlets', 'listen', 'silent', 'Tinsel'])
        self.assertEqual(anagrams.get_anagrams(' '), [])

    def test_only_line_ends_separate_words(self):
        anagrams = Anagrams(self.write_word_file(b'ab\x0ccd\nef\x1cgh\nice cream\n'))
        self.assertEqual(anagrams.get_anagrams('ab\x0ccd'), ['ab\x0ccd'])
        self.assertEqual(anagrams.get_anagrams('gh'), [])
        self.assertEqual(anagrams.get_anagrams('cream ice'), ['ice cream'])

    def test_repeated_lines_are_returned_once(self):
        anagrams = Anagrams(self.write_word_file(b'eat\ntea\neat\nEAT\n'))
        self.assertEqual(anagrams.get_anagrams('tea'), ['EAT', 'eat', 'tea'])

    def test_empty_file(self):
        self.assertEqual(Anagrams(self.write_word_file(b'')).get_anagrams('eat'), [])

    def test_byte_order_mark_is_not_part_of_the_first_word(self):
        anagrams = Anagrams(self.write_word_file(b'\xef\xbb\xbfeat\r\ntea\r\n'))
        self.assertEqual(anagrams.get_anagrams('tea'), ['eat', 'tea'])

    def test_non_ascii_words_are_compared_by_character(self):
        anagrams = Anagrams(self.write_word_file('café\néfac\nface\néī\nëĩ\n'.encode('utf-8')))
        self.assertEqual(anagrams.get_anagrams('CAFÉ'), ['café', 'éfac'])
        self.assertEqual(anagrams.get_anagrams('face'), ['face'])
        # 'e' plus a combining accent is two characters, not the one in 'café'.
        self.assertEqual(anagrams.get_anagrams('café'), [])
        # é+ī and ë+ĩ share their four UTF-8 bytes; comparing bytes would match them.
        self.assertEqual(anagrams.get_anagrams('īé'), ['éī'])
        self.assertEqual(anagrams.get_anagrams('ëĩ'), ['ëĩ'])

    def test_case_is_ignored_beyond_ascii(self):
        # casefold(), unlike lower(), treats final and medial sigma as one letter.
        anagrams = Anagrams(self.write_word_file('ΑΣ\nσα\n'.encode('utf-8')))
        self.assertEqual(anagrams.get_anagrams('ας'), ['ΑΣ', 'σα'])

    def test_each_call_returns_a_new_list(self):
        anagrams = Anagrams(self.write_word_file(b'eat\ntea\n'))
        self.assertIsNot(anagrams.get_anagrams('eat'), anagrams.get_anagrams('eat'))
        # Changing a result changes no later one: listed, unlisted, no match.
        for query, expected in (('eat', ['eat', 'tea']), ('ATE', ['eat', 'tea']), ('xyz', [])):
            with self.subTest(query=query):
                anagrams.get_anagrams(query).append('junk')
                self.assertEqual(anagrams.get_anagrams(query), expected)

    def test_instances_do_not_share_words(self):
        first = Anagrams(self.write_word_file(b'eat\ntea\n'))
        second = Anagrams(self.write_word_file(b'ate\nlisten\n'))
        self.assertEqual(first.get_anagrams('ate'), ['eat', 'tea'])
        self.assertEqual(second.get_anagrams('ate'), ['ate'])
        self.assertEqual(first.get_anagrams('silent'), [])

    def test_missing_file_raises_file_not_found_error(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(FileNotFoundError):
            Anagrams(os.path.join(tmp, 'missing.txt'))

    def test_default_word_file_is_the_one_in_the_working_directory(self):
        path = self.write_word_file(b'eat\ntea\n')
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(os.path.dirname(path))
        self.assertEqual(Anagrams().get_anagrams('ate'), ['eat', 'tea'])

    def test_default_word_file_is_found_from_any_working_directory(self):
        # Unlike the template: with no words.txt in the working directory, the
        # one next to this file is used.
        if not os.path.isfile(os.path.join(MODULE_DIR, 'words.txt')):
            self.skipTest('there is no words.txt next to anagrams.py')
        empty = tempfile.TemporaryDirectory()
        self.addCleanup(empty.cleanup)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(empty.name)
        self.assertEqual(Anagrams().get_anagrams('eat'), ['ate', 'eat', 'tea'])

    def test_concurrent_queries_give_the_same_results_as_sequential_ones(self):
        hot = ['eat', 'plates']
        queries = self.make_queries(self.words, 150, seed=2) + hot
        expected = {query: self.anagrams.get_anagrams(query) for query in queries}

        def worker(i):
            wrong = []
            for query in hot * 250 + random.Random(i).sample(queries, len(queries)):
                result = anagrams.get_anagrams(query)
                if result != expected[query]:
                    wrong.append((query, result))
                result.append('junk')
            return wrong

        for threads, interval in ((32, None), (32, None), (32, None), (8, 1e-6)):
            anagrams = Anagrams()  # new, so its first use happens in all threads at once
            with self.subTest(threads=threads, switch_interval=interval):
                results = self.run_in_threads(worker, threads, interval)
                wrong = [item for items in results for item in items]
                self.assertEqual(wrong[:3], [], f'{len(wrong)} wrong results')

    def test_instances_built_concurrently_keep_their_own_words(self):
        markers = [f'marker{i}' for i in range(4)]
        paths = [self.write_word_file('\n'.join(self.words[i::200] + [marker]).encode('utf-8'))
                 for i, marker in enumerate(markers)]

        def worker(i):
            anagrams = Anagrams(paths[i])
            return [anagrams.get_anagrams(marker) for marker in markers]

        for i, found in enumerate(self.run_in_threads(worker, len(markers), switch_interval=1e-6)):
            self.assertEqual(found, [[m] if j == i else [] for j, m in enumerate(markers)])

    
    @staticmethod
    def letter_counts(word):
        """The tests' own definition of an anagram: the same characters, each
        used as often, ignoring case."""
        return frozenset(Counter(word.casefold()).items())

    @staticmethod
    def make_queries(words, count, seed):
        """Five queries per sampled word: the word, a shuffled re-cased padded
        copy, and near misses with a letter repeated, removed and replaced."""
        rng = random.Random(seed)
        queries = []
        for word in rng.sample(words, count):
            letters = [c.upper() if rng.random() < 0.5 else c.lower() for c in word]
            rng.shuffle(letters)
            i = rng.randrange(len(word))
            other_letters = 'abcdefghijklmnopqrstuvwxyz'.replace(word[i].lower(), '')
            queries += [
                word,
                ' ' + ''.join(letters) + '\t',
                word + word[i],
                word[:i] + word[i + 1:],
                word[:i] + rng.choice(other_letters) + word[i + 1:],
            ]
        return queries

    def write_word_file(self, data):
        """Writes bytes (exact line endings on every OS) to words.txt in a new
        temporary directory and returns its path."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, 'words.txt')
        with open(path, 'wb') as f:
            f.write(data)
        return path

    def run_in_threads(self, worker, threads, switch_interval=None):
        """Runs worker(0) ... worker(threads - 1) in threads started together;
        returns their results and re-raises any exception. CPython switches
        threads every 5 ms by default, so without a tiny switch_interval the
        threads would just run one after another."""
        barrier = threading.Barrier(threads, timeout=10)

        def start(i):
            barrier.wait()
            return worker(i)

        old_interval = sys.getswitchinterval()
        if switch_interval is not None:
            sys.setswitchinterval(switch_interval)
        try:
            with ThreadPoolExecutor(max_workers=threads) as pool:
                return list(pool.map(start, range(threads)))
        finally:
            sys.setswitchinterval(old_interval)

    def assertMatchesOracle(self, cases):
        """cases: (query, expected) pairs. Reports how many were wrong and the
        first three."""
        wrong = []
        total = 0
        for query, expected in cases:
            total += 1
            result = self.anagrams.get_anagrams(query)
            if result != expected:
                wrong.append((query, result, expected))
        self.assertEqual(wrong[:3], [], f'{len(wrong)} of {total} queries were wrong')


if __name__ == '__main__':
    unittest.main()
