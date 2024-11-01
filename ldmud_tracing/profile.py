import ldmud, sys, collections, dataclasses, time

time_ns = getattr(time, 'time_ns', None)
if not time_ns:
    def time_ns():
        return int(time.time()*1000000)

class profile_result:
    @dataclasses.dataclass
    class LineInfo:
        cost: int = 0            # Eval cost
        time: int = 0            # Elapsed time in nanoseconds
        indirect_cost: int = 0   # Eval cost of called functions
        indirect_time: int = 0   # Elapsed time in nanoseconds of called functions

    @dataclasses.dataclass
    class FileInfo:
        cost: int = 0            # Eval cost
        time: int = 0            # Elapsed time in nanoseconds
        lines: dict = dataclasses.field(default_factory=lambda: collections.defaultdict(profile_result.LineInfo))

    def __init__(self):
        self.files = collections.defaultdict(profile_result.FileInfo)

    def add_line_info(self, fname, line, ticks, time):
        info = self.files[fname]
        info.cost += ticks
        info.time += time
        info.lines[line].cost += ticks
        info.lines[line].time += time

    def add_line_indirect_info(self, fname, line, ticks, time):
        info = self.files[fname]
        info.lines[line].indirect_cost += ticks
        info.lines[line].indirect_time += time

    def lpc_get_files(self):
        return ldmud.Array(sorted(self.files.keys()))

    def lpc_get_first_line(self, fname: str):
        return min(self.files[fname].lines.keys())

    def lpc_get_last_line(self, fname: str):
        return max(self.files[fname].lines.keys())

    def lpc_get_file_cost(self, fname: str):
        return self.files[fname].cost

    def lpc_get_file_time(self, fname: str):
        return self.files[fname].time

    def lpc_get_line_cost(self, fname: str, line: int):
        return self.files[fname].lines[line].cost

    def lpc_get_line_time(self, fname: str, line: int):
        return self.files[fname].lines[line].time

    def lpc_get_line_indirect_cost(self, fname: str, line: int):
        return self.files[fname].lines[line].indirect_cost

    def lpc_get_line_indirect_time(self, fname: str, line: int):
        return self.files[fname].lines[line].indirect_time

    def lpc_is_empty(self):
        return not self.files

    def __efun_call_strict__(self, fun: str, *args):
        return getattr(self, "lpc_" + fun)(*args)

def efun_profile_call(result: ldmud.Lvalue, fun: ldmud.Closure, *args) -> profile_result:
    """
    SYNOPSIS
            profile_result profile_call(mixed& result, closure fun, mixed arg, ...)

    DESCRIPTION
            Calls <fun> with the given arguments and stores the result in
            <result>, which must be passed by reference.

            Gathers profiling information that will be returned.

            The resulting object provides the following functions which can be
            called with call_strict (dot operator):

                string* get_files()
                    Returns a sorted list of programs that were traced.

                int get_first_line(string filename)
                    Returns the minimum line number of the given file where
                    trace information is available.

                int get_last_line(string filename)
                    Returns the maximum line number of the given file where
                    trace information is available.

                int get_line_cost(string filename, int linenumber)
                    Returns the accumulated costs for that line.

                int get_line_indirect_cost(string filename, int linenumber)
                    Returns those costs for that line, that are incurred in
                    calls done by this line.

                int get_file_cost(string filename)
                    Returns the accumulated costs for that file.

                int get_line_time(string filename, int linenumber)
                    Returns the accumulated durations in nanoseconds for that line.

                int get_line_indirect_time(string filename, int linenumber)
                    Returns the time for that line, that is used for processing
                    calls done by this line.

                int get_file_time(string filename)
                    Returns the accumulated durations in nanoseconds for that file.

                int is_empty()
                    Returns a value != 0, if there was no information
                    collected.

    SEE ALSO
            trace_call
    """

    @dataclasses.dataclass
    class PreviousLine:
        fname: str = None
        line_number: int = None
        ns: int = None
        eval_cost: int = None

    if not isinstance(result, ldmud.Lvalue):
        raise TypeError("Bad arg 1 to profile_call(): expected mixed &.")

    pr = profile_result()
    start_depth = len(ldmud.call_stack) - 1
    stack = [None] * start_depth
    last = PreviousLine()
    last.eval_cost = ldmud.call_stack[-1].eval_cost
    last.ns = time_ns()

    def hook(ob, instr):
        nonlocal last, stack

        cur_frame = ldmud.call_stack[-1]
        cur_fname = cur_frame.file_name
        cur_ns = time_ns()
        cur_depth = len(ldmud.call_stack) - 1 # Don't use the current frame.

        # Safeguard
        if cur_depth < start_depth:
            ldmud.unregister_hook(ldmud.BEFORE_INSTRUCTION, hook)

        if last.fname and last.line_number:
            pr.add_line_info(last.fname, last.line_number, max(1, cur_frame.eval_cost - last.eval_cost), cur_ns - last.ns)
            last.ns = cur_ns
            last.eval_cost = cur_frame.eval_cost

        if instr is None: # Don't do stack cleanup at the end, we will only get the profile_call() call.
            return

        if cur_fname:
            last.fname = cur_fname
            last.line_number = cur_frame.line_number

        while cur_depth > len(stack):
            new_frame = ldmud.call_stack[len(stack)]
            if new_frame.type == ldmud.CALL_FRAME_TYPE_LFUN:
                prev = PreviousLine()
                prev.fname = new_frame.file_name
                prev.line_number = new_frame.line_number
                prev.ns = cur_ns
                prev.eval_cost = new_frame.eval_cost
                stack.append(prev)
            else:
                stack.append(None)

        while cur_depth < len(stack):
            prev = stack.pop()
            if prev is not None and prev.fname and prev.line_number:
                pr.add_line_indirect_info(prev.fname, prev.line_number, max(1, cur_frame.eval_cost - prev.eval_cost), cur_ns - prev.ns)

    ldmud.register_hook(ldmud.BEFORE_INSTRUCTION, hook)
    try:
        result.value = ldmud.efuns.funcall(fun, *args)
    finally:
        ldmud.unregister_hook(ldmud.BEFORE_INSTRUCTION, hook)
    hook(None, None) # Process last instruction

    return pr


def register():
    """
    Register efuns and types.
    """
    ldmud.register_type("profile_result", profile_result)
    ldmud.register_efun("profile_call", efun_profile_call)
