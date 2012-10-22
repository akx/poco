from poco import translate
from subprocess import Popen, PIPE

def pipe_output(args, input):
    stdout, stderr = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True).communicate(input)
    if stderr:
        print stderr
        raise ValueError("pipe_output failed, stderr printed")
    return stdout


def number_lines(str):
    return "\n".join("%06d %s" % (i + 1, l) for i, l in enumerate(str.splitlines()))


def test(script):
    python_code = script.strip()
    coco_code = translate(python_code)
    js_code = pipe_output("coco -cbs", coco_code)
    print "\n===============\n".join(number_lines(s) for s in [python_code, coco_code, js_code])


def main():
    test(file("test-script.py", "rb").read())


if __name__ == '__main__':
    main()
