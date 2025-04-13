import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="ldmud-tracing",
    version="0.0.2",
    author="LDMud Team",
    author_email="ldmud-dev@UNItopia.DE",
    description="Python tracing package for LDMud",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ldmud/python-dbus",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    entry_points={
        'ldmud_efun': [
            'profile_call   = ldmud_tracing.profile:efun_profile_call',
            'trace_call     = ldmud_tracing.tracing:efun_trace_call',
        ],
        'ldmud_type': [
            'profile_result = ldmud_tracing.profile:profile_result',
            'trace_result   = ldmud_tracing.tracing:trace_result',
            'trace_cursor   = ldmud_tracing.tracing:trace_cursor',
        ]
    },
    zip_safe=False,
)
