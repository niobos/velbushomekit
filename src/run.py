import sys
import os
import runpy
path = os.path.dirname(sys.modules[__name__].__file__)
sys.path.insert(0, path)
runpy.run_module('velbushomekit', run_name="__main__", alter_sys=True)
