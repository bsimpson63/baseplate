from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from ... import mock

try:
    import pymemcache
except ImportError:
    raise unittest.SkipTest("pymemcache is not installed")
else:
    del pymemcache

from baseplate._compat import builtins
from baseplate.config import ConfigurationError
from baseplate.context.memcache import pool_from_config
from baseplate.context.memcache import lib as memcache_lib


class PoolFromConfigTests(unittest.TestCase):
    def test_empty_config(self):
        with self.assertRaises(ConfigurationError):
            pool_from_config({})

    def test_basic_url(self):
        pool = pool_from_config({
            "memcache.endpoint": "localhost:1234",
        })

        self.assertEqual(pool.server[0], "localhost")
        self.assertEqual(pool.server[1], 1234)

    def test_timeouts(self):
        pool = pool_from_config({
            "memcache.endpoint": "localhost:1234",
            "memcache.timeout": 1.23,
            "memcache.connect_timeout": 4.56,
        })

        self.assertEqual(pool.timeout, 1.23)
        self.assertEqual(pool.connect_timeout, 4.56)

    def test_max_connections(self):
        pool = pool_from_config({
            "memcache.endpoint": "localhost:1234",
            "memcache.max_pool_size": 300,
        })

        self.assertEqual(pool.client_pool.max_size, 300)

    def test_alternate_prefix(self):
        pool_from_config({
            "noodle.endpoint": "localhost:1234",
        }, prefix="noodle.")


class BaseSerdeTests(unittest.TestCase):
    def test_serialize_str(self):
        pickle_no_compress = memcache_lib.make_pickle_and_compress_fn()
        value, flags = pickle_no_compress(key="key", value="val")
        self.assertEqual(value, "val")
        self.assertEqual(flags, 0)

    def test_serialize_int(self):
        pickle_no_compress = memcache_lib.make_pickle_and_compress_fn()
        value, flags = pickle_no_compress(key="key", value=100)
        self.assertEqual(value, "100")
        self.assertEqual(flags, memcache_lib.Flags.INTEGER)

    def test_serialize_long(self):
        try:
            long
        except NameError:
            # python3
            value = 100
            expected_flags = memcache_lib.Flags.INTEGER
        else:
            value = long(100)
            expected_flags = memcache_lib.Flags.LONG

        pickle_no_compress = memcache_lib.make_pickle_and_compress_fn()
        value, flags = pickle_no_compress(key="key", value=value)
        self.assertEqual(value, "100")
        self.assertEqual(flags, expected_flags)

    def test_serialize_other(self):
        pickle_patch = mock.patch.object(memcache_lib, "pickle")
        pickle = pickle_patch.start()
        self.addCleanup(pickle_patch.stop)

        pickle_no_compress = memcache_lib.make_pickle_and_compress_fn()
        value, flags = pickle_no_compress(key="key", value=("stuff", 1, False))

        pickle.dumps.assertCalledWith(("stuff", 1, False), protocol=2)
        self.assertEqual(flags, memcache_lib.Flags.PICKLE)

    def test_deserialize_str(self):
        value = memcache_lib.decompress_and_unpickle(
            key="key", serialized="val", flags=0)
        self.assertEqual(value, "val")

    def test_deserialize_int(self):
        value = memcache_lib.decompress_and_unpickle(
            key="key", serialized="100", flags=memcache_lib.Flags.INTEGER)
        self.assertEqual(value, 100)
        self.assertTrue(isinstance(value, int))

    def test_deserialize_long(self):
        value = memcache_lib.decompress_and_unpickle(
            key="key", serialized="100", flags=memcache_lib.Flags.LONG)

        try:
            expected_class = long
        except NameError:
            # python3
            expected_class = int

        self.assertEqual(value, 100)
        self.assertTrue(isinstance(value, expected_class))

    def test_deserialize_other(self):
        pickle_patch = mock.patch.object(memcache_lib, "pickle")
        pickle = pickle_patch.start()
        self.addCleanup(pickle_patch.stop)

        expected_value = object()
        pickle.loads.return_value = expected_value

        value = memcache_lib.decompress_and_unpickle(
            key="key", serialized="garbage", flags=memcache_lib.Flags.PICKLE)

        pickle.loads.assertCalledWith("garbage")
        self.assertEqual(value, expected_value)


class CompressionSerdeTests(unittest.TestCase):
    def test_serialize_no_compress(self):
        zlib_patch = mock.patch.object(memcache_lib, "zlib")
        zlib = zlib_patch.start()
        self.addCleanup(zlib_patch.stop)

        pickle_no_compress = memcache_lib.make_pickle_and_compress_fn(
            min_compress_length=0,  # disable compression
        )
        value, flags = pickle_no_compress(key="key", value="simple string")
        self.assertEqual(value, "simple string")
        self.assertEqual(flags, 0)
        zlib.compress.assertNotCalled()

    def test_serialize_compress(self):
        zlib_patch = mock.patch.object(memcache_lib, "zlib")
        zlib = zlib_patch.start()
        self.addCleanup(zlib_patch.stop)

        expected_value = object()
        zlib.compress.return_value = expected_value

        pickle_and_compress = memcache_lib.make_pickle_and_compress_fn(
            min_compress_length=1,
            compress_level=1,
        )
        value, flags = pickle_and_compress(key="key", value="simple string")
        self.assertEqual(value, expected_value)
        self.assertEqual(flags, memcache_lib.Flags.ZLIB)
        zlib.compress.assertCalledWith("simple string", 1)

    def test_deserialize_no_decompress(self):
        zlib_patch = mock.patch.object(memcache_lib, "zlib")
        zlib = zlib_patch.start()
        self.addCleanup(zlib_patch.stop)

        value = memcache_lib.decompress_and_unpickle(
            key="key", serialized="stuff", flags=0)
        self.assertEqual(value, "stuff")
        zlib.decompress.assertNotCalled()

    def test_deserialize_decompress_str(self):
        zlib_patch = mock.patch.object(memcache_lib, "zlib")
        zlib = zlib_patch.start()
        self.addCleanup(zlib_patch.stop)

        expected_value = object()
        zlib.decompress.return_value = expected_value

        flags = 0 | memcache_lib.Flags.ZLIB
        value = memcache_lib.decompress_and_unpickle(
            key="key", serialized="nonsense", flags=flags)
        self.assertEqual(value, expected_value)
        zlib.decompress.assertCalledWith("nonsense")

    def test_deserialize_decompress_int(self):
        zlib_patch = mock.patch.object(memcache_lib, "zlib")
        zlib = zlib_patch.start()
        self.addCleanup(zlib_patch.stop)

        expected_zlib_value = object()
        zlib.decompress.return_value = expected_zlib_value

        int_patch = mock.patch.object(builtins, "int")
        int_cls = int_patch.start()
        self.addCleanup(int_patch.stop)

        expected_int_value = object()
        int_cls.return_value = expected_int_value
        flags = memcache_lib.Flags.INTEGER | memcache_lib.Flags.ZLIB
        value = memcache_lib.decompress_and_unpickle(
            key="key", serialized="nonsense", flags=flags)
        zlib.decompress.assertCalledWith("nonsense")
        int_cls.assertCalledWith(expected_zlib_value)
        self.assertEqual(value, expected_int_value)

    def test_deserialize_decompress_long(self):
        zlib_patch = mock.patch.object(memcache_lib, "zlib")
        zlib = zlib_patch.start()
        self.addCleanup(zlib_patch.stop)

        expected_zlib_value = object()
        zlib.decompress.return_value = expected_zlib_value

        long_patch = mock.patch.object(memcache_lib, "long")
        long_cls = long_patch.start()
        self.addCleanup(long_patch.stop)

        expected_long_value = object()
        long_cls.return_value = expected_long_value
        flags = memcache_lib.Flags.LONG | memcache_lib.Flags.ZLIB
        value = memcache_lib.decompress_and_unpickle(
            key="key", serialized="nonsense", flags=flags)
        zlib.decompress.assertCalledWith("nonsense")
        long_cls.assertCalledWith(expected_zlib_value)
        self.assertEqual(value, expected_long_value)

    def test_deserialize_decompress_unpickle(self):
        zlib_patch = mock.patch.object(memcache_lib, "zlib")
        zlib = zlib_patch.start()
        self.addCleanup(zlib_patch.stop)

        expected_zlib_value = object()
        zlib.decompress.return_value = expected_zlib_value

        pickle_patch = mock.patch.object(memcache_lib, "pickle")
        pickle = pickle_patch.start()
        self.addCleanup(pickle_patch.stop)

        expected_pickle_value = object()
        pickle.loads.return_value = expected_pickle_value

        flags = memcache_lib.Flags.PICKLE | memcache_lib.Flags.ZLIB
        value = memcache_lib.decompress_and_unpickle(
            key="key", serialized="nonsense", flags=flags)
        zlib.decompress.assertCalledWith("nonsense")
        pickle.loads.assertCalledWith(expected_zlib_value)
        self.assertEqual(value, expected_pickle_value)
