import time
from enum import Enum

from locomotion.position_control import PositionControl
from locomotion.relative_control import RelativeControl
from locomotion.utils import *
from locomotion.params import *
from locomotion.pathfinding import ThetaStar


class LocomotionState(Enum):
    POSITION_CONTROL = 0
    DIRECT_SPEED_CONTROL = 1
    STOPPED = 2
    REPOSITIONING = 3
    RELATIVE_CONTROL = 4


class Locomotion:
    def __init__(self, robot):
        self.robot = robot
        self.current_pose = PointOrient(0, 0, 0)
        self.previous_mode = None
        self.is_drifting = [False, False]
        self.mode = LocomotionState.POSITION_CONTROL

        # Position Control
        # self.trajectory[0].goal_point must be equal to self.current_point_objective
        self.position_control = PositionControl(self.robot)

        # Pathfinding
        self.pathfinder = ThetaStar(self.robot)


        # Direct speed control
        self.direct_speed_goal = Speed(0, 0, 0)  # for DIRECT_SPEED_CONTROL_MODE

        # Relative control
        self.relative_control = RelativeControl(self.robot)

        # Repositionning
        self.repositioning_end_position = (None, None, None)
        self.is_repositioning = False

        self.current_speed = Speed(0, 0, 0)  # type: Speed
        self.robot.communication.register_callback(self.robot.communication.eTypeUp.ODOM_REPORT,
                                                   self.handle_new_odometry_report)
        self.robot.communication.register_callback(self.robot.communication.eTypeUp.SPEED_REPORT,
                                                   self.handle_new_speed_report)
        self._last_position_control_time = None

    def handle_new_odometry_report(self, x, y, theta):
        self.current_pose.x = x
        self.current_pose.y = y
        self.current_pose.theta = center_radians(theta)

    def handle_new_speed_report(self, vx, vy, vtheta, drifting_left, drifting_right):
        self.is_drifting = [drifting_left, drifting_right]
        #self.current_speed = Speed(vx, vy, vtheta)

    def go_to_orient(self, x, y, theta):
        self.follow_trajectory([(x, y, theta)])

    def go_to_orient_point(self, point):
        self.go_to_orient(point.x, point.y, point.theta)

    def start_repositioning(self, x_end=None, y_end=None, theta_end=None):
        print("[Locomotion] Repositioning started")
        self.mode = LocomotionState.REPOSITIONING
        self.is_repositioning = True
        self.repositioning_end_position = (x_end, y_end, theta_end)

    @property
    def trajectory_finished(self):
        return self.position_control.state == self.position_control.state.IDLE

    @property
    def relative_command_finished(self):
        return self.relative_control.state == self.relative_control.state.IDLE

    @property
    def repositionning_finished(self):
        return not self.is_repositioning

    @property
    def is_one_drifting(self):
        return self.is_drifting[0] or self.is_drifting[1]

    def navigate_to(self, x, y, theta):
        # TODO: Probably detach a thread...
        traj = self.pathfinder.find_path((self.x, self.y), (float(x), float(y)))
        if traj is None or len(traj) < 2:
            print("[Locomotion] No trajectory found from {} to {} using pathfinder".format((self.x, self.y), (x, y)))
        traj_orient = []
        for pt in traj[:-1]:
            traj_orient.append((int(pt[0]), int(pt[1]), 0))
        traj_orient.append((int(traj[-1][0]), int(traj[-1][1]), theta))
        print(traj_orient)
        self.follow_trajectory(traj_orient)

    def speed_constraints_from_obstacles(self):
        min_vx = -LINEAR_SPEED_MAX
        max_vx = LINEAR_SPEED_MAX
        min_d_far_ellipse, max_d_far_ellipse = self.robot.io.distance_to_cone_ellipse(0, 1.4, FAR_ELLIPSE_MAJOR_AXIS,
                                                                                      FAR_ELLIPSE_MINOR_AXIS)
        if min_d_far_ellipse < 0:
            # If we are in the far ellipse check for the close
            min_d_close_e, max_d_close_e = self.robot.io.distance_to_cone_ellipse(0, 1.4, CLOSE_ELLIPSE_MAJOR_AXIS,
                                                                                  CLOSE_ELLIPSE_MINOR_AXIS)
            if min_d_close_e < 0:
                max_vx = 0
            else:
                max_vx = LINEAR_SPEED_MAX * min_d_close_e / ELLIPSE_SCALE_FACTOR

        min_d_far_ellipse_b, max_d_far_ellipse_b = self.robot.io.distance_to_cone_ellipse(-math.pi, 1.4,
                                                                                          FAR_ELLIPSE_MAJOR_AXIS,
                                                                                          FAR_ELLIPSE_MINOR_AXIS)
        if min_d_far_ellipse_b < 0:
            min_d_close_e_b, max_d_close_e_b = self.robot.io.distance_to_cone_ellipse(-math.pi, 1.4,
                                                                                      CLOSE_ELLIPSE_MAJOR_AXIS,
                                                                                      CLOSE_ELLIPSE_MINOR_AXIS)
            if min_d_close_e_b < 0:
                min_vx = 0
            else:
                min_vx = -LINEAR_SPEED_MAX * min_d_close_e_b / ELLIPSE_SCALE_FACTOR
        return SpeedConstraint(min_vx, max_vx, 0, 0, -ROTATION_SPEED_MAX, ROTATION_SPEED_MAX)


    def is_at_point_orient(self, point):
        if self.mode != LocomotionState.POSITION_CONTROL and self.mode != LocomotionState.STOPPED:
            return True
        if point is None:
            return True
        return self.distance_to(point.x, point.y) <= ADMITTED_POSITION_ERROR \
            and abs(center_radians(self.theta - point.theta)) <= ADMITTED_ANGLE_ERROR

    def locomotion_loop(self, obstacle_detection=False):
        control_time = time.time()
        if self._last_position_control_time is None:
            delta_time = 0
        else:
            delta_time = control_time - self._last_position_control_time
        self._last_position_control_time = control_time

        speed_constraints = SpeedConstraint(-LINEAR_SPEED_MAX, LINEAR_SPEED_MAX, 0, 0,
                                            -ROTATION_SPEED_MAX, ROTATION_SPEED_MAX)

        if obstacle_detection:
            speed_constraints = self.speed_constraints_from_obstacles()

        if self.mode == LocomotionState.STOPPED:
            speed = Speed(0, 0, 0)

        elif self.mode == LocomotionState.POSITION_CONTROL:
            speed = self.position_control.compute_speed(delta_time, speed_constraints)
        elif self.mode == LocomotionState.DIRECT_SPEED_CONTROL:
            if self.direct_speed_goal is not None:
                speed = self.direct_speed_goal
            else:
                speed = Speed(0, 0, 0)
        elif self.mode == LocomotionState.REPOSITIONING:
            if not self.is_repositioning:
                speed = Speed(0, 0, 0)
            elif self.is_drifting[0] and self.is_drifting[1]:
                speed = Speed(0, 0, 0)
                new_x = self.repositioning_end_position[0] if self.repositioning_end_position[0] is not None else self.current_pose.x
                new_y = self.repositioning_end_position[1] if self.repositioning_end_position[1] is not None else self.current_pose.y
                new_theta = self.repositioning_end_position[2] if self.repositioning_end_position[2] is not None else self.current_pose.theta
                self.reposition_robot(new_x, new_y, new_theta)
                self.is_repositioning = False
            elif self.is_drifting[0]:
                speed = Speed(50, 0, 0.3)
            elif self.is_drifting[1]:
                speed = Speed(50, 0, -0.3)
            else:
                speed = Speed(50, 0, 0)
        elif self.mode == LocomotionState.RELATIVE_CONTROL:
            speed = self.relative_control.compute_speed(delta_time, speed_constraints)
        else:
            # This should not happen
            speed = Speed(0, 0, 0)
        # print("Speed wanted : " + str(speed))
        # self.current_speed = self.comply_speed_constraints(speed, delta_time)
        # print("Speed after saturation : " + str(self.current_speed))
        #speed = self.comply_speed_constraints(speed, delta_time)
            
        # print("State : {}\tSending speed : {}".format(self.position_control.state, speed), end='\r', flush=True)
        self.current_speed = speed
        self.robot.communication.send_speed_command(*speed)

    def stop(self):
        self.previous_mode = self.mode
        self.mode = LocomotionState.STOPPED

    def restart(self):
        self.mode = self.previous_mode

    def set_direct_speed(self, x_speed, y_speed, theta_speed):
        if self.mode == LocomotionState.STOPPED:
            self.previous_mode = LocomotionState.DIRECT_SPEED_CONTROL
        else:
            self.mode = LocomotionState.DIRECT_SPEED_CONTROL
        self.direct_speed_goal = Speed(x_speed, y_speed, theta_speed)

    def go_straight(self, distance):
        self.mode = LocomotionState.RELATIVE_CONTROL
        if -ADMITTED_POSITION_ERROR < distance < 0:
            distance = -ADMITTED_POSITION_ERROR - 1
        elif 0 < distance < ADMITTED_POSITION_ERROR:
            distance = ADMITTED_POSITION_ERROR + 1
        self.relative_control.new_straight_goal(distance)
        print("[Locomotion] New straight relative goal received")

    def turn(self, relative_angle):
        self.mode = LocomotionState.RELATIVE_CONTROL
        if 0 > relative_angle > -ADMITTED_ANGLE_ERROR:
            relative_angle = -ADMITTED_ANGLE_ERROR - 0.001
        elif 0 < relative_angle < ADMITTED_ANGLE_ERROR:
            relative_angle = ADMITTED_ANGLE_ERROR + 0.001

        self.relative_control.new_rotate_goal(relative_angle)
        print("[Locomotion] New rotational relative goal received")

    def comply_speed_constraints(self, speed_cmd, dt):
        if dt == 0:
            return Speed(0, 0, 0)

        # Verify if maximum acceleration is respected
        vx, vy, vtheta = speed_cmd
        vx = min(vx, LINEAR_SPEED_MAX, self.current_speed.vx + ACCELERATION_MAX * dt)
        vx = max(vx, -LINEAR_SPEED_MAX, self.current_speed.vx - ACCELERATION_MAX * dt)
        vtheta = min(vtheta, ROTATION_SPEED_MAX, self.current_speed.vtheta + ROTATION_ACCELERATION_MAX * dt)
        vtheta = max(vtheta, -ROTATION_SPEED_MAX, self.current_speed.vtheta - ROTATION_ACCELERATION_MAX * dt)
        vy = 0

        return Speed(vx, vy, vtheta)

    def distance_to(self, x, y):
        return math.sqrt((self.x - x) ** 2 + (self.y - y) ** 2)

    def reposition_robot(self, x, y, theta):
        theta = center_radians(theta)
        if self.robot.communication.send_repositioning(x, y, theta) == 0:
            self.x = x
            self.y = y
            self.theta = theta

    def follow_trajectory(self, points_list):
        """

        :param points_list:
        :type points_list: list[tuple[int, int]]|list[Locomotion.PointOrient]
        :return:
        """
        self.mode = LocomotionState.POSITION_CONTROL
        self.position_control.new_trajectory(points_list)
        print("[Locomotion] New trajectory received.")
        print("[Locomotion] Going into position control mode.")

    @property
    def x(self):
        return self.current_pose.x

    @x.setter
    def x(self, value):
        self.current_pose.x = value

    @property
    def y(self):
        return self.current_pose.y

    @y.setter
    def y(self, value):
        self.current_pose.y = value

    @property
    def theta(self):
        return self.current_pose.theta

    @theta.setter
    def theta(self, value):
        self.current_pose.theta = value

