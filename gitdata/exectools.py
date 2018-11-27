"""
This module contains a set of functions for managing shell commands
consistently. It adds some logging and some additional capabilties to the
ordinary subprocess behaviors.
"""

from __future__ import print_function

import subprocess
import time
import shlex

import pushd
import assertion
import logging

SUCCESS = 0


class RetryException(Exception):
    """
    Provide a custom exception for retry failures
    """
    pass


class Exec(object):
    def __init__(self, logger=None):
        self.logger = logger
        if logger is None:
            self.logger = logging.getLogger()

    def retry(self, retries, task_f, check_f=bool, wait_f=None):
        """
        Try a function up to n times.
        Raise an exception if it does not pass in time

        :param retries int: The number of times to retry
        :param task_f func: The function to be run and observed
        :param func()bool check_f: a function to check if task_f is complete
        :param func()bool wait_f: a function to run between checks
        """
        for attempt in range(retries):
            ret = task_f()
            if check_f(ret):
                return ret
            if attempt < retries - 1 and wait_f is not None:
                wait_f(attempt)
        raise RetryException("Giving up after {} failed attempt(s)".format(retries))

    def check_assert(self, cmd, retries=1, pollrate=60, on_retry=None):
        """
        Run a command, logging (using gather) and raise an exception if the
        return code of the command indicates failure.
        Try the command multiple times if requested.

        :param cmd <string|list>: A shell command
        :param retries int: The number of times to try before declaring failure
        :param pollrate int: how long to sleep between tries
        :param on_retry <string|list>: A shell command to run before retrying a failure
        :return: (stdout,stderr) if exit code is zero
        """

        for try_num in range(0, retries):
            if try_num > 0:
                self.logger.debug(
                    "assert: Failed {} times. Retrying in {} seconds: {}".
                    format(try_num, pollrate, cmd))
                time.sleep(pollrate)
                if on_retry is not None:
                    self.gather(on_retry)  # no real use for the result though

            result, stdout, stderr = self.gather(cmd)
            if result == SUCCESS:
                break

        self.logger.debug("assert: Final result = {} in {} tries.".format(result, try_num))

        assertion.success(
            result,
            "Error running [{}] {}.\n{}".
            format(pushd.Dir.getcwd(), cmd, stderr))

        return stdout, stderr

    def gather(self, cmd):
        """
        Runs a command and returns rc,stdout,stderr as a tuple.

        If called while the `Dir` context manager is in effect, guarantees that the
        process is executed in that directory, even if it is no longer the current
        directory of the process (i.e. it is thread-safe).

        :param cmd: The command and arguments to execute
        :return: (rc,stdout,stderr)
        """

        if not isinstance(cmd, list):
            cmd_list = shlex.split(cmd)
        else:
            cmd_list = cmd

        cwd = pushd.Dir.getcwd()
        cmd_info = '[cwd={}]: {}'.format(cwd, cmd_list)

        self.logger.debug("Executing:gather {}".format(cmd_info))
        proc = subprocess.Popen(
            cmd_list, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
        rc = proc.returncode
        self.logger.debug(
            "Process {}: exited with: {}\nstdout>>{}<<\nstderr>>{}<<\n".
            format(cmd_info, rc, out, err))
        return rc, out, err
