# Copyright (C) 2020 Apple Inc. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1.  Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2.  Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY APPLE INC. AND ITS CONTRIBUTORS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL APPLE INC. OR ITS CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
from __future__ import annotations

import re
from typing import Iterable, Iterator


class Version(object):
    MATCHES_RE = re.compile(r'(?P<operator>==|!=|>|<|>=|<=)? *(?P<version>\d+(\.\d+)?(\.\d+)?(\.\*)?)')

    @classmethod
    def from_string(cls, string: str) -> "Version":
        if not isinstance(string, str):
            raise TypeError('Version.from_string requires a str')

        # We want this outside of the try statement so it can raise its own TypeError.
        split = string.split('.')

        try:
            return cls(*split)
        except TypeError:
            # This occurs when we have too many arguments.
            raise ValueError("Invalid version string") from None

    @classmethod
    def from_iterable(cls, val: Iterable[int | str]) -> "Version":
        try:
            return cls(*val)
        except TypeError:
            # This occurs when we have too many arguments.
            raise ValueError("Too many iterable items") from None

    @staticmethod
    def from_name(name: str) -> "Version":
        from webkitpy.common.version_name_map import VersionNameMap
        result = VersionNameMap.map().from_name(name)[1]
        assert isinstance(result, Version)
        return result

    def __init__(
        self,
        major: int | str = 0,
        minor: int | str = 0,
        tiny: int | str = 0,
        micro: int | str = 0,
        nano: int | str = 0,
    ) -> None:
        self.major = int(major)
        self.minor = int(minor)
        self.tiny = int(tiny)
        self.micro = int(micro)
        self.nano = int(nano)

    def __len__(self) -> int:
        return 5

    def __iter__(self) -> Iterator[int]:
        yield self.major
        yield self.minor
        yield self.tiny
        yield self.micro
        yield self.nano

    def __getitem__(self, key: int | str) -> int:
        if isinstance(key, int):
            if key == 0:
                return self.major
            elif key == 1:
                return self.minor
            elif key == 2:
                return self.tiny
            elif key == 3:
                return self.micro
            elif key == 4:
                return self.nano
            raise IndexError('Version key must be between 0 and 4')
        elif isinstance(key, str):
            if key in ('major', 'minor', 'tiny', 'micro', 'nano'):
                result = getattr(self, key)
                assert isinstance(result, int)
                return result
            raise KeyError('Version key must be major, minor, tiny, micro or nano')
        raise TypeError('Expected version key to be string or integer')

    def __setitem__(self, key: int | str, value: int | str) -> None:
        if isinstance(key, int):
            if key == 0:
                self.major = int(value)
                return
            elif key == 1:
                self.minor = int(value)
                return
            elif key == 2:
                self.tiny = int(value)
                return
            elif key == 3:
                self.micro = int(value)
                return
            elif key == 4:
                self.nano = int(value)
                return
            raise IndexError('Version key must be between 0 and 4')
        elif isinstance(key, str):
            if key in ('major', 'minor', 'tiny', 'micro', 'nano'):
                setattr(self, key, value)
                return
            raise KeyError('Version key must be major, minor, tiny, micro or nano')
        raise TypeError('Expected version key to be string or integer')

    def matches(self, expressions: str) -> bool:
        does_match = None
        for expression in expressions.split(','):
            match = self.MATCHES_RE.search(expression)
            if not match:
                continue
            operator = match.group('operator') or '=='
            if operator in ['==', '!=']:
                version_match = True
                split = match.group('version').split('.')
                for index in range(len(split)):
                    if '*' == split[index]:
                        continue
                    if str(self[index]) != split[index]:
                        version_match = False
                        break

                if operator == '==':
                    does_match = (does_match or False) | version_match
                if version_match and operator == '!=':
                    return False
                continue

            version = self.from_string(match.group('version').replace('*', '0'))
            does_match = (does_match or False) | {
                '>': lambda a, b: a > b,
                '<': lambda a, b: a < b,
                '>=': lambda a, b: a >= b,
                '<=': lambda a, b: a <= b,
            }[operator](self, version)

        return True if does_match is None else does_match

    def _strip_zeros(self) -> list[int]:
        """Return the version components as a list with trailing zero components removed.

        Iterates from the end of the component list and records how many consecutive
        zeros appear before the first non-zero value (i), then slices them off.

        Examples:
            Version(1, 2, 3)       -> [1, 2, 3]   (no trailing zeros)
            Version(1, 2, 0)       -> [1, 2]       (one trailing zero stripped)
            Version(1, 2, 0, 0, 0) -> [1, 2]       (three trailing zeros stripped)
            Version(0, 0, 3)       -> [0, 0, 3]    (leading zeros preserved)
            Version(1, 0, 0, 0, 3) -> [1, 0, 0, 0, 3]  (no trailing zeros, nano is non-zero)
        """
        parts = list(self)
        for i, part in enumerate(reversed(parts)):
            if part != 0:
                break
        return parts[:len(parts) - i]

    # 11.2 is in 11, but 11 is not in 11.2
    def __contains__(self, version: object) -> bool:
        if not isinstance(version, Version):
            raise TypeError('__contains__ requires a Version')
        stripped = tuple(self._strip_zeros())
        other: tuple[int, ...] = tuple(version)[:len(stripped)]
        return stripped == other

    def __str__(self) -> str:
        parts = self._strip_zeros()
        return '.'.join(map(str, parts))

    def __repr__(self) -> str:
        parts = self._strip_zeros()
        return f'Version({", ".join(map(str, parts))})'

    def __hash__(self) -> int:
        return hash(tuple(self))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return tuple(self) == tuple(other)

    def __lt__(self, other: object) -> bool:
        if other is None:
            return False
        if not isinstance(other, Iterable):
            return NotImplemented
        try:
            return tuple(self) < tuple(other)
        except TypeError:
            return NotImplemented

    def __le__(self, other: object) -> bool:
        if other is None:
            return False
        if not isinstance(other, Iterable):
            return NotImplemented
        try:
            return tuple(self) <= tuple(other)
        except TypeError:
            return NotImplemented

    def __gt__(self, other: object) -> bool:
        if other is None:
            return True
        if not isinstance(other, Iterable):
            return NotImplemented
        try:
            return tuple(self) > tuple(other)
        except TypeError:
            return NotImplemented

    def __ge__(self, other: object) -> bool:
        if other is None:
            return True
        if not isinstance(other, Iterable):
            return NotImplemented
        try:
            return tuple(self) >= tuple(other)
        except TypeError:
            return NotImplemented
