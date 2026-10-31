"""Runtime detection of Nuke API usage errors in code run by the Python executor.

An *API usage error* is a failure of a call, lookup or attribute access on Nuke's own API
(``nuke``/``_nuke`` functions, native classes such as ``Node`` or ``Format_Knob``, the
``nuke.nodes`` constructors, ``nukescripts``) that the runtime itself attributes to the API.
Ordinary Python errors (``1 / 0``), deliberate ``raise`` statements, syntax errors and
operational failures (rendering or writing with missing media) are never reported.

Nothing is guessed from message text and no user expression is ever evaluated again. Evidence
comes from the interpreter while the code runs, for frames of the executor namespace only:

* ``sys.setprofile`` ``c_exception``: the failing C callable and its ``__self__``. Native Nuke
  classes report ``__module__ == "builtins"`` and module functions are ``builtin_function_or_method``
  objects of ``_nuke``, so ownership is decided by identity with the classes and modules
  that Nuke actually exposes, never by ``__module__`` strings of builtin types.
* ``sys.settrace`` ``exception`` events (line events are switched off): ``AttributeError.obj``
  names the real receiver of a missing member; a failure raised straight out of an instruction
  (``tb_next is None``, no Python frame below) at a call or subscript is attributed through the
  instruction's own source span, resolved against the frame *without executing anything*:
  variables come from the frame, attributes from ``inspect.getattr_static``, and call results
  are only tracked as "came from the Nuke API". Slots such as ``node['missing']`` and
  tp_call objects such as ``nuke.nodes.Circle`` raise no ``c_exception``, which is why they need
  this path.

Every record also carries ``runtime_evidence``: what the running Nuke itself reports about the
failing receiver or callable (knobs and choices, public members, installed signature/docstring),
read once, read-only, while the receiver is alive, and bounded in size. It states its own
limitations and says explicitly when nothing could be read; it is evidence for the next call,
never proof that the next call is valid.

Hooks installed before the executor ran are chained and restored; a hook the executed code
installed itself is left alone. Hook failures never reach the executed code: they are counted
and reported in ``api_error_tracking_failures``.
"""

from __future__ import annotations

import ast
import builtins
import collections
import dis
import inspect
import itertools
import sys
import types
import weakref

_PUBLIC_MODULES = {
    "_nuke": "nuke",
    "nuke_internal": "nuke",
    "_nuke_internal": "nuke",
    "_nuke_color": "nuke",
    "_nukemath": "nuke.math",
}
_API_ROOTS = frozenset(_PUBLIC_MODULES) | {"nuke", "nukescripts"}

_MAX_RECORDS = 20
_MAX_MESSAGE = 400
_MAX_SOURCE = 300
_MAX_QUERY = 120
_MAX_FAILURES = 5
_MAX_PLANS = 256

_CALL_OPS = frozenset({"CALL", "CALL_FUNCTION_EX"})
_ITEM_METHODS = {
    "BINARY_SUBSCR": "__getitem__",
    "STORE_SUBSCR": "__setitem__",
    "DELETE_SUBSCR": "__delitem__",
}
# Iteration protocol and cancellation are control flow, not failures.
_CONTROL_FLOW = (StopIteration, StopAsyncIteration)
# The only places the interpreter fails an attribute lookup and sets ``AttributeError.obj``
# itself: an attribute instruction, or the builtin that performs one. An explicit ``raise`` can
# put any ``obj`` on an exception, so it is never evidence.
_ATTRIBUTE_OPS = frozenset({"LOAD_ATTR", "LOAD_METHOD", "STORE_ATTR", "DELETE_ATTR"})
_ATTRIBUTE_BUILTINS = (getattr, setattr, delattr)
_DESCRIPTOR_TYPES = (
    types.MethodDescriptorType,
    types.WrapperDescriptorType,
    types.ClassMethodDescriptorType,
    types.GetSetDescriptorType,
    types.MemberDescriptorType,
)

# Entry points whose RuntimeError/OSError describe the operation (rendering, reading or writing
# media and scripts, the GUI thread being unavailable), not a misuse of the API. A TypeError or
# other signature error from them is still a usage error.
_OPERATIONAL_FUNCTIONS = frozenset(
    {
        "execute",
        "executeMultiple",
        "executeBackgroundNuke",
        "executeInMainThread",
        "executeInMainThreadWithResult",
        "scriptOpen",
        "scriptSave",
        "scriptSaveAs",
        "scriptSaveToTemp",
        "scriptSaveAndClear",
        "scriptReadFile",
        "scriptReadText",
        "scriptSource",
        "scriptClose",
        "nodePaste",
        "nodeCopy",
    }
)
# Node methods that evaluate the image, so a missing or broken source fails them operationally.
_OPERATIONAL_NODE_METHODS = frozenset(
    {"sample", "bbox", "width", "height", "format", "metadata", "channels", "screenWidth", "screenHeight"}
)

_UNKNOWN = ("unknown", None)
_API = ("api", None)

_known_types = {"modules": -1, "types": frozenset()}


def _clip(text, limit):
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _root_module(name):
    return name.partition(".")[0] if isinstance(name, str) else ""


def _public_module(name):
    root, dot, rest = name.partition(".")
    return _PUBLIC_MODULES.get(root, root) + dot + rest


def _declared_by_api(cls):
    module = getattr(cls, "__module__", None)
    if _root_module(module) in _API_ROOTS:
        return True
    # Native Nuke classes report "builtins"; a genuine Python builtin is the object itself.
    return module == "builtins" and getattr(builtins, getattr(cls, "__name__", ""), None) is not cls


def _api_types():
    """Every class the loaded Nuke API modules expose, native ones included (cached)."""
    count = len(sys.modules)
    if _known_types["modules"] != count:
        found = set()
        for name, module in list(sys.modules.items()):
            if module is None or _root_module(name) not in _API_ROOTS:
                continue
            try:
                values = list(vars(module).values())
            except TypeError:
                continue
            for value in values:
                if isinstance(value, type) and _declared_by_api(value):
                    found.add(value)
        _known_types["types"] = frozenset(found)
        _known_types["modules"] = count
    return _known_types["types"]


def _is_api_class(cls):
    return _root_module(getattr(cls, "__module__", None)) in _API_ROOTS or cls in _api_types()


def _is_api_object(obj):
    """True when ``obj`` is part of Nuke's API: its module, class, instance, function or method."""
    if isinstance(obj, types.ModuleType):
        return _root_module(getattr(obj, "__name__", None)) in _API_ROOTS
    if isinstance(obj, type):
        return _is_api_class(obj)
    kind = type(obj)
    if kind is types.BuiltinFunctionType:
        owner = getattr(obj, "__self__", None)
        if isinstance(owner, types.ModuleType):
            return _is_api_object(owner)
        if owner is not None:
            return _is_api_class(owner if isinstance(owner, type) else type(owner))
        return _root_module(getattr(obj, "__module__", None)) in _API_ROOTS
    if kind in _DESCRIPTOR_TYPES:
        owner = getattr(obj, "__objclass__", None)
        return isinstance(owner, type) and _is_api_class(owner)
    if kind is types.FunctionType:
        return _root_module(getattr(obj, "__module__", None)) in _API_ROOTS
    if kind is types.MethodType:
        return _is_api_object(obj.__func__)
    return _is_api_class(kind)


def _owner_label(owner):
    """(public dotted label, receiver class name or None) for a failing receiver."""
    if isinstance(owner, types.ModuleType):
        return _public_module(owner.__name__), None
    name = owner.__name__ if isinstance(owner, type) else type(owner).__name__
    return name, name


def _callee_info(func):
    """(api name, receiver class name, receiver class, member) for a failed native callable."""
    owner = getattr(func, "__self__", None)
    name = getattr(func, "__name__", None) or "?"
    if isinstance(owner, types.ModuleType):
        return "%s.%s" % (_public_module(owner.__name__), name), None, None, name
    if owner is None:
        owner = getattr(func, "__objclass__", None)
    if owner is None:
        return "%s.%s" % (_public_module(getattr(func, "__module__", None) or "nuke"), name), None, None, name
    cls = owner if isinstance(owner, type) else type(owner)
    return "%s.%s" % (cls.__name__, name), cls.__name__, cls, name


def _defining_class(cls, name):
    for base in cls.__mro__:
        if name in vars(base):
            return base.__name__
    return cls.__name__


def _operational(value, name, cls):
    if not isinstance(value, (RuntimeError, OSError)):
        return False
    if cls is None:
        return name in _OPERATIONAL_FUNCTIONS
    return name in _OPERATIONAL_NODE_METHODS and any(base.__name__ == "Node" for base in cls.__mro__)


def _message(value):
    try:
        return _clip(str(value), _MAX_MESSAGE)
    except Exception:
        return "<unprintable %s>" % type(value).__name__


def _queries(items):
    queries = []
    for item in items:
        if isinstance(item, str) and item and item not in queries:
            queries.append(_clip(item, _MAX_QUERY))
    return queries[:4]


def _unparse(node):
    try:
        return ast.unparse(node)
    except Exception:
        return "<expression>"


def _last_name(node):
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _lookup(frame, name):
    for scope in (frame.f_locals, frame.f_globals, frame.f_builtins):
        if name in scope:
            return True, scope[name]
    return False, None


def _dotted(node, frame):
    """The source path of a callee with an aliased Nuke module root named canonically."""
    original = node
    names = []
    while isinstance(node, ast.Attribute):
        names.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return _clip(_unparse(original), _MAX_QUERY)
    found, value = _lookup(frame, node.id)
    root = node.id
    if found and isinstance(value, types.ModuleType) and _is_api_object(value):
        root = _public_module(value.__name__)
    names.append(root)
    return ".".join(reversed(names))


def _key_text(node, frame):
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int)):
        return str(node.value)
    if isinstance(node, ast.Name):
        found, value = _lookup(frame, node.id)
        if found and isinstance(value, (str, int)):
            return str(value)
    return _clip(_unparse(node), 60)


def _resolve(node, frame, depth=0):
    """Where an expression's value comes from, without evaluating or calling anything.

    Returns ``("value", obj)`` for an object read from the frame, ``("api", None)`` for a value
    produced by Nuke's API whose identity is unknown (a call result, or an attribute of an API
    object), and ``("unknown", None)`` otherwise.
    """
    if depth > 12:
        return _UNKNOWN
    if isinstance(node, ast.Name):
        found, value = _lookup(frame, node.id)
        return ("value", value) if found else _UNKNOWN
    if isinstance(node, ast.Attribute):
        state, base = _resolve(node.value, frame, depth + 1)
        if state == "api" or (state == "value" and _is_api_object(base)):
            return _API
        if state == "value":
            try:
                return "value", inspect.getattr_static(base, node.attr)
            except AttributeError:
                return _UNKNOWN
        return _UNKNOWN
    if isinstance(node, (ast.Call, ast.Subscript)):
        inner = node.func if isinstance(node, ast.Call) else node.value
        state, target = _resolve(inner, frame, depth + 1)
        if state == "api" or (state == "value" and _is_api_object(target)):
            return _API
    return _UNKNOWN


def _split_lines(source):
    return source.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _position_at(code, lasti):
    """(line, end_line, column, end_column) of the instruction at byte offset ``lasti``, or None."""
    index = lasti // 2
    position = next(itertools.islice(code.co_positions(), index, index + 1), None)
    if position is None or None in position:
        return None
    return position


def _segment_at(code, lasti, source):
    """Source text of the instruction at ``lasti`` of ``code`` (its own column span)."""
    position = _position_at(code, lasti)
    if position is None:
        return None
    line, end_line, column, end_column = position
    lines = _split_lines(source)
    if not 1 <= line <= end_line <= len(lines):
        return None
    first = lines[line - 1].encode("utf-8")
    if line == end_line:
        return first[column:end_column].decode("utf-8")
    last = lines[end_line - 1].encode("utf-8")
    middle = lines[line : end_line - 1]
    return "\n".join([first[column:].decode("utf-8"), *middle, last[:end_column].decode("utf-8")])


def _segment(frame, source):
    """Source text of the instruction that is failing in ``frame`` (its own column span)."""
    return _segment_at(frame.f_code, frame.f_lasti, source)


def _similar(owner, name):
    """Real member names close to a missing one, from the receiver itself."""
    if not isinstance(name, str) or not name or name.startswith("_"):
        return []
    import difflib

    try:
        members = [member for member in dir(owner) if not member.startswith("_")]
    except Exception:
        return []
    lowered = {member.lower(): member for member in members}
    return [lowered[match] for match in difflib.get_close_matches(name.lower(), list(lowered), n=5, cutoff=0.6)]


def _similar_knobs(owner, name):
    """Knob names close to a missing one, queried from the actual node (read-only)."""
    if not isinstance(name, str) or not name:
        return []
    import difflib

    try:
        knobs = getattr(owner, "knobs", None)
        names = list(knobs()) if callable(knobs) else []
    except Exception:
        return []
    names = [item for item in names if isinstance(item, str)]
    lowered = {item.lower(): item for item in names}
    return [lowered[match] for match in difflib.get_close_matches(name.lower(), list(lowered), n=5, cutoff=0.6)]


# -- runtime evidence --------------------------------------------------------------------------
#
# While a failed API receiver is still alive (inside the hook that saw the failure), the running
# Nuke is asked what it really has: the receiver's own knobs, its type's public members, or the
# failed callable's installed signature/docstring. Only read-only metadata calls on objects Nuke
# itself exposes are made. Nothing the code wrote is re-run, no value is read or set, and nothing
# is guessed: a fact that cannot be read is reported as a limitation, never filled in.

_EV_MEMBERS = 80
_EV_CONTROLS = 40
_EV_CHOICES = 40
_EV_DOC = 600
_EV_NAME = 80
_EV_READ_ONLY = (
    "queried read-only from the running Nuke when the call failed; no expression was re-run and no value was read or set"
)
_EV_NO_RECEIVER = {
    "native_item_access_failed": (
        "the receiver of the failed lookup came from a Nuke call and was not captured as a live object; "
        "it is not re-created by re-running the expression"
    ),
    "native_call_failed": (
        "the failing callable was not captured as a live object; the source expression is never re-evaluated"
    ),
}


def _unavailable(reason):
    return {"source": "running_nuke", "available": False, "sufficient": False, "limitations": [reason]}


def _is_instance(owner):
    return not isinstance(owner, (type, types.ModuleType))


def _has_methods(owner, *names):
    cls = type(owner)
    return all(callable(getattr(cls, name, None)) for name in names)


def _is_node(owner):
    return _is_instance(owner) and _has_methods(owner, "knobs", "fullName")


def _is_knob(owner):
    return _is_instance(owner) and _has_methods(owner, "name", "node") and any(
        base.__name__.endswith("Knob") for base in type(owner).__mro__
    )


def _class_module(cls):
    module = getattr(cls, "__module__", None)
    if not isinstance(module, str):
        return None
    if module == "builtins":
        # Native classes report ``builtins``: they belong to nuke only if nuke exposes this very class.
        exposed = getattr(sys.modules.get("nuke"), getattr(cls, "__name__", ""), None)
        return "nuke" if exposed is cls else None
    return _public_module(module)


def _receiver_info(owner):
    if isinstance(owner, types.ModuleType):
        return {"class": "module", "module": _public_module(owner.__name__), "kind": "module"}
    if isinstance(owner, type):
        return {"class": owner.__name__, "module": _class_module(owner), "kind": "class"}
    info = {"class": type(owner).__name__, "module": _class_module(type(owner)), "kind": "instance"}
    try:
        node = owner if _is_node(owner) else owner.node() if _is_knob(owner) else None
        if node is not None:
            info["node"] = _clip(str(node.fullName()), _EV_NAME)
    except Exception:
        pass
    return info


def _related(names, member):
    """Names close to, or containing / contained in, the member the code asked for."""
    if not isinstance(member, str) or not member:
        return []
    import difflib

    low = member.lower()
    lowered = {name.lower(): name for name in names}
    found = [lowered[match] for match in difflib.get_close_matches(low, list(lowered), n=5, cutoff=0.6)]
    if len(low) >= 3:
        for name in names:
            text = name.lower()
            if name not in found and len(text) >= 3 and (low in text or text in low):
                found.append(name)
    return found[:10]


def _ordered(names, member, limit):
    related = _related(names, member)
    return (related + [name for name in names if name not in related])[:limit]


def _members(owner, member, evidence):
    target = owner if not _is_instance(owner) else type(owner)
    names = sorted({name for name in dir(target) if isinstance(name, str) and not name.startswith("_")})
    chosen = _ordered(names, member, _EV_MEMBERS)
    evidence["members"] = [_clip(name, _EV_NAME) for name in chosen]
    evidence["members_total"] = len(names)
    if len(names) > len(chosen):
        evidence["limitations"].append(
            "members lists %d of %d public names, the ones closest to %r first" % (len(chosen), len(names), member)
        )


def _choices(knob):
    """Allowed values of a choice knob, or (None, None) when the knob has no fixed choices."""
    cls = type(knob)
    if callable(getattr(cls, "values", None)):
        raw, source = knob.values(), None
    elif cls.__name__ == "Format_Knob":
        import nuke

        raw, source = [item.name() for item in nuke.formats()], "nuke.formats() of this session"
    else:
        return None, None
    names = []
    for item in raw:
        if isinstance(item, str) and item and item not in names:
            names.append(item)
    return names, source


def _control(name, knob):
    entry = {"name": _clip(str(name), _EV_NAME)}
    for key, getter in (("class", "Class"), ("label", "label")):
        try:
            value = getattr(knob, getter)()
        except Exception:
            continue
        if isinstance(value, str) and value:
            entry[key] = _clip(value, _EV_NAME)
    try:
        size = knob.arraySize()
        if isinstance(size, int) and not isinstance(size, bool):
            entry["array_size"] = size
    except Exception:
        pass
    try:
        names, source = _choices(knob)
    except Exception:
        names, source = None, None
    if names:
        entry["choices"] = [_clip(item, _EV_NAME) for item in names[:_EV_CHOICES]]
        entry["choices_total"] = len(names)
        if source:
            entry["choices_source"] = source
    return entry


def _controls(owner, member, evidence):
    if _is_node(owner):
        knobs = owner.knobs()
        names = [name for name in knobs if isinstance(name, str)]
        chosen = _ordered(names, member, _EV_CONTROLS)
        evidence["controls"] = [_control(name, knobs[name]) for name in chosen]
        evidence["controls_total"] = len(names)
        if len(names) > len(chosen):
            evidence["limitations"].append(
                "controls lists %d of %d knobs of the node, the ones closest to %r first" % (len(chosen), len(names), member)
            )
    elif _is_knob(owner):
        evidence["controls"] = [_control(owner.name(), owner)]
        evidence["controls_total"] = 1


def _callable_help(callee, member, evidence):
    info = {"name": member if isinstance(member, str) and member else str(getattr(callee, "__name__", "?"))}
    try:
        info["signature"] = _clip(str(inspect.signature(callee)), 200)
    except (TypeError, ValueError):
        pass
    doc = getattr(callee, "__doc__", None)
    if isinstance(doc, str) and doc.strip():
        info["doc"] = _clip("\n".join(line.strip() for line in doc.strip().splitlines() if line.strip()), _EV_DOC)
    evidence["callable"] = info
    if "signature" in info or "doc" in info:
        evidence["limitations"].append(
            "callable signature/doc are the installed object's own inspect.signature / __doc__: they can be "
            "incomplete or wrong and are not verified behaviour"
        )
    else:
        evidence["limitations"].append("the native callable exposes neither a signature nor a docstring")


def _runtime_evidence(kind, member, owner, callee):
    """Facts about a failed API call read from the live receiver/callable; see the section note."""
    if owner is None and callee is None:
        return _unavailable(_EV_NO_RECEIVER.get(kind, "no live receiver was captured for this failure"))
    evidence = {"source": "running_nuke", "available": True, "sufficient": False, "limitations": [_EV_READ_ONLY]}
    if isinstance(member, str) and member:
        evidence["member"] = member
    if owner is not None:
        evidence["receiver"] = _receiver_info(owner)
    else:
        evidence["limitations"].append("the interpreter did not expose the receiver instance of this native method")
    if kind == "missing_attribute":
        _members(owner, member, evidence)
        _controls(owner, member, evidence)
    elif kind == "native_item_access_failed":
        _controls(owner, member, evidence)
        if "controls" not in evidence:
            _members(owner, member, evidence)
    elif callee is not None:
        _callable_help(callee, member, evidence)
        if owner is not None and _is_knob(owner):
            _controls(owner, member, evidence)
    callable_help = evidence.get("callable", {})
    evidence["sufficient"] = bool(
        "receiver" in evidence
        and "member" in evidence
        and (
            evidence.get("members")
            or evidence.get("controls")
            or callable_help.get("signature")
            or callable_help.get("doc")
        )
    )
    return evidence


class SourceRegistry:
    """Source text of executed code objects, so a failing instruction's span can be read back.

    Code objects of functions defined by earlier calls stay registered for as long as they live.
    """

    def __init__(self):
        self._entries = {}

    def add(self, code, source):
        entries = self._entries
        stack = [code]
        while stack:
            current = stack.pop()
            key = id(current)

            def forget(_reference, key=key, entries=entries):
                entries.pop(key, None)

            entries[key] = (weakref.ref(current, forget), source)
            stack.extend(const for const in current.co_consts if isinstance(const, types.CodeType))

    def get(self, code):
        entry = self._entries.get(id(code))
        if entry is not None and entry[0]() is code:
            return entry[1]
        return None


class _Chain:
    """A frame's local trace function shared with one that was installed before ours."""

    __slots__ = ("inherited", "ours")

    def __init__(self, inherited, ours):
        self.inherited = inherited
        self.ours = ours

    def __call__(self, frame, event, arg):
        if self.inherited is not None:
            self.inherited = self.inherited(frame, event, arg)
        if self.ours is not None and self.ours(frame, event, arg) is None:
            self.ours = None
        return self if (self.inherited is not None or self.ours is not None) else None


class _Record:
    __slots__ = (
        "kind",
        "api",
        "member",
        "receiver",
        "provenance",
        "exception_type",
        "message",
        "function",
        "line",
        "source",
        "queries",
        "owner",
        "callee",
        "evidence",
        "similar",
        "occurrences",
        "exc",
    )

    def __init__(self, kind, api, member, receiver, provenance, value, frame, source, queries, owner=None, callee=None):
        self.kind = kind
        self.api = api
        self.member = member
        self.receiver = receiver
        self.provenance = provenance
        self.exception_type = type(value).__name__
        self.message = _message(value)
        self.function = frame.f_code.co_name
        self.line = frame.f_lineno
        self.source = source
        self.queries = _queries(queries)
        self.owner = owner
        self.callee = callee
        self.evidence = None
        self.similar = []
        self.occurrences = 1
        self.exc = None

    def key(self):
        return (self.kind, self.api, self.exception_type, self.message, self.function, self.line)

    def settle(self):
        """Compute suggestions and live runtime evidence once, then release every live reference."""
        owner, self.owner = self.owner, None
        callee, self.callee = self.callee, None
        if owner is not None:
            try:
                if self.kind == "missing_attribute":
                    self.similar = _similar(owner, self.member)
                elif self.kind == "native_item_access_failed":
                    self.similar = _similar_knobs(owner, self.member)
            except Exception:
                self.similar = []
        try:
            self.evidence = _runtime_evidence(self.kind, self.member, owner, callee)
        except Exception as failure:
            self.evidence = _unavailable("runtime evidence query failed: %s" % type(failure).__name__)

    def as_dict(self, caught):
        location = {"function": self.function, "line": self.line}
        if self.source:
            location["source"] = self.source
        record = {
            "api": self.api,
            "kind": self.kind,
            "exception_type": self.exception_type,
            "message": self.message,
            "member": self.member,
            "receiver": self.receiver,
            "caught": caught,
            "occurrences": self.occurrences,
            "provenance": self.provenance,
            "location": location,
            "search_queries": list(self.queries),
        }
        if self.similar:
            record["similar_members"] = list(self.similar)
        record["runtime_evidence"] = self.evidence or _unavailable("runtime evidence was not collected")
        return record


class ApiErrorTracker:
    """Context manager that records Nuke API usage errors raised by executed code.

    ``namespace`` is the executor namespace: only frames whose globals are that dict (the executed
    code and every function it defined, in this or an earlier call) are observed. ``sources`` maps
    their code objects to source text. Entering installs the profile and trace hooks, chained to
    any already installed; leaving restores them. ``response_fields`` then yields the executor
    response entries.
    """

    def __init__(self, namespace, sources=None):
        self._namespace = namespace
        self._sources = sources if sources is not None else SourceRegistry()
        self._records = {}
        self._omitted = 0
        self._failures = []
        self._seen = collections.deque(maxlen=8)
        self._plans = {}
        self._pending = None
        self._active = False
        self._previous_trace = None
        self._previous_profile = None
        self._trace_fn = None
        self._profile_fn = None
        self._local_fn = None

    # -- hook installation -------------------------------------------------------------------

    def __enter__(self):
        self._previous_trace = sys.gettrace()
        self._previous_profile = sys.getprofile()
        self._local_fn = self._make_local()
        self._trace_fn = self._make_trace()
        self._profile_fn = self._make_profile()
        self._active = True
        sys.setprofile(self._profile_fn)
        sys.settrace(self._trace_fn)
        return self

    def __exit__(self, exc_type, exc, tb):
        self._active = False
        try:
            # Hooks the executed code installed itself stay, as they would without tracking.
            if sys.gettrace() is self._trace_fn:
                sys.settrace(self._previous_trace)
            if sys.getprofile() is self._profile_fn:
                sys.setprofile(self._previous_profile)
        finally:
            self._pending = None
            self._seen.clear()
            self._plans.clear()
            self._trace_fn = self._profile_fn = self._local_fn = None
        return False

    def _make_profile(self):
        namespace = self._namespace
        previous = self._previous_profile
        handle = self._on_c_exception
        if previous is None:

            def profile(frame, event, arg):
                if event == "c_exception" and frame.f_globals is namespace:
                    handle(frame, arg)

        else:

            def profile(frame, event, arg):
                previous(frame, event, arg)
                if event == "c_exception" and frame.f_globals is namespace:
                    handle(frame, arg)

        return profile

    def _make_trace(self):
        namespace = self._namespace
        previous = self._previous_trace
        local = self._local_fn
        if previous is None:

            def trace(frame, event, arg):
                if frame.f_globals is namespace:
                    frame.f_trace_lines = False
                    return local
                return None

        else:
            # A tracer that was already installed (debugger, coverage) still sees every line.
            def trace(frame, event, arg):
                inherited = previous(frame, event, arg)
                if frame.f_globals is namespace:
                    return _Chain(inherited, local)
                return inherited

        return trace

    def _make_local(self):
        handle = self._on_exception

        def local(frame, event, arg):
            if not self._active:
                return None
            if event == "exception":
                handle(frame, arg)
            return local

        return local

    # -- observation -------------------------------------------------------------------------

    def _fail(self, failure):
        if len(self._failures) < _MAX_FAILURES:
            self._failures.append(_clip("%s: %s" % (type(failure).__name__, failure), _MAX_MESSAGE))

    def _on_c_exception(self, frame, func):
        # Every C callable of the executed code is remembered, API or not: a failure of a builtin
        # (``list.pop``, ``int``) on a value the API returned must not be taken for an API error.
        self._pending = (frame, frame.f_lasti, func)

    def _on_exception(self, frame, arg):
        func = None
        pending = self._pending
        if pending is not None and pending[0] is frame:
            self._pending = None
            if pending[1] == frame.f_lasti:
                func = pending[2]
        try:
            _type, value, trace = arg
            # A traceback with deeper frames means the failure was raised below this frame.
            if trace.tb_next is not None or not isinstance(value, Exception) or isinstance(value, _CONTROL_FLOW):
                return
            record = self._classify(frame, value, func)
            if record is not None:
                self._add(record, value)
        except Exception as failure:
            self._fail(failure)

    def _add(self, record, value):
        # One exception passes through several frames and handlers: record it once.
        if any(seen is value for seen in self._seen):
            return
        self._seen.append(value)
        key = record.key()
        existing = self._records.get(key)
        if existing is not None:
            existing.occurrences += 1
            existing.exc = value
            return
        if len(self._records) >= _MAX_RECORDS:
            self._omitted += 1
            return
        record.exc = value
        record.settle()
        self._records[key] = record

    # -- classification ----------------------------------------------------------------------

    def _classify(self, frame, value, func):
        if func is not None and _is_api_object(func):
            return self._native_call(frame, value, func)
        if isinstance(value, AttributeError):
            record = self._missing_attribute(frame, value, func)
            if record is not None:
                return record
        if func is not None and type(getattr(func, "__self__", None)).__name__ != "PyCapsule":
            # A builtin or foreign C callable failed (``list.pop()`` on a result of the API).
            # pybind11 methods are the exception: their ``__self__`` is a capsule, so who owns
            # them is decided from the source like any other call.
            return None
        return self._native_operation(frame, value)

    def _text(self, frame):
        try:
            source = self._sources.get(frame.f_code)
            if source is None:
                return None
            text = _segment(frame, source)
            if text is None:
                lines = _split_lines(source)
                text = lines[frame.f_lineno - 1] if 1 <= frame.f_lineno <= len(lines) else None
            return _clip(" ".join(text.split()), _MAX_SOURCE) if text else None
        except Exception:
            return None

    def _native_call(self, frame, value, func):
        """A native callable raised (``c_exception`` provenance)."""
        api, receiver, cls, member = _callee_info(func)
        if _operational(value, member, cls):
            return None
        queries = [api]
        if cls is not None:
            queries.append("%s.%s" % (_defining_class(cls, member), member))
        queries.append(member)
        holder = getattr(func, "__self__", None)
        if holder is not None and type(holder).__name__ == "PyCapsule":
            holder = None  # pybind11 hides the instance behind a capsule: no receiver is claimed
        return _Record(
            "native_call_failed",
            api,
            member,
            receiver,
            "profile:c_exception",
            value,
            frame,
            self._text(frame),
            queries,
            owner=holder,
            callee=func,
        )

    def _missing_attribute(self, frame, value, func):
        """``AttributeError.obj`` is a Nuke API object, set by a failed attribute lookup."""
        if func is not None:
            if not any(func is builtin for builtin in _ATTRIBUTE_BUILTINS):
                return None
        elif dis.opname[frame.f_code.co_code[frame.f_lasti]] not in _ATTRIBUTE_OPS:
            return None
        owner = getattr(value, "obj", None)
        if owner is None or not _is_api_object(owner):
            return None
        name = getattr(value, "name", None)
        member = name if isinstance(name, str) else None
        label, receiver = _owner_label(owner)
        api = "%s.%s" % (label, member or "?")
        return _Record(
            "missing_attribute",
            api,
            member,
            receiver,
            "trace:AttributeError.obj",
            value,
            frame,
            self._text(frame),
            [api, member],
            owner=owner,
        )

    def _plan(self, frame):
        code = frame.f_code
        key = (id(code), frame.f_lasti)
        cached = self._plans.get(key)
        if cached is not None and cached[0] is code:
            return cached[1]
        plan = self._build_plan(frame)
        if len(self._plans) >= _MAX_PLANS:
            self._plans.clear()
        self._plans[key] = (code, plan)
        return plan

    def _build_plan(self, frame):
        """The failing instruction as ``(opname, ast node)`` when it is a call or subscript."""
        code = frame.f_code
        operation = dis.opname[code.co_code[frame.f_lasti]]
        if operation in _CALL_OPS:
            wanted = ast.Call
        elif operation in _ITEM_METHODS:
            wanted = ast.Subscript
        else:
            return None
        source = self._sources.get(code)
        text = _segment(frame, source) if source is not None else None
        if not text:
            return None
        try:
            node = ast.parse("(" + text + ")", mode="eval").body
        except (SyntaxError, ValueError):
            return None
        return (operation, node) if isinstance(node, wanted) else None

    def _native_operation(self, frame, value):
        """A call or subscript raised straight out of the instruction, with no ``c_exception``."""
        plan = self._plan(frame)
        if plan is None:
            return None
        operation, node = plan
        if isinstance(node, ast.Call):
            return self._call_failure(frame, value, node)
        return self._item_failure(frame, value, operation, node)

    def _call_failure(self, frame, value, node):
        # tp_call objects such as nuke.nodes.Circle and native types are not PyCFunctions.
        state, target = _resolve(node.func, frame)
        if state == "unknown" or (state == "value" and not _is_api_object(target)):
            return None
        api = member = None
        if state == "value" and isinstance(node.func, ast.Name):
            # A variable holding an API callable: name what it is, not what the code called it.
            if isinstance(target, (type, types.FunctionType, types.BuiltinFunctionType)):
                api = member = target.__name__
            else:
                api = member = type(target).__name__
        else:
            api = _dotted(node.func, frame)
            member = _last_name(node.func)
        return _Record(
            "native_call_failed", api, member, None, "trace:native_call", value, frame, self._text(frame), [api, member]
        )

    def _item_failure(self, frame, value, operation, node):
        state, target = _resolve(node.value, frame)
        key = _key_text(node.slice, frame)
        owner = None
        if state == "value":
            if not _is_api_object(target):
                return None
            label, receiver = _owner_label(target)
            api = "%s.%s" % (label, _ITEM_METHODS[operation])
            queries = [api, key]
            owner = target
        elif state == "api":
            # The receiver's type is unknown. Python's own containers raise TypeError, KeyError
            # or IndexError, never these, so only a native slot can have raised them.
            if type(value) not in (NameError, LookupError):
                return None
            receiver = None
            api = _clip(_unparse(node.value), _MAX_QUERY) + "[...]"
            producer = _dotted(node.value.func, frame) if isinstance(node.value, ast.Call) else None
            queries = [producer, key]
        else:
            return None
        return _Record(
            "native_item_access_failed",
            api,
            key,
            receiver,
            "trace:native_item",
            value,
            frame,
            self._text(frame),
            queries,
            owner=owner,
        )

    # -- results -----------------------------------------------------------------------------

    def response_fields(self, error=None):
        """Executor response entries. ``error`` is the exception that ended the run, if any."""
        records = [record.as_dict(caught=record.exc is not error) for record in self._records.values()]
        fields = {"api_errors": records}
        if self._omitted:
            fields["api_errors_omitted"] = self._omitted
        if self._failures:
            fields["api_error_tracking_failures"] = list(self._failures)
        self._records.clear()
        return fields
