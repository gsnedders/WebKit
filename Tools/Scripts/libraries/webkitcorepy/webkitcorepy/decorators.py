# Copyright (C) 2020 Apple Inc. All rights reserved.
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

import functools
import time
from collections.abc import Hashable
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    TypeVar,
    overload,
)

if TYPE_CHECKING:
    from typing_extensions import (
        Concatenate,
        ParamSpec,
    )


_T = TypeVar("_T")
_R_co = TypeVar("_R_co", covariant=True)
if TYPE_CHECKING:
    _P = ParamSpec("_P")
else:
    _P = TypeVar("_P")


class _MemoizedFunction(Generic[_R_co]):
    def __init__(self, function: Callable[..., _R_co], memoize: Memoize) -> None:
        self._function = function
        self._memoize = memoize
        self._cache: dict[tuple[Hashable, ...], _R_co] = {}
        self._last_called: dict[tuple[Hashable, ...], float] = {}
        functools.update_wrapper(self, function)

    def __call__(self, *args: Any, **kwargs: Any) -> _R_co:
        fargs = self._function.__code__.co_varnames[:self._function.__code__.co_argcount]

        timeout = self._memoize.timeout
        if 'timeout' not in fargs:
            timeout = kwargs.pop('timeout', timeout)

        cached = self._memoize.cached
        if 'cached' not in fargs:
            cached = kwargs.pop('cached', cached)

        keyargs = args + tuple(sorted([(key, value) for key, value in kwargs.items()]))
        last_called = self._last_called.get(keyargs, 0)
        is_cached = keyargs in self._cache
        if not cached:
            is_cached = False
        if timeout and timeout < time.time() - last_called:
            is_cached = False
        if is_cached:
            return self._cache[keyargs]

        value = self._function(*args, **kwargs)
        self._last_called[keyargs] = time.time()
        self._cache[keyargs] = value
        return value

    def clear(self) -> None:
        self._cache = {}
        self._last_called = {}


class Memoize:
    def __init__(self, timeout: float | None=None, cached: bool=True) -> None:
        self.timeout = timeout
        self.cached = cached
        self._functions: list[_MemoizedFunction[object]] = []

    def __call__(self, function: Callable[..., _R_co]) -> _MemoizedFunction[_R_co]:
        memoized = _MemoizedFunction(function, self)
        self._functions.append(memoized)
        return memoized

    def clear(self) -> None:
        for func in self._functions:
            func.clear()


class _BoundHybridMethod(Generic[_T, _P, _R_co]):
    def __init__(
        self, func: Callable[Concatenate[type[_T] | _T, _P], _R_co], self_or_cls: type[_T] | _T
    ) -> None:
        self.__func__ = func
        self.__self__ = self_or_cls
        functools.update_wrapper(self, func)

    def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _R_co:
        return self.__func__(self.__self__, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.__func__, name)


class hybridmethod(Generic[_T, _P, _R_co]):
    def __init__(self, function: Callable[Concatenate[type[_T] | _T, _P], _R_co]) -> None:
        self.function = function

    @overload
    def __get__(self, instance: None, owner: type[_T]) -> _BoundHybridMethod[_T, _P, _R_co]: ...
    @overload
    def __get__(self, instance: _T, owner: type[_T]) -> _BoundHybridMethod[_T, _P, _R_co]: ...
    def __get__(self, instance: _T | None, owner: type[_T]) -> _BoundHybridMethod[_T, _P, _R_co]:
        if instance is None:
            return _BoundHybridMethod(self.function, owner)
        return _BoundHybridMethod(self.function, instance)
