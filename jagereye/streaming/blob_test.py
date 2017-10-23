from jagereye.streaming.blob import Blob

import unittest
import numpy as np

def create_blob(tensor_name=None, tensor=None):
    blob = Blob()
    if not (tensor_name is None) and not (tensor is None):
        blob.feed(tensor_name, tensor)
    return blob

class BlobTest(unittest.TestCase):

    def test_feed_with_non_string_name(self):
        blob = Blob()
        with self.assertRaises(TypeError):
            blob.feed(100, np.array([]))

    def test_feed_non_ndarray(self):
        blob = Blob()
        for non_tensor in [100, [100], 'str']:
            with self.assertRaises(TypeError):
                blob.feed('non__ndarray', non_tensor)

    def test_feed_non_float_like_ndarray(self):
        blob = Blob()
        for dtype in [np.complex64, np.complex128, np.complex256,
                      np.object, np.str, np.unicode, np.void]:
            tensor = np.array([]).astype(dtype)
            with self.assertRaises(TypeError):
                blob.feed('non_float_like_ndarray', tensor)

    def test_feed_float_like_ndarray(self):
        blob = Blob()
        for dtype in [np.int8, np.int16, np.int32, np.int64,
                      np.uint8, np.uint16, np.uint32, np.uint64,
                      np.float16, np.float32, np.float64, np.float128,
                      np.bool]:
            tensor = np.random.rand(1, 2, 3).astype(dtype)
            np.testing.assert_equal(tensor, blob.feed('float_like_ndarray', tensor))

    def test_has_with_non_string_name(self):
        blob = create_blob()
        with self.assertRaises(TypeError):
            blob.has(100)

    def test_has_with_none_existing_name(self):
        blob = create_blob()
        self.assertFalse(blob.has('non_existing'))

    def test_has_with_existing_name(self):
        blob = create_blob('existing', np.array([]))
        self.assertTrue(blob.has('existing'))

    def test_fetch_with_non_string_name(self):
        blob = create_blob()
        with self.assertRaises(TypeError):
            blob.fetch(100)

    def test_fetch_with_non_existing_name(self):
        blob = create_blob()
        with self.assertRaises(RuntimeError):
            blob.fetch('non_existing')

    def test_fetch_with_existing_name(self):
        tensor = np.random.rand(1, 2, 3)
        blob = create_blob('existing', tensor)
        np.testing.assert_equal(tensor, blob.fetch('existing'))

    def test_remove_with_non_string_name(self):
        blob = create_blob()
        with self.assertRaises(TypeError):
            blob.remove(100)

    def test_remove_with_non_existing_name(self):
        blob = create_blob()
        with self.assertRaises(RuntimeError):
            blob.remove('non_existing')

    def test_remove_with_existing_name(self):
        tensor = np.random.rand(1, 2, 3)
        blob = create_blob('existing', tensor)
        np.testing.assert_equal(tensor, blob.remove('existing'))
        # Check the tensor is removed
        with self.assertRaises(RuntimeError):
            blob.remove('existing')

    def test_copy(self):
        tensor_i = np.array([1, 2, 3])
        tensor_f = np.array([1.0, 2.0, 3.0])
        tensor_b = np.array([True, False, False])

        blob = create_blob()
        blob.feed('tensor_f', tensor_f)
        blob.feed('tensor_i', tensor_i)
        blob.feed('tensor_b', tensor_b)

        c_blob = blob.copy()
        np.testing.assert_equal(blob.fetch('tensor_f'), c_blob.fetch('tensor_f'))
        np.testing.assert_equal(blob.fetch('tensor_i'), c_blob.fetch('tensor_i'))
        np.testing.assert_equal(blob.fetch('tensor_b'), c_blob.fetch('tensor_b'))

if __name__ == '__main__':
    unittest.main()
