# Copyright (C) 2021 Apple Inc. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1.  Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
# 2.  Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY APPLE INC. AND ITS CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL APPLE INC. OR ITS CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar, cast

_T = TypeVar("_T")


class CallByNeed(Generic[_T]):
    def __init__(self, callback: Callable[[], _T], type: type[_T] | None = None) -> None:
        self._callback: Callable[[], _T] | None = callback
        self._value: _T | None = None
        self.type = type

    def __getattr__(self, name: str) -> Any:
        if self.type is not None and name not in dir(self.type):
            raise AttributeError("'{}' object has no attribute '{}'".format(self.type.__name__, name))
        return getattr(self.value, name)

    @property
    def value(self) -> _T:
        cb = self._callback
        if cb is not None:
            self._callback = None
            result = cb()
            self._value = result
            return result
        return cast(_T, self._value)

    def __call__(self, *args: Any, **kwargs: Any) -> _T:
        val = self.value
        if callable(val):
            return cast(_T, val(*args, **kwargs))
        return val

    def __repr__(self) -> str:
        return self.value.__repr__()

    def __str__(self) -> str:
        return str(self.value)
