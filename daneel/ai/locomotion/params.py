ACCELERATION_MAX = 300  # mm/s²
LINEAR_SPEED_MAX = 350  # mm/s
ADMITTED_POSITION_ERROR = 10  # mm

ROTATION_ACCELERATION_MAX = 3.0 # rad/s²
ROTATION_SPEED_MAX = 1.5  # rad/s
ADMITTED_ANGLE_ERROR = 0.05  # rad

### Position control
LOOKAHEAD_DISTANCE = 150.

### Obstacle stopping
FAR_ELLIPSE_MAJOR_AXIS = 550
FAR_ELLIPSE_MINOR_AXIS = 490
CLOSE_ELLIPSE_MAJOR_AXIS = 490
CLOSE_ELLIPSE_MINOR_AXIS = 490
ELLIPSE_SCALE_FACTOR = FAR_ELLIPSE_MAJOR_AXIS - CLOSE_ELLIPSE_MAJOR_AXIS