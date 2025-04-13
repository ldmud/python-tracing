import ldmud, time
from . import formatting

time_ns = getattr(time, 'time_ns', None)
if not time_ns:
    def time_ns():
        return int(time.time()*1000000)

class Step:
    def __init__(self, frame, ns):
        self.object = frame.object
        self.program_name = frame.program_name
        self.file_name = frame.file_name
        self.line_number = frame.line_number
        self.eval_cost = frame.eval_cost
        self.eval_time = ns
        self.calls = []
        self.variables_dict = {} # name: [indices into self.variables]
        self.variables = []

    def add_variable(self, name, value):
        # This is emulating a ordered multi dict.
        self.variables_dict.setdefault(name, []).append(len(self.variables))
        self.variables.append((name, value,))

class trace_cursor:
    def __init__(self, steps, pos):
        self.stack = []
        self.steps = steps
        self.pos = pos
        self.current = steps[pos]

    def lpc_step_into(self) -> int:
        if not self.current.calls:
            return self.lpc_step_over()

        self.stack.append((self.steps, self.pos,))
        self.steps = self.current.calls
        self.pos = 0
        self.current = self.steps[0]
        return 1

    def lpc_step_over(self) -> int:
        while True:
            if self.pos + 1 < len(self.steps):
                self.pos += 1
                self.current = self.steps[self.pos]
                return 1

            if not self.stack:
                return 0

            (self.steps, self.pos) = self.stack.pop()
            self.current = self.steps[self.pos]

    def lpc_step_out(self) -> None:
        if not self.stack:
            return 0

        (self.steps, self.pos) = self.stack.pop()
        return self.lpc_step_over()

    def lpc_get_object(self) -> ldmud.Object:
        return self.current.object

    def lpc_get_program_name(self) -> str:
        return self.current.program_name

    def lpc_get_file_name(self) -> str:
        return self.current.file_name

    def lpc_get_line_number(self) -> int:
        return self.current.line_number

    def lpc_get_eval_cost(self) -> int:
        return self.current.eval_cost

    def lpc_get_time(self) -> int:
        return self.current.eval_time

    def lpc_get_variables(self) -> ldmud.Array[ldmud.Array[ldmud.String]]:
        return ldmud.Array(ldmud.Array(var) for var in self.current.variables)

    def lpc_get_variable(self, name: str) -> ldmud.Array[ldmud.String]:
        return ldmud.Array(self.current.variables[idx][1] for idx in self.current.variables_dict.get(name, []))

    def __efun_call_strict__(self, fun: str, *args):
        return getattr(self, "lpc_" + fun)(*args)

    def __copy__(self):
        result = trace_cursor(self.steps, self.pos)
        result.stack = self.stack
        return result

    def __eq__(self, other):
        if isinstance(other, trace_cursor):
            return (self.pos, self.stack, self.steps) == (other.pos, other.stack, other.steps)
        return NotImplemented

class trace_result:
    def __init__(self):
        self.steps = []

    def lpc_begin(self) -> trace_cursor:
        if not self.steps:
            return None
        return trace_cursor(self.steps, 0)

    def lpc_end(self) -> trace_cursor:
        if not self.steps:
            return None
        return trace_cursor(self.steps, len(self.steps)-1)

    def __efun_call_strict__(self, fun: str, *args):
        return getattr(self, "lpc_" + fun)(*args)

trace_call_options = ldmud.register_struct("trace_call_options", None, (
    ('granularity', int,),
    ('max_depth', int,),
    ('exclude', ldmud.Mapping,),
    ('only', ldmud.Mapping,),
    ('capture_local_variables', int,),
    ('variable_format_depth', int,),
    ('variable_format_compact', int,),
))

def partition(values, condition):
    if values is None or values is 0:
        return (None, None)

    values_and_condition = [(value, condition(value)) for value in values]
    return ([value for (value, cond) in values_and_condition if cond], [value for (value, cond) in values_and_condition if not cond])

def efun_trace_call(opts: trace_call_options, result: ldmud.Lvalue, fun: ldmud.Closure, *args) -> trace_result:
    """
    SYNOPSIS
            trace_result trace_call(struct trace_call_options opts, mixed& result, closure fun, mixed arg, ...)

    DESCRIPTION
            Calls <fun> with the given arguments and stores the result in
            <result>, which must be passed by reference.

            The following options can be given:

                int granularity
                    Determins how operations are aggregated:
                        0: Single operation, i.e. don't aggregate.
                        1: Single line, i.e. aggregate all operations from
                           the same source line.
                        2: Function call, i.e. aggregate all operations from
                           the same function call (until interrupted by another
                           call).

                int max_depth
                    Don't trace any calls beyond that stack depth.

                mapping exclude
                    A 0-width mapping containing objects, file or program names
                    that shouldn't be traced. It can also contain directory
                    names (strings ending with a slash), then all files in the
                    directory and its subdirectories are excluded.

                mapping only
                    A 0-width mapping containing objects, file or program names
                    that should only be traced. It can also contain directory
                    names (strings ending with a slash), then all files in the
                    directory and its subdirectories are included as well.

                int capture_local_variables
                    Whether the values of local variables shall be captured.
                    When capturing they will be formatted as strings, so the
                    original value will not be copied/stored.

                int variable_format_depth
                    For formatting of nested data structures (arrays, mappings,
                    structs) specifies the depth for formatting. 0 (default)
                    means only the immediate values are shown, not any array/
                    mapping/struct members. To show the whole datastructure,
                    pass -1.

                int variable_format_compact
                    Whether to use compact format.

            This function raises a privilege violation("trace_call", object, opts, fun).
            The master can change the options when checking privileges.

            The resulting object provides the following functions which can be
            called with call_strict (dot operator):

                trace_cursor begin()
                    Returns a cursor that represents the state at the beginning
                    of the execution.

                trace_cursor end()
                    Returns a cursor that represents the state at the end
                    of the execution.

            A cursor object provides the following functions:

                int step_into()
                    Moves to the cursor into the next function call.
                    Returns 1 on success.

                int step_over()
                    Moves to the cursor to state just beyond the next
                    function call. Returns 1 on success.

                int step_out()
                    Moves to the cursor to the state after returning
                    from the current function. Returns 1 on success.

                object get_object()
                    Returns the current object.

                string get_program_name()
                    Returns the current program name.
                    This will be 0 for lambdas.

                string get_file_name()
                    Returns the current file name.
                    This will be 0 for lambdas.

                int get_line_number()
                    Returns the current line number.

                int get_eval_cost()
                    Returns the current eval cost.

                int get_time()
                    Returns the number of nano-seconds elapsed to this
                    position from the start of evaluation.

                string** get_variables()
                    Returns an array of all local variables. Each entry is an
                    array ({ name, value }), where the value is the original
                    value formatted into a string. This is only populated when
                    <capture_local_variables> flag is true.

                string* get_variable(string name)
                    Returns an array with the values of all local variables
                    with that name. The returned array can be empty if there
                    was no such variable or contain more than one entries when
                    there were multiple variables with the same name (which is
                    discouraged and usually leads to a compiler warning).

    SEE ALSO
            profile_call
    """

    if not isinstance(result, ldmud.Lvalue):
        raise TypeError("Bad arg 2 to trace_call(): expected mixed &.")

    # Create a struct, so the master can add/change entries.
    if not opts:
        opts = trace_call_options()

    master = ldmud.get_master()
    this_object = ldmud.efuns.this_object()
    if master != this_object and not master.functions.privilege_violation("trace_call", this_object, opts, fun, None):
        raise PermissionError("Insufficient privileges for trace_call()")

    granularity = opts.members.granularity.value
    max_depth = opts.members.max_depth.value
    exclude = opts.members.exclude.value
    include = opts.members.only.value

    if opts.members.capture_local_variables.value:
        formatter = formatting.LDMudFormatter(max_depth = opts.members.variable_format_depth.value, compact = opts.members.variable_format_compact.value != 0)
    else:
        formatter = None

    tr = trace_result()
    start_depth = len(ldmud.call_stack) + 1
    stack = [ tr.steps ]

    if not exclude and include is not None:
        def allow_frame(frame):
            return True
    else:
        def contains(frame, lst, dirs):
            if frame.object in lst:
                return True
            if frame.program_name and frame.program_name in lst:
                return True
            if frame.file_name and frame.file_name in lst:
                return True
            if any(frame.file_name.startswith(d) for d in dirs):
                return True
            return False

        (excluded_dirs, exclude) = partition(exclude, lambda d: isinstance(d, str) and d.endswith("/"))
        (included_dirs, include) = partition(include, lambda d: isinstance(d, str) and d.endswith("/"))
        def allow_frame(frame):
            if include is not None and not contains(frame, include, included_dirs):
                return False
            if (exclude or excluded_dirs) and contains(frame, exclude, excluded_dirs):
                return False
            return True

    if granularity == 2: # Function
        def allow_join(prev, cur):
            return True
    elif granularity == 1: # By Line
        def allow_join(prev, cur):
            return prev.file_name == cur.file_name and prev.line_number == cur.line_number
    else:
        def allow_join(prev, cur):
            return False

    last_ns = time_ns()
    def hook(ob, instr):
        nonlocal stack, last_ns

        # Safeguard
        cur_depth = len(ldmud.call_stack)
        if cur_depth < start_depth:
            ldmud.unregister_hook(ldmud.BEFORE_INSTRUCTION, hook)
            return

        if max_depth and cur_depth > start_depth + max_depth:
            return

        cur_frame = ldmud.call_stack[-1]
        if cur_frame.type not in (ldmud.CALL_FRAME_TYPE_LFUN, ldmud.CALL_FRAME_TYPE_LAMBDA):
            return

        cur_ns = time_ns()
        step = Step(cur_frame, cur_ns - last_ns)
        if not allow_frame(step):
            return

        if formatter is not None:
            for name, var in cur_frame.variables.__dict__.items():
                step.add_variable(name, formatter.format(var.value))

        parent_idx = cur_depth - start_depth
        if len(stack) > parent_idx + 1:
            stack = stack[:parent_idx+1]
        elif len(stack) < parent_idx + 1:
            stack.extend(None for _ in range(len(stack), parent_idx + 1))
        while stack[parent_idx] is None:
            parent_idx -= 1

        stack_entry = stack[parent_idx]
        if not stack_entry:
            stack_entry.append(step)
            last_ns = cur_ns
        elif allow_join(stack_entry[-1], step) and not stack_entry[-1].calls:
            stack_entry[-1] = step
        else:
            stack_entry.append(step)
            last_ns = cur_ns
        stack.append(step.calls)

    ldmud.register_hook(ldmud.BEFORE_INSTRUCTION, hook)
    try:
        result.value = fun(*args)#ldmud.efuns.funcall(fun, *args)
    finally:
        ldmud.unregister_hook(ldmud.BEFORE_INSTRUCTION, hook)

    return tr

def register():
    """
    Register efuns and types.
    """
    ldmud.register_type("trace_result", trace_result)
    ldmud.register_type("trace_cursor", trace_cursor)
    ldmud.register_efun("trace_call", efun_trace_call)
