# Copyright (C) 2021 Apple Inc. All rights reserved.
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

from collections.abc import Iterator, MutableMapping
from typing import TypeVar, overload

VT = TypeVar("VT")
_T = TypeVar("_T")


class AmbiguousKeyError(KeyError):
    """Raised when a key matches multiple entries in the NestedFuzzyDict."""

    pass


class NestedFuzzyDict(MutableMapping[str, VT]):
    @classmethod
    def assert_valid_key(cls, key: object) -> None:
        if not isinstance(key, str):
            raise ValueError(f"'{type(key)}' is not a valid key for a NestedDict")

    def __init__(self, primary_size: int | None = None, **kwargs: VT) -> None:
        self.primary_size = int(primary_size or 6)
        self._data: dict[str, dict[str, VT]] = dict()
        self.update(dict(**kwargs))

    def __getitem__(self, keyname: str) -> VT:
        self.assert_valid_key(keyname)
        key_a, key_b = keyname[: self.primary_size], keyname[self.primary_size :]
        found = False
        for key, result in self._data.get(key_a, dict()).items():
            if key.startswith(key_b):
                if found:
                    raise AmbiguousKeyError(f"Multiple values match '{keyname}'")
                found = True
                value = result
        if found:
            return value
        else:
            raise KeyError(keyname)

    @overload
    def get(self, keyname: str) -> VT | None: ...
    @overload
    def get(self, keyname: str, default: VT | _T) -> VT | _T: ...
    def get(self, keyname: str, default: VT | _T | None = None) -> VT | _T | None:
        try:
            return self[keyname]
        except AmbiguousKeyError:
            raise
        except KeyError:
            return default

    def __setitem__(self, key: str, value: VT) -> None:
        self.assert_valid_key(key)
        key_a, key_b = key[: self.primary_size], key[self.primary_size :]
        self._data.setdefault(key_a, {})[key_b] = value

    def __delitem__(self, keyname: str) -> None:
        self.assert_valid_key(keyname)
        key_a, key_b = keyname[: self.primary_size], keyname[self.primary_size :]
        to_remove = []
        for key, result in self._data.get(key_a, dict()).items():
            if key.startswith(key_b):
                to_remove.append(key)
        if not to_remove:
            raise KeyError(keyname)
        for key in to_remove:
            del self._data[key_a][key]
        if not self._data.get(key_a, True):
            del self._data[key_a]

    def __contains__(self, keyname: object) -> bool:
        if not isinstance(keyname, str):
            return False
        key_a, key_b = keyname[: self.primary_size], keyname[self.primary_size :]
        for key, result in self._data.get(key_a, dict()).items():
            if key.startswith(key_b):
                return True
        return False

    def __len__(self) -> int:
        return sum([len(values) for values in self._data.values()])

    def __iter__(self) -> Iterator[str]:
        for key_a, values in self._data.items():
            for key_b in values.keys():
                yield key_a + key_b

    def dict(self) -> dict[str, VT]:
        result = dict()
        for key, value in self.items():
            result[key] = value
        return result

    def __repr__(self) -> str:
        return self.dict().__repr__()

    def __str__(self) -> str:
        return self.dict().__str__()
