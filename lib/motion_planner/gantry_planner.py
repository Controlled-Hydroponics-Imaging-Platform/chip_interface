import numpy as np

class LinearGantryPlanner:
    def __init__(self,
                 limits, #in mm dict: [x:x_limit, y:y_limit, z:z_limit]
                 home_dirs, #dict: [x:x_home_dir, y:y_home_dir, z:z_home_dir]
                 mm_per_revs, #dict: [x:x_mm_per_rev, ....]
                 default_home_pose, # in mm dict,list, or nparray: [x_default_home, ....]
                 max_speed # mm/s
                 ):
        """ this class is used to plan motion for a gantry robot, done in mm"""

        self.limits = limits


        self.home_dirs = home_dirs #[x,y,z]
        self.mm_per_revs = mm_per_revs #[x,y,z]
        self.max_speed = float(max_speed)

        self.INVERSE_JACOBIAN = np.diag([
            -home_dirs['x']/ mm_per_revs['x'],
            -home_dirs['y'] / mm_per_revs['y'],
            -home_dirs['z'] / mm_per_revs['z']
        ]).astype(float)

        self.curr_pose = np.array([0.0, 0.0, 0.0], dtype=float)
        
        if isinstance(default_home_pose, dict):
            self.default_home_pose = np.asarray( [default_home_pose["x"], default_home_pose["y"], default_home_pose["z"]], dtype=float ).reshape(3,)
        else:
            self.default_home_pose = np.asarray(default_home_pose, dtype=float).reshape(3,)

    
    def move_to(self, target_pose, vel):
        """
        target_pose: [x,y,z] in mm
        vel: linear velocity in the task space in mm/s
        """
        
        target_pose = np.asarray(target_pose, dtype=float).reshape(3,)

        delta_x = target_pose - self.curr_pose

        delta_q = self.INVERSE_JACOBIAN @ (delta_x)

        distance = np.linalg.norm(delta_x)

        if distance <1e-9:
            # print(f'already at {target_pose}')
            return
        if vel<=0:
            raise ValueError("vel must be > 0")
        
        vel = min(float(vel), float(self.max_speed))

        t = distance/ vel #seconds

        q_dot = (delta_q/t) * 60

        out = {
            'delta_q':{'x':float(delta_q[0]),'y': float(delta_q[1]),'z':float(delta_q[2])},
            'q_dot': {'x':int(q_dot[0]), 'y':int(q_dot[1]), 'z': int(q_dot[2]) },
            't_s': float(t),
            "distance": float(distance)
        }

        self.curr_pose = target_pose.copy()

        return out

    def move(self, rel_pose, vel):
        
        rel_pose = np.asarray(rel_pose, dtype=float).reshape(3,)

        target_pose = self.curr_pose + rel_pose

        out = self.move_to(target_pose, vel)
        
        return out



    def stand_by(self):
        pass

    def home(self, calibrate = False):
        
        if not calibrate:
            out = self.move_to(self.default_home_pose, self.max_speed)
        else:
            out = self.move([-1000, -1000, -1000], self.max_speed)
            self.curr_pose = np.array([0.0, 0.0, 0.0], dtype=float)

        return out
    
    def get_current_pose(self):

        out = {'x':float(self.curr_pose[0]),'y': float(self.curr_pose[1]),'z':float(self.curr_pose[2])}
        return out