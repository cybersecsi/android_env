"""Tests for android_env.components.remote_controller."""

import time

from absl.testing import absltest
from android_env.components import action_type
from android_env.components import adb_controller
from android_env.components import dumpsys_thread
from android_env.components import emulator_simulator
from android_env.components import errors
from android_env.components import logcat_thread
from android_env.components import remote_controller
from android_env.components import setup_step_interpreter
from android_env.proto import task_pb2
import mock
import numpy as np


class RemoteControllerTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.addCleanup(mock.patch.stopall)  # Disable previous patches.

    self._adb_controller = mock.create_autospec(adb_controller.AdbController)
    self._simulator = mock.create_autospec(emulator_simulator.EmulatorSimulator)
    self._setup_step_interpreter = mock.create_autospec(
        setup_step_interpreter.SetupStepInterpreter)
    self._dumpsys_thread = mock.create_autospec(dumpsys_thread.DumpsysThread)
    self._logcat_thread = mock.create_autospec(logcat_thread.LogcatThread)

    mock.patch.object(
        adb_controller, 'AdbController',
        return_value=self._adb_controller).start()
    mock.patch.object(
        setup_step_interpreter,
        'SetupStepInterpreter',
        return_value=self._setup_step_interpreter).start()
    mock.patch.object(
        dumpsys_thread, 'DumpsysThread',
        return_value=self._dumpsys_thread).start()
    mock.patch.object(
        logcat_thread, 'LogcatThread',
        return_value=self._logcat_thread).start()

    self._remote_controller = remote_controller.RemoteController(
        self._simulator,
        task=task_pb2.Task(),
        max_bad_states=3,
        dumpsys_check_frequency=100,
        max_failed_current_activity=3,
        step_timeout_sec=2,
        expected_fps=60,
        periodic_restart_time_min=0)

  def test_restart(self):
    self._remote_controller.restart()
    assert hasattr(self._remote_controller, '_logcat_thread')

  def test_reset(self):
    self._remote_controller.reset()
    assert hasattr(self._remote_controller, '_logcat_thread')
    assert hasattr(self._remote_controller, '_dumpsys_thread')

  def test_get_current_reward(self):
    self._remote_controller._logcat_thread.get_and_reset_reward.return_value = 1.0
    reward = self._remote_controller.get_current_reward()
    self.assertEqual(reward, 1.0)

  def test_get_current_reward_none(self):
    self._remote_controller._logcat_thread.get_and_reset_reward.return_value = None
    reward = self._remote_controller.get_current_reward()
    self.assertEqual(reward, 0.0)

  def test_get_current_extras(self):
    expected_extra = {'extra': 0}
    self._remote_controller._logcat_thread.get_and_reset_extras.return_value = expected_extra
    extra = self._remote_controller.get_current_extras()
    self.assertDictEqual(extra, expected_extra)

  def test_get_current_extras_none(self):
    self._remote_controller._logcat_thread.get_and_reset_extras.return_value = {}
    extra = self._remote_controller.get_current_extras()
    self.assertDictEqual(extra, {})

  def test_check_episode_end(self):
    self._remote_controller._logcat_thread.get_and_reset_episode_end.return_value = True
    episode_end = self._remote_controller.check_episode_end()
    self.assertTrue(episode_end)

  def test_get_current_observation(self):
    self._simulator.get_observation.return_value = {'observation': 0}
    observation = self._remote_controller.get_current_observation(
        wait_for_next_frame=False)
    self.assertDictEqual(observation, {'observation': 0})

  def test_get_current_observation_error(self):
    self._simulator.get_observation.side_effect = errors.ReadObservationError()
    observation = self._remote_controller.get_current_observation(
        wait_for_next_frame=False)
    self.assertTrue(self._remote_controller._should_restart)
    self.assertIsNone(observation)

  def test_execute_action_touch(self):
    self._simulator.send_action.return_value = True
    action = {'action_type': np.array(action_type.ActionType.TOUCH)}
    self._remote_controller.execute_action(action)
    self._simulator.send_action.assert_called_once_with(action)

  def test_execute_action_repeat(self):
    self._simulator.send_action.return_value = True
    self._remote_controller.execute_action(
        {'action_type': np.array(action_type.ActionType.REPEAT)})
    self._simulator.send_action.assert_not_called()

  def test_execute_action_error(self):
    self._simulator.send_action.side_effect = errors.SendActionError
    self._remote_controller.execute_action(
        {'action_type': np.array(action_type.ActionType.TOUCH)})
    self.assertTrue(self._remote_controller._should_restart)

  def test_check_timeout_false(self):
    self._remote_controller._latest_observation_local_time = time.time()
    timeout = self._remote_controller.check_timeout()
    self.assertFalse(timeout)

  def test_check_timeout_true(self):
    self._remote_controller._latest_observation_local_time = time.time()
    time.sleep(3)
    timeout = self._remote_controller.check_timeout()
    self.assertTrue(timeout)

  def test_max_restarts_adb_error(self):
    # The method was called once at init.
    init_fn_call = self._simulator.create_adb_controller.call_count
    self._simulator.create_adb_controller.side_effect = (
        errors.AdbControllerError)
    self.assertRaises(errors.TooManyRestartsError,
                      self._remote_controller.restart)
    # The method was called three more times when attempting to restart.
    self.assertEqual(init_fn_call + 3,
                     self._simulator.create_adb_controller.call_count)

  def test_max_restarts_setup_steps(self):
    init_fn_call = self._setup_step_interpreter.interpret.call_count
    self._setup_step_interpreter.interpret.side_effect = errors.StepCommandError
    self.assertRaises(errors.TooManyRestartsError,
                      self._remote_controller.restart)
    # The method was called three more times when attempting to restart.
    self.assertEqual(init_fn_call + 3,
                     self._setup_step_interpreter.interpret.call_count)


if __name__ == '__main__':
  absltest.main()
