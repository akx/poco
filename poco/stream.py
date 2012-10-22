class StreamIndent(object):
    def __init__(self, stream):
        self.stream = stream

    def __enter__(self):
        self.stream.indent += 1

    def __exit__(self, et, ev, tb):
        self.stream.indent -= 1


class CodeStream(object):
    def __init__(self):
        self.output = []
        self.indent = 0
        self._write = getattr(self, "_write", None) or self.output.append

    def enter(self, prelude=None):
        if prelude:
            self.write(prelude)
        return StreamIndent(self)

    def write(self, string):
        for line in (string.splitlines() if "\n" in string else [string]):
            self._write("\t" * self.indent + line)

    def get_output(self):
        return "\n".join(self.output)


class StdoutCodeStream(CodeStream):
    def _write(self, string):
        sys.stdout.write(string + "\n")
