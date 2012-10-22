def greet(name, greeting="Hello"):
	window.alert(greeting + ", " + name)

def hi_friends(greeting, names):
	for name in names:
		greet(name, greeting)
	if len(names) == 1:
		print "There was only one"

def foo(x = 60):
	print (5 + (3 + 4 * x))

def ifexpr(a, b):
	return (1 if a else b)

def constant_expr_fold_test():
	return (5 * 5) + (3 * 3)

def forin(it):
	for a, b in it._jsobj:
		print a, b

def implicit_return(a):
	35 + a

def list_of_lambdas(x):
	return [
		lambda f: x + f,
		lambda f: x - f
	]

def test(script):

	tree = ast.parse(script)
	nv = Walker()
	nv.visit(tree)

	python_code = script.strip()
	coco_code = "\n".join(nv.stream.output)
	js_code = pipe_output("coco -cbs", coco_code)
	a=[x+5 for x in c]
	print "\n===============\n".join(number_lines(s) for s in [python_code, coco_code, js_code])
