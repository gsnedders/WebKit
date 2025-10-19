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

import io
import logging
import os
import signal
import subprocess
import sys
import time
from typing import Any, Callable, IO, Sequence
from types import TracebackType

from webkitcorepy import TimeoutExpired, string_utils
from webkitcorepy.mocks import Subprocess
from webkitcorepy.mocks.subprocess import ProcessCompletion

log = logging.getLogger('webkitcorepy')


# This file is mocked version of the subprocess.Popen object. This object differs slightly between Python 2 and 3.
# This object is not a complete mock of subprocess.Popen, but it does enable thorough testing of code which uses Popen,
# in particular, the subprocess.check_call, subprocess.check_output and subprocess.run commands.
#
# If you find yourself needing to edit this file, lean heavily on the testing in
# webkitcorepy.tests.mocks.subprocess_unittest and Python's implementation of Popen.


class PopenBase(object):
    NEXT_PID = os.getpid() + 1
    SIGTERM = getattr(signal, 'SIGTERM', 1)
    SIGKILL = getattr(signal, 'SIGKILL', 2)

    def __init__(self, args: Sequence[str], bufsize: int | None=None, cwd: str | None = None, env: dict[str, str] | None = None, stdin: None | int | IO[bytes] = None, stdout: None | int | IO[bytes] = None, stderr: None | int | IO[bytes] = None) -> None:
        self._completion: ProcessCompletion | None = None
        self._communication_started = False
        if bufsize is None:
            bufsize = -1
        if not isinstance(bufsize, int):
            raise TypeError("bufsize must be an integer")

        self._args = args
        self._cwd = cwd
        self._env = env or dict()

        self.returncode: int | None = None

        if stdin is None or stdin == subprocess.PIPE or stdin == 0:
            self.stdin: IO[Any] = string_utils.BytesIO()
        elif isinstance(stdin, int):
            raise TypeError("Mock Popen does not support file descriptor {} for stdin".format(stdin))
        else:
            self.stdin = stdin

        if stdout == subprocess.PIPE:
            self.stdout: IO[Any] | None = string_utils.BytesIO()
            self._stdout_type: type[bytes] | type[str] = bytes
            self._stdout_devnull = False
        elif stdout is None or stdout == subprocess.DEVNULL or stdout == 1:
            self.stdout = None
            self._stdout_type = str
            self._stdout_devnull = (stdout == subprocess.DEVNULL)
        elif isinstance(stdout, int):
            raise TypeError("Mock Popen does not support file descriptor {} for stdout".format(stdout))
        else:
            self.stdout = stdout
            self._stdout_type = str
            self._stdout_devnull = False

        if stderr == subprocess.STDOUT or stderr == 1:
            self.stderr: IO[Any] | None = self.stdout
            self._stderr_type: type[bytes] | type[str] = self._stdout_type
            self._stderr_devnull = self._stdout_devnull
        elif stderr == subprocess.PIPE:
            self.stderr = string_utils.BytesIO()
            self._stderr_type = bytes
            self._stderr_devnull = False
        elif stderr is None or stderr == subprocess.DEVNULL or stderr == 2:
            self.stderr = None
            self._stderr_type = str
            self._stderr_devnull = (stderr == subprocess.DEVNULL)
        elif isinstance(stderr, int):
            raise TypeError("Mock Popen does not support file descriptor {} for stderr".format(stderr))
        else:
            self.stderr = stderr
            self._stderr_type = str
            self._stderr_devnull = False

        Subprocess.completion_generator_for(args[0])

        self.pid = self.NEXT_PID
        self.NEXT_PID += 1

        self._start_time = time.time()

    @property
    def universal_newlines(self) -> bool:
        return self.text_mode

    @universal_newlines.setter
    def universal_newlines(self, universal_newlines: bool) -> None:
        self.text_mode = bool(universal_newlines)

    def poll(self) -> int | None:
        if not self._completion:
            self.stdin.seek(0)
            self._completion = Subprocess.completion_for(*self._args, cwd=self._cwd, env=self._env, input=self.stdin.read())

            if not self._stdout_devnull:
                stdout_data = string_utils.decode(self._completion.stdout, target_type=self._stdout_type)
                stream = self.stdout or sys.stdout
                stream.write(stdout_data)  # type: ignore[arg-type]
                stream.flush()

            if not self._stderr_devnull:
                stderr_data = string_utils.decode(self._completion.stderr, target_type=self._stderr_type)
                stream = self.stderr or sys.stderr
                stream.write(stderr_data)  # type: ignore[arg-type]
                stream.flush()

            if self.stdout:
                self.stdout.seek(0)
            if self.stderr:
                self.stderr.seek(0)

        assert self._completion is not None
        if self.returncode is not None and time.time() >= self._start_time + self._completion.elapsed:
            self.returncode = self._completion.returncode

        return self.returncode

    def send_signal(self, sig: int) -> None:
        if self.returncode is not None:
            return

        if sig not in [self.SIGTERM, self.SIGKILL]:
            raise ValueError('Mock Popen object cannot handle signal {}'.format(sig))
        log.critical('Mock process {} send signal {}'.format(self.pid, sig))
        self.returncode = -1

    def terminate(self) -> None:
        self.send_signal(self.SIGTERM)

    def kill(self) -> None:
        self.send_signal(self.SIGKILL)


class Popen(PopenBase):
    def __init__(self, args: Sequence[str], bufsize: int | None=None, executable: str | None = None,
                 stdin: None | int | IO[bytes] = None, stdout: None | int | IO[bytes] = None, stderr: None | int | IO[bytes] = None,
                 preexec_fn: Callable[[], object] | None = None, close_fds: bool=True,
                 shell: bool=False, cwd: str | None = None, env: dict[str, str] | None = None, universal_newlines: bool | None = None,
                 startupinfo: object | None = None, creationflags: int=0,
                 restore_signals: bool=True, start_new_session: bool=False,
                 pass_fds: Sequence[int] = (), encoding: str | None = None, errors: str | None = None, text: str | None=None) -> None:

        str_args = []
        for arg in args:
            if not isinstance(arg, (str, bytes, os.PathLike)):
                raise TypeError(
                    'expected {}, {} or os.PathLike object, not {}',
                    str, bytes, type(arg),
                )
            str_args.append(str(arg))
        args = str_args

        super(Popen, self).__init__(args, bufsize=bufsize, cwd=cwd, env=env, stdin=stdin, stdout=stdout, stderr=stderr)

        if pass_fds and not close_fds:
            log.warn("pass_fds overriding close_fds.")

        self.args = args
        self.encoding = encoding
        self.errors = errors

        if (text is not None and universal_newlines is not None and bool(universal_newlines) != bool(text)):
            raise subprocess.SubprocessError('Cannot disambiguate when both text and universal_newlines are supplied but different. Pass one or the other.')

        self.text_mode = bool(encoding or errors or text or universal_newlines)

        if self.stdin is not None and text:
            self.stdin = io.TextIOWrapper(self.stdin, write_through=True, line_buffering=(bufsize == 1), encoding=encoding, errors=errors)
        if self.stdout is not None and self.text_mode:
            self.stdout = io.TextIOWrapper(self.stdout, encoding=encoding, errors=errors)
            self._stdout_type = str
        if self.stderr is not None and self.text_mode:
            self.stderr = io.TextIOWrapper(self.stderr, encoding=encoding, errors=errors)
            self._stderr_type = str

    def communicate(self, input: str | bytes | None = None, timeout: float | None = None) -> tuple[str | bytes | None, str | bytes | None]:
        if self._communication_started and input:
            raise ValueError('Cannot send input after starting communication')

        self._communication_started = True
        if input and isinstance(self.stdin, io.TextIOWrapper):
            self.stdin.write(input)  # type: ignore[arg-type]
        elif input:
            self.stdin.write(string_utils.encode(input))
        self.wait(timeout=timeout)
        return self.stdout.read() if self.stdout else None, self.stderr.read() if self.stderr else None

    def wait(self, timeout: float | None = None) -> None:
        if self.poll() is not None:
            return

        assert self._completion is not None
        if timeout and (self._completion.elapsed is None or timeout < self._completion.elapsed):
            raise TimeoutExpired(self._args, timeout)

        if self._completion.elapsed is None:
            raise ValueError('Running a command that hangs without a timeout')

        if self._completion.elapsed:
            time.sleep(self._completion.elapsed)

        self.returncode = self._completion.returncode
        if self.stdout:
            self.stdout.seek(0)
        if self.stderr:
            self.stderr.seek(0)

    def __enter__(self) -> "Popen":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> None:
        if self.stdout:
            self.stdout.close()
        if self.stderr:
            self.stderr.close()
        if self.stdin:
            self.stdin.close()
