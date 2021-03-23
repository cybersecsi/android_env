"""Tests for android_env.components.utils."""

import os  # copybara:strip

from absl.testing import absltest
from absl.testing import parameterized
from android_env.components import utils
# copybara:strip_begin
from android_env.proto import task_pb2
from dm_env import specs
import ml_collections as collections
# copybara:strip_end
import numpy as np


class UtilsTest(parameterized.TestCase):

  @parameterized.parameters(
      ([0.5, 0.5], [320, 480], (160, 240)),
      ([0.25, 0.75], [320, 480], (80, 360)),
      ([0.0, 0.0], [320, 480], (0, 0)),
      ([1.0, 1.0], [320, 480], (319, 479)),
      )
  def test_touch_position_to_pixel_position(
      self, touch_pos, width_height, pixel_pos):
    self.assertEqual(utils.touch_position_to_pixel_position(
        np.array(touch_pos), width_height), pixel_pos)

  def test_transpose_pixels(self):
    image = np.reshape(np.array(range(12)), (3, 2, 2))
    expected = [[[0, 1], [4, 5], [8, 9]], [[2, 3], [6, 7], [10, 11]]]
    self.assertEqual(utils.transpose_pixels(image).shape, (2, 3, 2))
    self.assertTrue((utils.transpose_pixels(image) == expected).all())

  def test_orient_pixels(self):
    image = np.reshape(np.array(range(12)), (3, 2, 2))

    expected_90 = [[[8, 9], [4, 5], [0, 1]], [[10, 11], [6, 7], [2, 3]]]
    rot_90 = task_pb2.AdbCall.Rotate.Orientation.LANDSCAPE_90
    rotated = utils.orient_pixels(image, rot_90)
    self.assertEqual(rotated.shape, (2, 3, 2))
    self.assertTrue((rotated == expected_90).all())

    expected_180 = [[[10, 11], [8, 9]], [[6, 7], [4, 5]], [[2, 3], [0, 1]]]
    rot_180 = task_pb2.AdbCall.Rotate.Orientation.PORTRAIT_180
    rotated = utils.orient_pixels(image, rot_180)
    self.assertEqual(rotated.shape, (3, 2, 2))
    self.assertTrue((rotated == expected_180).all())

    expected_270 = [[[2, 3], [6, 7], [10, 11]], [[0, 1], [4, 5], [8, 9]]]
    rot_270 = task_pb2.AdbCall.Rotate.Orientation.LANDSCAPE_270
    rotated = utils.orient_pixels(image, rot_270)
    self.assertEqual(rotated.shape, (2, 3, 2))
    self.assertTrue((rotated == expected_270).all())

    rot_0 = task_pb2.AdbCall.Rotate.Orientation.PORTRAIT_0
    rotated = utils.orient_pixels(image, rot_0)
    self.assertEqual(rotated.shape, (3, 2, 2))
    self.assertTrue((rotated == image).all())

  # copybara:strip_begin
  def test_instantiate_class(self):
    # Instantiate an arbitrary class by name and verify that it's not None.
    array_spec = utils.instantiate_class(
        'dm_env.specs.Array', shape=(1, 2, 3), dtype=np.uint16)
    self.assertIsNotNone(array_spec)
    # Also verify that it produced what we expect.
    self.assertEqual(array_spec, specs.Array(shape=(1, 2, 3), dtype=np.uint16))

  def test_get_class_default_params(self):

    class TestClass():

      def __init__(self, arg0, arg1='arg1', arg2=324, arg3=None, **kwargs):
        pass

    kwargs = utils.get_class_default_params(TestClass)
    self.assertEqual({'arg1': 'arg1', 'arg2': 324, 'arg3': None}, kwargs)

  def test_merge_settings(self):
    config = collections.ConfigDict({
        'int_arg': 1,
        'bool_arg': True,
        'tuple_arg': (3, 3),
        'float_arg': 2.3,
        'dict_arg': {
            'a': 'x',
            'b': (2, 3),
            'c': 'foo'
        },
        'list_arg': [2, 3, 4],
        'nested_tuple_arg': ((2, 3), (4, 5, 6)),
        'nested_list_arg': [[2, 3], [4, 5, 6]],
        'extra_nested_list_arg': [[2, 2], [2]],
        'extra_arg': 'extra',
    })
    # Settings is expected to be a flat dictionary of strings.
    settings = {
        'int_arg': '3',
        'bool_arg': 'false',
        'tuple_arg.1': '3',
        'tuple_arg.2': '4',
        'float_arg': '3.4',
        'dict_arg.b.1': '5',
        'dict_arg.a': 'y',
        'list_arg.1': '5',
        'list_arg.2': '6',
        'nested_tuple_arg.1.1': '7.3',
        'nested_tuple_arg.1.2': '8',
        'nested_tuple_arg.1.3': '9',
        'nested_tuple_arg.2.1': '1',
        'nested_tuple_arg.2.2': '2',
        'nested_list_arg.1.1': '1',
        'nested_list_arg.1.2': '1',
        'nested_list_arg.1.3': '1',
        'nested_list_arg.2.1': '1',
        'nested_list_arg.2.2': '1',
    }
    kwargs = utils.merge_settings(config, settings)
    expected = {
        'int_arg': 3,
        'bool_arg': False,
        'tuple_arg': [3, 4],
        'float_arg': 3.4,
        'dict_arg': {
            'a': 'y',
            'b': [5,],
            'c': 'foo',
        },
        'list_arg': [5, 6],
        'nested_tuple_arg': [[7.3, 8, 9], [1, 2]],
        'nested_list_arg': [[1, 1, 1], [1, 1]],
        'extra_nested_list_arg': [[2, 2], [2]],
        'extra_arg': 'extra',
    }
    for k, v in kwargs.items():
      self.assertEqual(expected[k], v)
    self.assertEqual(expected, kwargs)

  def test_expand_vars(self):
    os.environ['VAR1'] = 'value1'
    dictionary = {
        'not_expanded1': 'VAR1',
        'not_expanded2': 100,
        'not_expanded3': ['$VAR1', '${VAR1}'],
        'not_expanded4': '${ENV_VAR_THAT_DOES_NOT_EXIST}',
        'not_expanded5': '${ENV_VAR_THAT_DOES_NOT_EXIST:=default_value}',
        'expanded1': '$VAR1',
        'expanded2': '${VAR1}',
        'expanded3': 'text$VAR1/text',
        'expanded4': 'text${VAR1}moretext',
        'expanded5': 'text${VAR1}moretext$VAR1',
        '${VAR1}notexpandedinkeys': 'foo',
        'nested_dict': {
            'expanded': '$VAR1',
            'not_expanded': 'VAR1',
            'nested_nested_dict': {
                'expanded': '$VAR1'
            },
        },
    }
    output = utils.expand_vars(dictionary)
    expected_output = {
        'not_expanded1': 'VAR1',
        'not_expanded2': 100,
        'not_expanded3': ['$VAR1', '${VAR1}'],
        'not_expanded4': '${ENV_VAR_THAT_DOES_NOT_EXIST}',
        'not_expanded5': '${ENV_VAR_THAT_DOES_NOT_EXIST:=default_value}',
        'expanded1': 'value1',
        'expanded2': 'value1',
        'expanded3': 'textvalue1/text',
        'expanded4': 'textvalue1moretext',
        'expanded5': 'textvalue1moretextvalue1',
        '${VAR1}notexpandedinkeys': 'foo',
        'nested_dict': {
            'expanded': 'value1',
            'not_expanded': 'VAR1',
            'nested_nested_dict': {
                'expanded': 'value1'
            },
        },
    }
    self.assertEqual(expected_output, output)

  def test_convert_int_to_float_bounded_array(self):
    spec = specs.BoundedArray(
        shape=(4,),
        dtype=np.int32,
        minimum=[0, 1, 10, -2],
        maximum=[5, 5, 20, 2],
        name='bounded_array')
    data = np.array([2, 2, 10, 0], dtype=np.int32)
    float_data = utils.convert_int_to_float(data, spec, np.float64)
    np.testing.assert_equal(
        np.array([2. / 5., 1. / 4., 0., 0.5], dtype=np.float64), float_data)

  def test_convert_int_to_float_bounded_array_broadcast(self):
    spec = specs.BoundedArray(
        shape=(3,), dtype=np.int16, minimum=2, maximum=4, name='bounded_array')
    data = np.array([2, 3, 4], dtype=np.int16)
    float_data = utils.convert_int_to_float(data, spec, np.float32)
    np.testing.assert_equal(
        np.array([0.0, 0.5, 1.0], dtype=np.float32), float_data)

  def test_convert_int_to_float_no_bounds(self):
    spec = specs.Array(
        shape=(3,),
        dtype=np.int8,  # int8 implies min=-128, max=127
        name='bounded_array')
    data = np.array([-128, 0, 127], dtype=np.int16)
    float_data = utils.convert_int_to_float(data, spec, np.float32)
    np.testing.assert_equal(
        np.array([0.0, 128. / 255., 1.0], dtype=np.float32), float_data)
  # copybara:strip_end

if __name__ == '__main__':
  absltest.main()
