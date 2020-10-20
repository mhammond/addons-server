import re
from functools import total_ordering

from django.utils.encoding import force_text


BIGINT_POSITIVE_MAX = 2 ** 63 - 1
MAX_VERSION_PART = 2 ** 16 - 1

version_re = re.compile(r"""(?P<major>\d+|\*)      # major (x in x.y)
                            \.?(?P<minor1>\d+|\*)? # minor1 (y in x.y)
                            \.?(?P<minor2>\d+|\*)? # minor2 (z in x.y.z)
                            \.?(?P<minor3>\d+|\*)? # minor3 (w in x.y.z.w)
                            (?P<alpha>[a|b]?)      # alpha/beta
                            (?P<alpha_ver>\d*)     # alpha/beta version
                            (?P<pre>pre)?          # pre release
                            (?P<pre_ver>\d)?       # pre release version
                        """,
                        re.VERBOSE)

LETTERS = ['alpha', 'pre']
NUMBERS = ['major', 'minor1', 'minor2', 'minor3', 'alpha_ver', 'pre_ver']
ASTERISK = '*'


def version_dict(version, asterisk_value=MAX_VERSION_PART):
    """Turn a version string into a dict with major/minor/... info."""
    match = version_re.match(version or '')

    if match:
        vdict = match.groupdict()
        for letter in LETTERS:
            vdict[letter] = vdict[letter] if vdict[letter] else None
        for num in NUMBERS:
            if vdict[num] == ASTERISK:
                vdict[num] = asterisk_value
            else:
                vdict[num] = int(vdict[num]) if vdict[num] else None
    else:
        vdict = {number_part: None for number_part in NUMBERS}
        vdict.update((letter_part, None) for letter_part in LETTERS)
    return vdict


@total_ordering
class VersionString():
    string = ''
    full_dict = {}

    def __init__(self, string):
        self.string = force_text(string)
        vdict = version_dict(self.string, ASTERISK)
        self.full_dict = self._fill_vdict(vdict)

    def _fill_vdict(self, vdict):
        last_part_value = None
        for part in NUMBERS:
            part_value = vdict[part]
            # reset last_part_value once we get to the alpha/pre parts
            if part in ('alpha_ver', 'pre_ver'):
                last_part_value = None
            if part_value is None:
                # if the part was missing it's 0, unless the last part was *;
                # then it inherits the * and is max value.
                vdict[part] = ASTERISK if last_part_value == ASTERISK else 0
            else:
                last_part_value = part_value
        for part in LETTERS:
            vdict[part] = vdict[part] or ''
        return vdict

    @classmethod
    def _cmp_part(cls, part_a, part_b):
        if part_a == ASTERISK and part_b != ASTERISK:
            return 1
        elif part_b == ASTERISK and part_a != ASTERISK:
            return -1
        return 0 if part_a == part_b else 1 if part_a > part_b else -1

    def __eq__(self, other):
        for part, value in self.full_dict.items():
            cmp = self._cmp_part(value, other.full_dict[part])
            if cmp == 0:
                continue
            else:
                return False
        return True

    def __gt__(self, other):
        for part, value in self.full_dict.items():
            other_value = other.full_dict[part]
            if part in LETTERS:
                cmp = self._cmp_part(value or 'z', other_value or 'z')
            else:
                cmp = self._cmp_part(value, other_value)
            if cmp == 0:
                continue
            else:
                return cmp == 1
        return False

    def __str__(self):
        return self.string


def version_int(version):
    """This is used for converting an app version's version string into a
    single number for comparison.  To maintain compatibility the minor parts
    are limited to 99 making it unsuitable for comparing addon version strings.
    """
    vstr = VersionString(version)
    vdict = dict(vstr.full_dict)
    for part in NUMBERS:
        max_num = MAX_VERSION_PART if part == 'major' else 99
        number = vdict[part]
        vdict[part] = max_num if number == ASTERISK else min(number, max_num)
    vdict['alpha'] = {'a': 0, 'b': 1}.get(vdict['alpha'], 2)
    vdict['pre'] = 0 if vdict['pre'] else 1

    vint = '%d%02d%02d%02d%d%02d%d%02d' % (
        vdict['major'], vdict['minor1'], vdict['minor2'], vdict['minor3'],
        vdict['alpha'], vdict['alpha_ver'], vdict['pre'], vdict['pre_ver'])
    return min(int(vint), BIGINT_POSITIVE_MAX)
