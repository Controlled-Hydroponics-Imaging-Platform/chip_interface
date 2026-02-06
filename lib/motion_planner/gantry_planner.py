import numpy as np

class GantryPlanner:
    def __init__(self,
                 x_limit,
                 y_limit, 
                 z_limit,
                 x_home_dir,
                 y_home_dir,
                 z_home_dir,
                 x_mm_per_rev,
                 y_mm_per_rev,
                 z_mm_per_rev,
                 max_speed
                 ):
        """ this class is used to plan motion for a gantry robot, done in mm"""

        self.x_limit = x_limit
        self.y_limit = y_limit
        self.z_limit = z_limit
        self.x_home_dir = x_home_dir
        self.y_home_dir = y_home_dir
        self.z_home_dir = z_home_dir
        self.x_mm_per_rev = x_mm_per_rev
        self.y_mm_per_rev = y_mm_per_rev
        self.z_mm_per_rev = z_mm_per_rev
        self.max_speed = max_speed

        self.INVERSE_JACOBIAN = np.diag([
            -self.x_home_dir / self.x_mm_per_rev,
            -self.y_home_dir / self.y_mm_per_rev,
            -self.z_home_dir / self.z_mm_per_rev
        ])

        self.curr_pose = np.array([0.0, 0.0, 0.0])





    def home(self):
        pass
    def move_to(self):
        pass
    def stand_by(self):
        pass
    def move(self):
        pass

        