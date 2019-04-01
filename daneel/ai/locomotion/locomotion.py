import time
from enum import Enum

from locomotion.position_control import PositionControl
from locomotion.utils import *
from locomotion.params import *


class LocomotionState(Enum):
    POSITION_CONTROL = 0
    DIRECT_SPEED_CONTROL = 1
    STOPPED = 2
    REPOSITIONING = 3


class Locomotion:
    def __init__(self, robot):
        self.robot = robot
        self.current_pose = PointOrient(0, 0, 0)
        self.previous_mode = None
        self.mode = LocomotionState.POSITION_CONTROL

        # Position Control
        # self.trajectory[0].goal_point must be equal to self.current_point_objective
        self.position_control = PositionControl(self.robot)

        # Direct speed control
        self.direct_speed_goal = Speed(0, 0, 0)  # for DIRECT_SPEED_CONTROL_MODE

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

    def handle_new_speed_report(self, vx, vy, vtheta):
        self.current_speed = Speed(vx, vy, vtheta)

    def go_to_orient(self, x, y, theta):
        self.mode = LocomotionState.POSITION_CONTROL
        self.trajectory.clear()
        self.trajectory.append(TrajPoint(PointOrient(x, y, center_radians(theta)), 0.))
        self.current_point_objective = self.trajectory[0].goal_point
        self.position_control_speed_goal = self.trajectory[0].goal_speed

    def go_to_orient_point(self, point):
        self.go_to_orient(point.x, point.y, point.theta)

    def handle_obstacle(self, speed, detection_angle, stop_distance):
        if math.hypot(speed.vx, speed.vy) < 0.01:
            return
        if self.robot.io.is_obstacle_in_cone(self.theta, detection_angle, stop_distance):
            if self.mode != LocomotionState.STOPPED:
                self.stop()
        else:
            if self.mode == LocomotionState.STOPPED:
                self.restart()

    def is_at_point_orient(self, point=None):
        if point is None:
            point = self.current_point_objective
        if self.mode != LocomotionState.POSITION_CONTROL and self.mode != LocomotionState.STOPPED:
            return True
        if point is None:
            return True
        return self.distance_to(point.x, point.y) <= ADMITTED_POSITION_ERROR \
            and abs(center_radians(self.theta - point.theta)) <= ADMITTED_ANGLE_ERROR

    def is_trajectory_next_point_needed(self):
        if self.is_at_point_orient():
            return True
        else:
            if self.distance_to(self.current_point_objective.x, self.current_point_objective.y) <= 3 * ADMITTED_POSITION_ERROR and \
                    self.trajectory[0].goal_speed > 0.1:
                rp_x = self.current_point_objective.x - self.x
                rp_y = self.current_point_objective.y - self.y
                speed_dot_rp = self.current_speed.vy * rp_x + self.current_speed.vy * rp_y
                return speed_dot_rp <= 0  # If speed is in not in the same direction as the point, proceed to next point

    def is_trajectory_finished(self):
        if len(self.trajectory) == 0:
            return self.is_at_point_orient()
        return False

    def locomotion_loop(self, obstacle_detection=False):
        control_time = time.time()
        if self._last_position_control_time is None:
            delta_time = 0
        else:
            delta_time = control_time - self._last_position_control_time
        self._last_position_control_time = control_time

        if self.mode == LocomotionState.STOPPED:
            speed = Speed(0, 0, 0)

        elif self.mode == LocomotionState.POSITION_CONTROL:
            speed = self.position_control.compute_speed(delta_time)
        elif self.mode == LocomotionState.DIRECT_SPEED_CONTROL:
            if self.direct_speed_goal is not None:
                speed = self.direct_speed_goal
            else:
                speed = Speed(0, 0, 0)
        elif self.mode == LocomotionState.REPOSITIONING:
            if self.repositioning_speed_goal is not None and not self.is_repositioning_ended:
                speed = self.repositioning_speed_goal
                self.reposition_loop()
            else:
                speed = Speed(0, 0, 0)
        else:
            # This should not happen
            speed = Speed(0, 0, 0)
        # print("Speed wanted : " + str(speed))
        # self.current_speed = self.comply_speed_constraints(speed, delta_time)
        # print("Speed after saturation : " + str(self.current_speed))

        if obstacle_detection:
            if self.mode == LocomotionState.STOPPED:
                if self.previous_mode == LocomotionState.POSITION_CONTROL:
                    wanted_speed = self.position_control.compute_speed(delta_time)
                elif self.previous_mode == LocomotionState.DIRECT_SPEED_CONTROL:
                    wanted_speed = self.direct_speed_goal
                elif self.previous_mode == LocomotionState.REPOSITIONING:
                    wanted_speed = self.repositioning_speed_goal
                else:
                    wanted_speed = Speed(0, 0, 0)
            else:
                wanted_speed = speed
            vx_r = wanted_speed.vx * math.cos(self.theta) + wanted_speed.vy * math.sin(self.theta)
            vy_r = wanted_speed.vx * -math.sin(self.theta) + wanted_speed.vy * math.cos(self.theta)
            self.handle_obstacle(Speed(vx_r, vy_r, 0), 35, 350)
        #print("State : {}\tSending speed : {}".format(self.position_control.state, speed), end='\r', flush=True)
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

    def position_control_loop(self, delta_time):
        if len(self.trajectory) > 0:
            if self.is_trajectory_next_point_needed():
                # We reached a point in the trajectory, remove it.
                self.trajectory.pop(0)
                if len(self.trajectory) > 0:
                    # Go to next point in the trajectory
                    self.current_point_objective = self.trajectory[0].goal_point
                    self.position_control_speed_goal = self.trajectory[0].goal_speed

        if self.current_point_objective is not None:
            self.robot.ivy.highlight_point(0, self.current_point_objective.x, self.current_point_objective.y)
            distance_to_objective = self.current_point_objective.lin_distance_to(self.x, self.y)
            # if distance_to_objective <= ADMITTED_POSITION_ERROR:
            #     self.current_point_objective = None
            #     return

            # Acceleration part
            alpha = math.atan2(self.current_point_objective.y - self.y, self.current_point_objective.x - self.x)
            target_speed = LINEAR_SPEED_MAX * (1 - abs(alpha) / (math.pi / 2))
            current_linear_speed = math.hypot(self.current_speed.vx, self.current_speed.vy)
            new_speed = min((target_speed, current_linear_speed + delta_time * ACCELERATION_MAX))

            # Check if we need to decelerate
            if new_speed > self.position_control_speed_goal:
                t_reach_speed = (current_linear_speed - self.position_control_speed_goal) / ACCELERATION_MAX
                reach_speed_length = 2 * (
                    current_linear_speed * t_reach_speed - 1 / 2 * ACCELERATION_MAX * t_reach_speed ** 2)  # Why 2 times ? Don't know, without the factor, it is largely underestimated... Maybe because of the reaction time of the motors ?
                # current_speed_alpha = math.atan2(self.current_speed[1], self.current_speed[0])
                planned_stop_point = Point(self.x + reach_speed_length * math.cos(self.theta),
                                                self.y + reach_speed_length * math.sin(self.theta))
                self.robot.ivy.highlight_point(1, planned_stop_point.x, planned_stop_point.y)
                planned_stop_error = planned_stop_point.lin_distance_to_point(self.current_point_objective)
                if planned_stop_error <= ADMITTED_POSITION_ERROR or planned_stop_point.lin_distance_to(self.x,
                                                                                                       self.y) > distance_to_objective:
                    # Deceleration time
                    new_speed = max((0, current_linear_speed - ACCELERATION_MAX * delta_time))

            # Pure pursuit
            # Find the path point closest to the robot
            d = 99999
            t_min = 1
            ith_traj_point = 0
            p_min = None
            for i in range(len(self.trajectory) - 1):
                ab = self.trajectory[i + 1].goal_point - self.trajectory[i].goal_point
                ar = Point(self.x, self.y) - self.trajectory[i].goal_point
                # print(ab)
                t = (ar[0]*ab[0]+ar[1]*ab[1]) / (ab[0]**2 + ab[1]**2)
                p = self.trajectory[i].goal_point + Point(t * ab[0], t * ab[1])
                pr = Point(self.x, self.y) - Point(p[0], p[1])
                dist = math.hypot(pr[0], pr[1])
                # print(p, dist)
                if dist < d:
                    d = dist
                    t_min = t
                    ith_traj_point = i
                    p_min = p

            # self.goal_point = p_min

            # Find the goal point
            lookhead_left = LOOKAHEAD_DISTANCE
            browse_traj_i = 0
            self.trajectory = self.trajectory[ith_traj_point:]
            self.current_point_objective = self.trajectory[0].goal_point
            self.position_control_speed_goal = self.trajectory[0].goal_speed

            t_robot = t_min
            # print(lookahead_t, t_min, goal_t)
            path_len = math.hypot(self.trajectory[1].goal_point[0] - p_min[0],
                                  self.trajectory[1].goal_point[1] - p_min[1])
            while lookhead_left > path_len:
                # Go to the next segment and recompute it while lookhead_left > 1. If last traj element is reach, extrapolate or clamp to 1 ?
                t_robot = 0
                browse_traj_i += 1
                lookhead_left -= path_len
                path_len = math.hypot(
                    self.trajectory[browse_traj_i + 1].goal_point[0] - self.trajectory[browse_traj_i].goal_point[0],
                    self.trajectory[browse_traj_i + 1].goal_point[1] - self.trajectory[browse_traj_i].goal_point[1])

            ab = self.trajectory[browse_traj_i + 1].goal_point - self.trajectory[browse_traj_i].goal_point
            goal_t = t_robot + lookhead_left / math.hypot(ab[0], ab[1])
            goal_point = self.trajectory[browse_traj_i].goal_point + Point(goal_t * ab[0], goal_t * ab[1])
            # print(lookhead_left, ab, goal_t)
            # self.goal_point = goal_point

            # Goal point in vehicle coord
            goal_point_r = [
                -(goal_point[0] - self.x) * math.sin(self.theta) + (goal_point[1] - self.y) * math.cos(
                    self.theta),
                (goal_point[0] - self.x) * math.cos(self.theta) + (goal_point[1] - self.y) * math.sin(
                    self.theta)]

            # Compute the curvature gamma
            gamma = 2 * goal_point_r[0] / (10 ** 2)
            vtheta = new_speed * gamma

            speed_command = Speed(new_speed, 0, vtheta)
        else:
            speed_command = Speed(0, 0, 0)
        return speed_command

    def comply_speed_constraints(self, speed_cmd, dt, alpha_step=0.05):
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

