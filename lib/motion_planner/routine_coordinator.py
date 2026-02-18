import threading
from datetime import datetime, timedelta
from time import sleep

def _expand_schedule(schedule, default_step=60, sort_output=True, unique=True):
    """    
    :param schedule: list of individual time entries or time ranges formatted as such: "start_time-endtime;minute_steps" 
    :param sort_output: sort from earliest to latest time
    :param unique: remove duplicates
    """
    fmt = "%H:%M"
    times = []

    for entry in schedule:
        entry = entry.strip()

        # formated range entries
        if "-" in entry:
            try:
                if ";" in entry:
                    time_range, step = entry.split(";",1)
                    step = int(step.strip())
                else:
                    time_range = entry
                    step = default_step

                if step<=0:
                    raise ValueError("steps must be positive")

                start_s, end_s = [t.strip() for t in time_range.split("-",1)]
                start = datetime.strptime(start_s, fmt)
                end = datetime.strptime(end_s, fmt)

                # CROSSING MIDNIGHT
                if end < start:
                    end += timedelta(days=1)

                cur = start
                while cur <= end:
                    times.append(cur.strftime(fmt))
                    cur += timedelta(minutes=step)

            except  Exception as e:
                raise ValueError(f"Invalid schedule range format:'{entry}' ({e})")

        # normal time entries
        else:
            try:
                t = datetime.strptime(entry, fmt)  # validate
                times.append(t.strftime(fmt))

            except Exception as e:
                raise ValueError(f"Invalid time format: '{entry}' ({e})")

    if unique:
        times = list(dict.fromkeys(times))

    if sort_output:
        times.sort()

    return set(times), times


class RoutineHandler:
    def __init__(self,
                 action_callback,
                 poll_rate = 1, # in seconds
                 associated_device_name = "routine_device"
                 ):
        
        self.task = None
        self._running = False
        self.associated_device_name = associated_device_name 

        self.poll_rate= poll_rate
        self.action_triggered = False
        self.last_trigger = None
        self.last_check = None
        self.schedule = []
        self.trigger_times = set()
        self.action_callback = action_callback

    def set_schedule(self, schedule=["00:00-23:00;60"]):
        self.trigger_times, self.schedule= _expand_schedule(schedule)
        print(f"{self.associated_device_name} schedule set: \n{self.schedule}")


    def get_schedule(self):
        return self.schedule


    def should_trigger(self, with_catchup =False):
        """
        Docstring for should_trigger
        
        :param self: Description
        :param with_catchup: Description
        """
        now = datetime.now()

        if self.last_check is None:
            self.last_trigger= None
            self.last_check = now
            return False
        
        start = self.last_check
        end = now

        if end<=start:
            self.last_check = now
            return False

        next_hit = None

        for t in self.trigger_times:
            hour, minute = map(int, t.split(":"))

            today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            yesterday = today - timedelta(days =1)

            for trigger in (yesterday, today):
                
                if start<trigger<=end:
                    if with_catchup:
                        if next_hit is None or trigger<next_hit:
                            next_hit = trigger
                    else:
                        if next_hit is None or trigger>next_hit:
                            next_hit = trigger
                    
        if next_hit is None:
            self.last_check=now
            return False
        
        last_trigger_key=next_hit.strftime("%Y-%m-%d %H:%M")

        if last_trigger_key == self.last_trigger:
            self.last_check = now
            return False
        
        self.last_trigger = last_trigger_key
        self.last_check = next_hit if with_catchup else now
        return True


    def get_next_trigger_info(self):
        now = datetime.now()

        next_trig = None

        for t in self.trigger_times:
            hour, minute = map(int, t.split(":"))
            today= now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)

            for trig in (today,tomorrow):
                if trig >now:

                    if next_trig is None or trig<next_trig:
                        next_trig = trig
        
        if next_trig is None:
            return None, None
        
        delta = next_trig-now
        
        total_seconds = int(delta.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        duration_str = f"{days}d {hours:02}:{minutes:02}:{seconds:02}"

        return next_trig.strftime("%Y-%m-%d %H:%M"), duration_str


    def run_routine(self, with_catchup = False):
        if not self.trigger_times:
            print("Schedule not set")
            return

        while self._running:
            if self.should_trigger(with_catchup=with_catchup):
                self.action_callback()
            
            sleep(self.poll_rate)
            

    def start(self, with_catchup=False):
        self.kill()
        self._running = True
        self.task = threading.Thread(target=self.run_routine, kwargs={"with_catchup": with_catchup}, daemon=True)
        self.task.start()
        

    def kill(self):
        self._running = False
        if self.task:
            self.task.join(timeout=5)
            self.task = None
    
    def get_output(self):

        next_trig, time_unitl_next_trig = self.get_next_trigger_info()
        
        out = {
            "last_trigger": self.last_trigger,
            "last_check": self.last_check.isoformat(),
            "routine_active": self._running,
            "trigger_schedule": self.schedule,
            "next_scheduled_trigger": next_trig,
            "time_until_next_trigger": time_unitl_next_trig
        }
        
        return out


if __name__ == "__main__": 

    def action_callback():
        print("action hit")

    test_routine = RoutineHandler(action_callback)

    test_routine.set_schedule(["15:43", "15:45"])

    test_routine.start()

    while True:
        

        out = test_routine.get_output()

        print(out)
        sleep(1)