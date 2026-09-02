import inspect, os
import rich.console as rc
src = inspect.getsource(rc.Console.size.fget)
print(src)
