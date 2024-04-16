# Python Tracing package for LDMud

Python package to provide tracing information to LPC.

This package provides the following types:
 * `profile_result`

This package contains the following efuns:
 * `profile_result profile_call(mixed& result, closure fun, mixed arg, ...)`

## Usage

### Install from the python package index

The efun package can be downloaded from the python package index:

```
pip3 install --user ldmud-tracing
```

### Build & install the package yourself

You can build the package yourself.

First clone the repository
```
git clone https://github.com/ldmud/python-tracing.git
```

Install the package
```
cd python-tracing
python3 setup.py install --user
```

### Automatically load the modules at startup

Also install the [LDMud Python efuns](https://github.com/ldmud/python-efuns) and use its
[startup.py](https://github.com/ldmud/python-efuns/blob/master/startup.py) as the Python startup script for LDMud.
It will automatically detect the installed Python efuns and load them.

### Manually load the modules at startup

Add the following lines to your startup script:
```
import ldmud_tracing.profile

ldmud_tracing.profile.register()
```

## Profiling

The `profile_call` efun evaluates the given closure, any extra arguments will
be passed to the closure. The result will be assigned to the first argument
which needs to be passed as a reference.

The efun will return a `profile_result` object. This object provides evaluation
cost and elapsed time information for each executed LPC code line. A complete
list of functions is available in the efun documentation.

Have fun!
