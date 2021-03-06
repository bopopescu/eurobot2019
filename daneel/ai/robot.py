#!/usr/bin/python3
import sys
import map
import datetime
import argparse

import communication
import ivy_robot
from io_robot import *
from locomotion.locomotion import *
from behavior import Behaviors
from table.table import Table
from robot_parts import AtomStorage

TRACE_FILE = "/home/pi/code/primary_robot/ai/log/log_"+str(datetime.datetime.now()).replace(' ', '_')

robot = None

BEHAVIOR_DEFAULT = Behaviors.FSMMatch.value
IVY_ADDRESS_DEFAULT = "192.168.1.255:2010"
LIDAR_MASK_FILE = "data/obstacles_lidar_mask.yaml"
STATIC_OBSTACLES_FILE = "data/obstacles_2019.yaml"
TEENSY_SERIAL_PATH_DEFAULT = "/dev/ttyAMA0"


class Robot(object):
    def __init__(self, behavior=BEHAVIOR_DEFAULT, ivy_address=IVY_ADDRESS_DEFAULT,
                 static_obstacles_file=STATIC_OBSTACLES_FILE, lidar_mask_file=LIDAR_MASK_FILE,
                 teensy_serial_path=TEENSY_SERIAL_PATH_DEFAULT):
        self.map = map.Map(self, static_obstacles_file, lidar_mask_file)
        self.table = Table(self)
        self.storages = {AtomStorage.Side.RIGHT: AtomStorage(robot, AtomStorage.Side.RIGHT),
                         AtomStorage.Side.LEFT: AtomStorage(robot, AtomStorage.Side.LEFT)}
        self.communication = communication.Communication(teensy_serial_path)
        self.communication.start()
        self.io = IO(self)
        self.locomotion = Locomotion(self)
        self.ivy = ivy_robot.Ivy(self, ivy_address)
        if behavior == Behaviors.FSMMatch.value:
            from behavior.fsmmatch import FSMMatch
            self.behavior = FSMMatch(self)
        elif behavior == Behaviors.FSMTests.value:
            raise NotImplementedError("This behavior is not implemented yet !")
        elif behavior == Behaviors.Slave.value:
            from behavior.slave import Slave
            self.behavior = Slave(self)
        else:
            raise NotImplementedError("This behavior is not implemented yet !")

    @property
    def right_storage(self):
        return self.storages[AtomStorage.Side.RIGHT]

    @property
    def left_storage(self):
        return self.storages[AtomStorage.Side.LEFT]


def main():
    global robot
    robot = Robot(behavior=parsed_args.behavior, ivy_address=parsed_args.ivy, lidar_mask_file=parsed_args.mask,
                  teensy_serial_path=parsed_args.teensy_serial)
    # Arguments parsing
    robot.communication.mock_communication = parsed_args.no_teensy
    robot.communication.register_callback(communication.eTypeUp.ODOM_REPORT,
                                          lambda x, y, t: robot.ivy.send_robot_position())
    robot.communication.register_callback(communication.eTypeUp.HMI_STATE,
                                          lambda cord, b1, b2, lr, lg, lb: print("c: {}, b1: {}, b2: {}".format(
                                            robot.io.cord_state, robot.io.button1_state, robot.io.button2_state)))
    #robot.communication.register_callback(communication.eTypeUp.HMI_STATE, new_hmi_state_callback)
    # robot.communication.register_callback(communication.eTypeUp.ODOM_REPORT,
    #                                       robot.locomotion.handle_new_odometry_report)
    # robot.communication.register_callback(communication.eTypeUp.ODOM_REPORT, lambda o, n, x, y, t: print(
    #     "X : {}, Y : {}, Theta : {}".format(robot.locomotion.x, robot.locomotion.y, robot.locomotion.theta)))
    last_behavior_time = time.time()
    last_locomotion_time = time.time()
    while True:
        robot.communication.check_message(10)
        if time.time() - last_locomotion_time >= 0.05:
            robot.locomotion.locomotion_loop(obstacle_detection=True)
        if time.time() - last_behavior_time >= 0.2:
            robot.behavior.loop()
            last_behavior_time = time.time()


if __name__ == '__main__':
    parser = argparse.ArgumentParser("AI option parser", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--no_teensy', action='store_true', default=False,
                        help="Mock communications with teensy")
    parser.add_argument('-b', '--behavior', type=str, default=BEHAVIOR_DEFAULT,
                        help="The robot behavior. Available : \n{}".format(
                            "\n".join("\t* {}".format(k) for k in [e.value for e in list(Behaviors)])))
    parser.add_argument('-i', '--ivy', type=str, default=IVY_ADDRESS_DEFAULT,
                        help="The ivy bus address.")
    parser.add_argument('-m', '--mask', type=str, default=LIDAR_MASK_FILE,
                        help="Path to YAML file containing obstacle detection lidar masks")
    parser.add_argument('-t', '--teensy_serial', type=str, default=TEENSY_SERIAL_PATH_DEFAULT,
                        help="Path to serial plugged to Teensy.")
    parsed_args = parser.parse_args()
    # if __debug__:
    #     with open(TRACE_FILE, 'w') as sys.stdout:
    #         main()
    # else:
    main()


def new_hmi_state_callback(cord_state, button1_state, button2_state, red_led_state, green_led_state, blue_led_state):
    if __debug__:
        print("[Comm] New HMI State : cord : {}; b1 : {}; b2 : {}; red LED : {}; green LED : {}; blue LED : {}".format(
            cord_state, button1_state, button2_state, red_led_state, green_led_state, blue_led_state))
    robot.io.cord_state = cord_state
    robot.io.button1_state = button1_state
    robot.io.button2_state = button2_state
