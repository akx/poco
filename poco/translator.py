from poco.stream import CodeStream, StdoutCodeStream
import ast
import json
import operator


BIN_OPS = {  # XXX: Totally incomplete :D
    ast.Add: ("+", operator.add),
    ast.Div: ("/", operator.div),
    ast.Eq: ("==", None),
    ast.Mult: ("*", operator.mul),
    ast.Sub: ("-", operator.sub),
}


NOPE = object()


def ifparen(str, test):
    if test:
        str = "(%s)" % str
    return str


def constant_fold(left, right, opfun):
    if isinstance(left, ast.Num) and isinstance(right, ast.Num) and opfun:
        return ast.Num(n=opfun(left.n, right.n))
    elif isinstance(left, ast.Str) and isinstance(right, ast.Str) and opfun is operator.add:
        return ast.Str(s=left.s + right.s)
    else:
        return None


class Translator(ast.NodeVisitor):
    def __init__(self, debug=False):
        if debug:
            self.debug_stream = StdoutCodeStream()
        else:
            self.debug_stream = None
        self.stream = CodeStream()

    def visit(self, node):
        if self.debug_stream:
            with self.debug_stream.enter(repr(node)):
                super(Translator, self).visit(node)
        else:
            super(Translator, self).visit(node)

    def generic_function(self, node, implicit_return, prelude="", as_expr=False):
        args = node.args
        if args:
            assert not args.kwarg, "**kwarg not supported"
            assert not args.vararg, "*vararg not supported"
            assert all(isinstance(arg, ast.Name) for arg in args.args), "unpacks not supported"
            padded_defaults = [NOPE] * (len(args.args) - len(args.defaults)) + args.defaults

            arglist = []
            for arg, default in zip(args.args, padded_defaults):
                arg = self.expr_to_js(arg)
                if default is not NOPE:
                    arg += " = %s" % self.expr_to_js(default, node)
                arglist.append(arg)

            if arglist:
                arglist = "(%s) " % ", ".join(arglist)
            else:
                arglist = ""
        else:
            arglist = ""

        if not implicit_return:
            last_exp = node.body[-1] if isinstance(node.body, list) else node.body
            if isinstance(last_exp, (ast.BinOp, ast.Expr, ast.IfExp)):
                implicit_return = True
                node.body = last_exp

        prefix = "!" if not implicit_return else ""

        sig = "%s%s%s->" % (prelude, prefix, arglist)

        if isinstance(node.body, list):
            with self.stream.enter(sig):
                for expr in node.body:
                    self.visit(expr)
        else:
            funexpr = "%s %s" % (sig, self.expr_to_js(node.body))
            self.stream.write(ifparen(funexpr, as_expr))

    def visit_FunctionDef(self, node):
        self.generic_function(node, False, "%s = " % node.name)
        self.stream.write("")

    def _emit_bodied(self, node, prelude, forbid_single=False):
        if len(node.body) == 1 and not forbid_single:
            self.stream.write("%s %s" % (self.expr_to_js(node.body[0], node), prelude))
        else:
            with self.stream.enter(prelude):
                for expr in node.body:
                    self.visit(expr)

    def visit_For(self, node):
        assert not node.orelse, "for orelse not supported"
        fnode = self.emit_for_fnode(node)
        self._emit_bodied(node, fnode)

    def visit_Call(self, node):
        self.stream.write(self.transform_call_node(node))

    def visit_If(self, node):
        ifexpr = "if %s" % self.expr_to_js(node.test)
        if not node.orelse:
            self._emit_bodied(node, ifexpr)
        else:
            self._emit_bodied(node, ifexpr, True)
            self._emit_bodied(node.orelse, "else", True)

    def visit_Print(self, node):
        self.stream.write(self.expr_to_js(node))

    def visit_Return(self, node):
        self.stream.write(self.expr_to_js(node))

    def visit_BinOp(self, node):
        self.stream.write(self.expr_to_js(node))

    def visit_Assign(self, node):
        assert len(node.targets) == 1, "only one assignment target supported"
        self.stream.write("%s = %s" % (self.expr_to_js(node.targets[0]), self.expr_to_js(node.value)))

    def expr_to_js(self, node, parent=None, context=None):
        if isinstance(node, (tuple, list)):
            return ", ".join(self.expr_to_js(p, parent, context) for p in node)
        elif isinstance(node, ast.Print):
            cnode = ast.Call(func=ast.Name(id="console.log"), args=node.values, kwargs=None, starargs=None)
            return self.transform_call_node(cnode)
        elif isinstance(node, ast.Expr):
            return self.expr_to_js(node.value, node)
        elif isinstance(node, ast.Attribute):
            return self.dotify_attribute(node)
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Str):
            return json.dumps(node.s)
        elif isinstance(node, ast.Num):
            return json.dumps(node.n)
        elif isinstance(node, ast.Call):
            return self.transform_call_node(node)
        elif isinstance(node, (ast.Compare, ast.BinOp)):
            if isinstance(node, ast.Compare):
                assert len(node.ops) == 1, "multicompare not supported"
                op = node.ops[0]
                left = node.left
                right = node.comparators[0]
            else:
                op = node.op
                left = node.left
                right = node.right

            binop, opfun = BIN_OPS.get(op.__class__, (None, None))
            assert binop, "Unknown binop %s" % op

            cex = constant_fold(left, right, opfun)

            if cex:
                return self.expr_to_js(cex)

            expr = "%s %s %s" % (self.expr_to_js(left, node), binop, self.expr_to_js(right, node))
            parens = isinstance(parent, (ast.Compare, ast.BinOp))
            if parens and isinstance(parent, ast.BinOp) and parent.op.__class__ == node.op.__class__:
                parens = False
            return ifparen(expr, parens)

        elif isinstance(node, ast.IfExp):
            ifexp = "if %s then %s else %s" % (
                self.expr_to_js(node.test, node, "if"),
                self.expr_to_js(node.body, node),
                self.expr_to_js(node.orelse, node)
            )
            return ifparen(ifexp, not isinstance(parent, ast.Return))

        elif isinstance(node, ast.Return):
            return "return %s" % self.expr_to_js(node.value, node)
        elif isinstance(node, (ast.List, ast.Tuple)):
            if context == "for-target":
                assert len(node.elts) == 2, "for-target tuple may have exactly two elements"
                return self.expr_to_js(node.elts)
            else:
                return "[%s]" % self.expr_to_js(node.elts)
        elif isinstance(node, ast.Lambda):
            subwalker = self.__class__()
            subwalker.generic_function(node, True, "", True)
            return subwalker.get_output()
        elif isinstance(node, (ast.GeneratorExp, ast.ListComp)):
            assert len(node.generators) == 1, "only one generator per listcomp supported"
            gen = node.generators[0]
            body = node.elt
            return "%s %s" % (self.expr_to_js(body), self.emit_for_fnode(gen))
        else:
            raise NotImplementedError("Node not implemented: %r", node)

    def emit_for_fnode(self, node):
        if isinstance(node.iter, ast.Attribute) and node.iter.attr == "_jsobj":
            node.iter = node.iter.value
            op = "in"
        else:
            op = "of"
        iterable = self.expr_to_js(node.iter, node)
        return "for %s %s %s" % (self.expr_to_js(node.target, node, "for-target"), op, iterable)

    def dotify_attribute(self, node):
        if node.value:
            prefix = "%s." % self.expr_to_js(node.value)
        else:
            prefix = ""
        return prefix + node.attr

    def transform_call_node(self, node):
        assert not node.kwargs, "kwargs not supported"
        assert not node.starargs, "starargs not supported"

        parens = True
        if len(node.args) == 1 and isinstance(node.args[0], (ast.Str, ast.Num, ast.Tuple, ast.List, ast.Name, ast.Attribute)):
            parens = False
        arglist = [self.expr_to_js(arg, node) for arg in node.args]
        callee = self.expr_to_js(node.func, node)
        if callee == "len":
            assert len(arglist) == 1, "len() called with != 1 args"
            return "%s.length" % arglist[0]
        else:
            if not arglist:
                return "%s!" % callee
            elif parens:
                return "%s(%s)" % (callee, ", ".join(arglist))
            else:
                return "%s %s" % (callee, ", ".join(arglist))

    def get_output(self):
        return self.stream.get_output()

    @classmethod
    def translate(cls, source, **kwargs):
        tree = ast.parse(source)
        translator = cls(**kwargs)
        translator.visit(tree)
        return translator.get_output()
