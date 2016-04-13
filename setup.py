import sys

from setuptools import setup, find_packages


PY3 = (sys.version_info.major == 3)

install_requires = [
    "requests",
],

extras_require = {
    "gevent": [
        "gevent",
    ],

    "pyramid": [
        "pyramid",
    ],

    "cassandra": [
        "cassandra",
    ],

    "redis": [
        "redis",
    ],
}

# I'm kinda abusing tests_require as a general "dev requirements" list
tests_require = [
    "nose",
    "coverage",

    "pyramid",
    "webtest",

    "sphinx",
    "sphinxcontrib-spelling",
    "alabaster",
    "pyenchant",

    "thrift",
    "posix_ipc",
]

if not PY3:
    tests_require.append("mock")


setup(
    name="baseplate",
    version="0.7.0",
    packages=find_packages(exclude=["tests"]),

    install_requires=install_requires,
    extras_require=extras_require,

    tests_require=tests_require,

    scripts=[
        "bin/baseplate-serve{:d}".format(sys.version_info.major),
    ],

    # the thrift compiler must be able to find baseplate.thrift to build
    # services which extend BaseplateService.
    package_data={
        "baseplate.thrift": [
            "*.thrift"
        ],
    },
    zip_safe=False,
    entry_points={
        "distutils.commands": [
            "build_thrift = baseplate.integration.thrift.command:BuildThriftCommand",
        ],

        "console_scripts": [
            "baseplate-healthcheck{:d} = baseplate.server.healthcheck:run_healthchecks".format(sys.version_info.major),
        ],
    },

    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
)
