import ldmud, functools

def format(value, max_depth = -1, compact = False, quote_string = False, object_name_fun = None):
    return LDMudFormatter(max_depth = max_depth, compact = compact, quote_string = quote_string, object_name_fun = object_name_fun).format(value)

_escape_chars = {
    0x00: '\\0',
    0x07: '\\a',
    0x08: '\\b',
    0x09: '\\t',
    0x0a: '\\n',
    0x0d: '\\r',
    0x1b: '\\e',
    0x22: '\\"',
    0x5c: '\\\\',
}

class LDMudFormatter:
    def __init__(self, max_depth = -1, compact = False, quote_string = False, object_name_fun = None):
        self.max_depth = max_depth
        self.compact = compact
        self.quote_string = quote_string
        self.object_name_fun = object_name_fun

    def format(self, value):
        return self._print(value, indent = 0, depth = 0, seen = {})

    @functools.singledispatchmethod
    def _print(self, value, indent, depth, seen):
        return repr(value)

    @_print.register
    def _print_integer(self, value: int, indent, depth, seen):
        return repr(value)

    @_print.register
    def _print_float(self, value: float, indent, depth, seen):
        result = "%g" % (value,)
        if not '.' in result and not 'e' in result:
            return result + ".0"
        else:
            return result

    @_print.register
    def _print_string(self, value: str, indent, depth, seen):
        def quote_char(ch):
            cp = ord(ch)
            result = _escape_chars.get(cp)
            if result:
                return result
            if cp < 0x20:
                return "\\x%02x" % (cp,)
            elif cp < 0x7f:
                return ch
            elif cp < 0x10000:
                return "\\u%04x" % (cp,)
            else:
                return "\\U%08x" % (cp,)

        if self.quote_string:
            return '"' + "".join(quote_char(ch) for ch in value) + "'"
        else:
            return '"' + value + '"'

    @_print.register
    def _print_bytes(self, value: bytes, indent, depth, seen):
        return '"' + "".join("\\x%02x" % (ch,) for ch in value) + '"'

    @_print.register
    def _print_symbol(self, value: ldmud.Symbol, indent, depth, seen):
        return "'" * value.quotes + value.name

    @_print.register
    def _print_array(self, value: ldmud.Array, indent, depth, seen):
        if not len(value):
            return "({})" if self.compact else "({ })"
        next_id = len(seen)+1
        cur_id = seen.setdefault(value, next_id)
        if cur_id != next_id:
            if self.compact:
                return "({#%d})" % (cur_id,)
            else:
                return "({ #%d })" % (cur_id,)
        elif self.max_depth >= 0 and depth >= self.max_depth:
            if self.compact:
                return "({#%d ... })" % (cur_id,)
            else:
                return "({ /* #%d, size: %d */ ... })" % (cur_id, len(value),)
        else:
            if self.compact:
                return ("({#%d " % (cur_id,)) + ",".join(self._print(element, indent+2, depth+1, seen) for element in value) + "})"
            else:
                return ("({ /* #%d, size: %d */\n" % (cur_id, len(value),)) + ",\n".join(' '*(indent+2) + self._print(element, indent+2, depth+1, seen) for element in value) + "\n" + ' ' * indent + "})"

    @_print.register
    def _print_quoted_array(self, value: ldmud.QuotedArray, indent, depth, seen):
        return "'" * value.quotes + self._print_array(value.array, indent, depth, seen)

    @_print.register
    def _print_mapping(self, value: ldmud.Mapping, indent, depth, seen):
        def print_entry(entry):
            if len(entry) == 1:
                return self._print(entry[0], indent+2, depth+1, seen)
            key = self._print(entry[0], indent+2, depth+1, seen)
            width = len(key) - key.rfind("\n")
            return key + ": " + "; ".join(self._print(val, indent+width+3, depth+1, seen) for val in entry[1:])

        def print_entry_compact(entry):
            if len(entry) == 1:
                return self._print(entry[0], indent+2, depth+1, seen)
            return self._print(entry[0], indent+2, depth+1, seen) + ":" + ";".join(self._print(val, indent+2, depth+1, seen) for val in entry[1:])

        next_id = len(seen)+1
        cur_id = seen.setdefault(value, next_id)
        if cur_id != next_id:
            if self.compact:
                return "([#%d])" % (cur_id,)
            else:
                return "([ #%d ])" % (cur_id,)
        elif self.max_depth >= 0 and depth >= self.max_depth:
            if self.compact:
                return "([#%d ... ])" % (cur_id,)
            else:
                return "([ /* #%d */ ... ])" % (cur_id,)
        else:
            if self.compact:
                return ("([#%d " % (cur_id,)) + ",".join(print_entry_compact(entry) for entry in value.items()) + "])"
            else:
                return ("([ /* #%d */" % (cur_id,)) + ",".join('\n' + ' '*(indent+2) + print_entry(entry) for entry in value.items()) + "\n" + ' ' * indent + "])"

    @_print.register
    def _print_struct(self, value: ldmud.Struct, indent, depth, seen):
        def print_member(member):
            return "/* %s: */ " % (member.name,) + self._print(member.value, indent+2, depth+1, seen)

        def print_member_compact(member):
            return self._print(member.value, indent+2, depth+1, seen)

        next_id = len(seen)+1
        cur_id = seen.setdefault(value, next_id)

        if cur_id != next_id:
            if self.compact:
                return "(<#%d>)" % (cur_id,)
            else:
                return "(< #%d >)" % (cur_id,)
        elif not len(value.members):
            if self.compact:
                return "(<'%s %s'#%d>)" % (value.name, value.program_name, cur_id,)
            else:
                return "(<'%s %s' /* #%d, size: %d */ >)" % (value.name, value.program_name, cur_id, len(value.members),)
        elif self.max_depth >= 0 and depth >= self.max_depth:
            if self.compact:
                return "(<'%s %s'#%d> ... )" % (value.name, value.program_name, cur_id,)
            else:
                return "(<'%s %s' /* #%d, size: %d */ > ... )" % (value.name, value.program_name, cur_id, len(value.members),)
        else:
            if self.compact:
                return ("(<'%s %s'#%d> " % (value.name, value.program_name, cur_id,)) + ",".join(print_member_compact(member) for member in value.members) + ")"
            else:
                return ("(<'%s %s' /* #%d, size: %d */ >" % (value.name, value.program_name, cur_id, len(value.members),)) + ",".join('\n' + ' '*(indent+2) + print_member(member) for member in value.members) + "\n" + ' ' * indent + ")"

    @_print.register
    def _print_object(self, value: ldmud.Object, indent, depth, seen):
        if self.object_name_fun and not self.compact:
            name = self.object_name_fun(value)
        else:
            name = None
        if isinstance(name, str):
            return value.name + ' ("' + name + '")'
        return value.name

    @_print.register
    def _print_lwobject(self, value: ldmud.LWObject, indent, depth, seen):
        return "(" + value.program_name + ")"

    @_print.register
    def _print_lfun_closure(self, value: ldmud.LfunClosure, indent, depth, seen):
        if value.bound_object != value.object:
            prefix = "[%s]" % (self._object_name(value.bound_object),)
        else:
            prefix = ""
        if value.inherited:
            inh = "(%s)" % (value.lfun.program_name[:-2],)
        else:
            inh = ""
        return "#'%s%s%s->%s()" % (prefix, self._object_name(value.object), inh, value.lfun.name)

    @_print.register
    def _print_identifier_closure(self, value: ldmud.IdentifierClosure, indent, depth, seen):
        if value.variable is None:
            return "#'<repl lvar>" if self.compact else "#'<local variable from replaced program>"
        return "#'%s->%s" % (self._object_name(value.object), value.variable.name)

    @_print.register
    def _print_lambda(self, value: ldmud.LambdaClosure, indent, depth, seen):
        return "<lambda:%s>" % (self._object_name(value.object),)

    @_print.register
    def _print_unbound_lambda(self, value: ldmud.UnboundLambdaClosure, indent, depth, seen):
        return "<free lambda>"

    @_print.register
    def _print_bound_lambda(self, value: ldmud.BoundLambdaClosure, indent, depth, seen):
        return "<bound lambda:%s>" % (self._object_name(value.object),)

    @_print.register
    def _print_efun_closurea(self, value: ldmud.EfunClosure, indent, depth, seen):
        return "#'%s" % (value.efun.name,)

    @_print.register
    def _print_sefun_closurea(self, value: ldmud.SimulEfunClosure, indent, depth, seen):
        return "#'sefun::%s" % (value.simul_efun.name,)

    @_print.register
    def _print_operator_closurea(self, value: ldmud.OperatorClosure, indent, depth, seen):
        return "#'%s" % (value.operator_name,)

    @_print.register
    def _print_coroutine(self, value: ldmud.Coroutine, indent, depth, seen):
        ob = value.object
        if isinstance(ob, ldmud.Object):
            ob_str = ob.name
        elif isinstance(ob, ldmud.LWObject):
            ob_str = ob.program_name
        else:
            return "<coroutine in destructed object>"
        return "<coroutine %s->%s>" % (ob_str, value.function_name,)

    @_print.register
    def _print_type(self, value: type, indent, depth, seen):
        return "[%s]" % (str(value),)

    @functools.singledispatchmethod
    def _object_name(self, value):
        return repr(value)

    @_object_name.register
    def _print_integer(self, value: ldmud.Object):
        return value.name

    @_object_name.register
    def _print_integer(self, value: ldmud.LWObject):
        return value.program_name
