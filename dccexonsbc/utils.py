import importlib, pathlib
import importlib.machinery
import importlib.util

def load_module_from_file(filepath):
    path = pathlib.Path(filepath)
    name = path.stem

    loader = importlib.machinery.SourceFileLoader( name, filepath)
    spec = importlib.util.spec_from_loader( name, loader )
    module = importlib.util.module_from_spec( spec )
    loader.exec_module( module )

    return module

def hardware_setup_function_from(modulename):
    if modulename.endswith(".py"):
        module = load_module_from_file(modulename)
    else:
        module = importlib.import_module(modulename)

    func = getattr(module, "hardware_setup", None)
    if func:
        return func
    else:
        warnings.warn(f"{modulename} does not contain a "
                      "hardware_setup() function.")
        return None

def hardware_setup_functions(modules):
    for modulename in modules:
        f = hardware_setup_function_from(modulename)
        if f is not None:
            yield f
            
