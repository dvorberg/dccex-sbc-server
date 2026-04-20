import sys, io
import termcolor

_debug=True
_comdebug=True

def make_printable(arg):
    if type(arg) is bytes:
        return arg.decode("ascii", "ignore").rstrip()
    elif type(arg) is str:
        return arg.rstrip()
    else:
        return arg

def _debug(doit:bool, *args, color="black", **kw):
    if doit:
        if len(args) == 0:
            sys.stderr.write("\n")
        else:
            args = [ make_printable(arg) for arg in args ]
            
            out = io.StringIO()
            print(*args, **kw, file=out)
            s = out.getvalue()

            termcolor.cprint(s, color, end="")
        sys.stderr.flush()

def debug(*args, color="grey", **kw):
    _debug(_debug, *args, color=color, **kw)

def comdebug(*args, color="light_grey", **kw):
    _debug(_comdebug, *args, color=color, **kw)
