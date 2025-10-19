# Copyright (C) 2020-2022 Apple Inc. All rights reserved.
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
from functools import cmp_to_key
from typing import Any, Callable, overload
from unittest.mock import patch

import webkitcorepy.string_utils as string_utils
from webkitcorepy.mocks import ContextStack
from webkitcorepy.string_utils import unicode


class ProcessCompletion(object):
    def __init__(self, returncode: int | None = None, stdout: str | None = None, stderr: str | None = None, elapsed: int=0) -> None:
        self.returncode = 1 if returncode is None else returncode
        self.stdout = string_utils.encode(stdout) if stdout else b''
        self.stderr = string_utils.encode(stderr) if stderr else b''
        self.elapsed = elapsed


class Subprocess(ContextStack):
    """
    Organize ProcessCompletions so calls to subprocess functions will return a ProcessCompletion for
    a set of arguments or trigger a ProcessCompletion generator. mocks.Subprocess makes an attempt to
    prioritize CommandRoute objects for a given set of arguments such that the most specific applicable route
    is prefered.

    Example usage mocking a single command:
        with mocks.Subprocess(
            'ls', completion=mocks.ProcessCompletion(returncode=0, stdout='file1.txt\nfile2.txt\n'),
        ):
            result = run(['ls'], capture_output=True, encoding='utf-8')
            assert result.returncode == 0
            assert result.stdout == 'file1.txt\nfile2.txt\n'

    Example usage mocking a set of commands:
        with mocks.Subprocess(
            mocks.Subprocess.CommandRoute('command-a', 'argument', completion=mocks.ProcessCompletion(returncode=0)),
            mocks.Subprocess.CommandRoute('command-b', completion=mocks.ProcessCompletion(returncode=-1)),
        ):
            result = run(['command-a', 'argument'])
            assert result.returncode == 0

            result = run(['command-b'])
            assert result.returncode == -1
    """
    top = None

    class CommandRoute(object):
        def __init__(self, *args: str | None, completion: ProcessCompletion | None = None, cwd: str | None = None, input: str | None = None, env: dict[str, str] | None = None, generator: "Callable[..., ProcessCompletion] | None" = None) -> None:
            if isinstance(args, str) or isinstance(args, unicode):
                self.args: tuple[str | None, ...] = (args,)
            elif not args:
                raise ValueError('Arguments must be provided to a CommandRoute')
            else:
                self.args = args

            self.generator: Callable[..., ProcessCompletion] = generator or (lambda *args, **kwargs: completion or ProcessCompletion())
            self.cwd = cwd
            self.input = string_utils.encode(input) if input else None
            self.env = env

        def matches(self, *args: str, cwd: str | None = None, input: bytes | None = None, env: dict[str, str] | None = None) -> bool:
            if len(self.args) > len(args):
                return False

            for count in range(len(self.args)):
                arg = self.args[count]
                if arg is None:
                    return False

                if arg == args[count]:
                    continue
                elif hasattr(arg, 'match') and arg.match(args[count]):
                    continue
                elif re.match(arg, args[count]):
                    continue
                elif not count and arg.split('/')[-1] == args[count]:
                    continue
                return False

            if self.cwd is not None and cwd != self.cwd:
                return False
            if self.input is not None and input != self.input:
                return False
            if self.env is not None and env != self.env:
                return False
            return True

        def __call__(self, *args: str, cwd: str | None = None, input: bytes | None = None, env: dict[str, str] | None = None) -> ProcessCompletion:
            return self.generator(*args, cwd=cwd, input=input, env=env)

        @classmethod
        def compare(cls, a: "Subprocess.CommandRoute", b: "Subprocess.CommandRoute") -> int:
            for candidate in [
                len(b.args) - len(a.args),
                0 if type(a.cwd) == type(b.cwd) else -1 if a.cwd else 1,
                0 if type(a.input) == type(b.input) else -1 if a.input else 1,
            ]:
                if candidate:
                    return candidate
            return 0

    Route = CommandRoute

    @classmethod
    def completion_generator_for(cls, program: str) -> "list[Subprocess.CommandRoute]":
        current = cls.top
        candidates: list[Subprocess.CommandRoute] = []
        while current:
            for completion in current.completions:
                if completion.args[0] == program or completion.args[0].split('/')[-1] == program:
                    candidates.append(completion)
                if current.ordered:
                    break
            current = current.previous

        if candidates:
            return candidates

        raise FileNotFoundError("No such file or directory: '{path}': '{path}'".format(path=program))

    @classmethod
    def completion_for(cls, *args: str, cwd: str | None = None, input: bytes | None = None, env: dict[str, str] | None = None) -> ProcessCompletion:
        candidates = [
            candidate for candidate in cls.completion_generator_for(args[0]) if candidate.matches(*args, cwd=cwd, input=input, env=env)
        ]
        if not candidates:
            raise AssertionError('Provided arguments to {} do not match a provided completion'.format(args[0]))

        completion = candidates[0]
        current = cls.top
        while current:
            if current.ordered and completion is current.completions[0]:
                current.completions.pop(0)
                break
            current = current.previous
        return completion(*args, cwd=cwd, input=input, env=env)

    @overload
    def __init__(self, *args: "Subprocess.CommandRoute", ordered: bool = ...) -> None: ...
    @overload
    def __init__(self, *args: str, completion: ProcessCompletion | None = ..., cwd: str | None = ..., input: str | None = ..., env: "dict[str, str] | None" = ..., generator: "Callable[..., ProcessCompletion] | None" = ...) -> None: ...
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if all([isinstance(arg, self.CommandRoute) for arg in args]):
            self.ordered = kwargs.pop('ordered', False)
            if kwargs:
                raise TypeError('__init__() got an unexpected keyword argument {}'.format(next(iter(kwargs))))
            self.completions: list[Subprocess.CommandRoute] = list(args) if self.ordered else sorted(args, key=cmp_to_key(self.CommandRoute.compare))
        elif any([isinstance(arg, self.CommandRoute) for arg in args]):
            raise TypeError('mocks.Subprocess arguments must be of a consistent type')
        else:
            self.ordered = False
            self.completions = [self.CommandRoute(*args, **kwargs)]

        super(Subprocess, self).__init__(cls=Subprocess)

        from webkitcorepy.mocks.popen import Popen
        self.patches.append(patch('subprocess.Popen', new=Popen))
