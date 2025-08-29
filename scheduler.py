# Import necessary libraries
from datetime import time, timedelta, date, datetime
import math
import copy

# --- 1. Data Structures ---

class ScheduledEvent:
    def __init__(self, name, event_date, start_time, end_time):
        self.name = name
        self.date = event_date
        self.start_time = start_time
        self.end_time = end_time

class Task:
    def __init__(self, name, category, urgency=0, importance=0, enjoyment=0, total_hours=1):
        self.name = name
        self.category = category
        self.urgency = urgency
        self.importance = importance
        self.enjoyment = enjoyment
        self.total_hours = total_hours
        self.priority_score = 0 # Will be calculated by the engine
        self.status = 'active'

class Routine:
    def __init__(self, name, days_of_week, start_time=None, end_time=None, total_hours=0):
        self.name = name
        self.days_of_week = days_of_week
        self.start_time = start_time
        self.end_time = end_time
        self.is_flexible = (start_time is None)

# --- 2. The "Brain" - Scheduler Class v5.1 ---

class Scheduler:
    def __init__(self, start_date, start_time, num_days, scheduled_events, tasks, routines, energy_levels):
        self.start_datetime = datetime.combine(start_date, start_time)
        self.num_days = num_days
        self.scheduled_events = scheduled_events
        self.all_tasks = tasks
        self.active_tasks = [t for t in tasks if t.status == 'active']
        self.routines = routines
        self.energy_levels = energy_levels
        self.schedule = {}
        self.scheduled_task_names = set()

    def _create_time_slots(self, day):
        slots = {}
        start_of_day = datetime.combine(day, time(8, 0))
        for i in range(26):
            slot_time = (start_of_day + timedelta(minutes=30 * i)).time()
            slots[slot_time] = None
        return slots

    def _create_task_chunks(self, tasks):
        chunked_list = []
        for task in tasks:
            num_chunks = math.ceil(task.total_hours * 2)
            for _ in range(num_chunks):
                chunked_list.append(copy.copy(task))
        return chunked_list
    
    def _ensure_diversity(self):
        original_task_names = {task.name for task in self.active_tasks}
        orphaned_tasks = original_task_names - self.scheduled_task_names
        if not orphaned_tasks: return

        tasks_to_place = [task for task in self.active_tasks if task.name in orphaned_tasks]
        
        for day in sorted(self.schedule.keys(), reverse=True):
             if "All Day" in self.schedule[day]: continue
             for slot_time in sorted(self.schedule[day].keys(), reverse=True):
                 if not tasks_to_place: return
                 current_activity = self.schedule[day][slot_time]
                 if "ADVISORY:" in str(current_activity):
                     task_to_place = tasks_to_place.pop(0)
                     self.schedule[day][slot_time] = f"TASK: {task_to_place.name}"

    def generate_schedule(self):
        # --- Initialization ---
        for i in range(self.num_days):
            current_date = self.start_datetime.date() + timedelta(days=i)
            self.schedule[current_date] = self._create_time_slots(current_date)

        # --- Pass 1: Place all STATIC, non-negotiable items ---
        all_day_events = []
        for event in self.scheduled_events:
            if event.start_time is None:
                all_day_events.append(event.date)
                self.schedule[event.date] = {"All Day": f"FIXED: {event.name}"}
                continue
            if event.date in self.schedule:
                for slot_time in self.schedule[event.date]:
                    if event.start_time <= slot_time < event.end_time:
                        self.schedule[event.date][slot_time] = f"FIXED: {event.name}"

        static_routines = [r for r in self.routines if not r.is_flexible]
        for day, slots in self.schedule.items():
            if day in all_day_events: continue
            for routine in static_routines:
                if day.weekday() in routine.days_of_week:
                    for slot_time in slots:
                        if routine.start_time <= slot_time < routine.end_time:
                            slots[slot_time] = f"ROUTINE: {routine.name}"

        for day, energy in self.energy_levels.items():
            if day in self.schedule and energy == "Low" and day not in all_day_events:
                for slot_time in self.schedule[day]:
                    if time(16, 0) <= slot_time < time(18, 0):
                        self.schedule[day][slot_time] = "ADVISORY: Nap"

        # --- Pass 2: Place FLEXIBLE Routines ---
        flexible_routines = [r for r in self.routines if r.is_flexible]
        for day, slots in self.schedule.items():
            if day in all_day_events or not flexible_routines: continue
            routine = flexible_routines[0]
            chunks_needed = math.ceil(routine.total_hours * 2)
            for slot_start_time in sorted(slots.keys()):
                is_block_free = True; block_times = []
                for i in range(chunks_needed):
                    current_slot_time = (datetime.combine(day, slot_start_time) + timedelta(minutes=30 * i)).time()
                    if slots.get(current_slot_time) is not None: is_block_free = False; break
                    block_times.append(current_slot_time)
                if is_block_free:
                    for t in block_times: slots[t] = f"ROUTINE: {routine.name}"
                    break
                    
        # --- Pass 3: Schedule flexible TASKS by priority ---
        task_chunks = self._create_task_chunks(self.active_tasks)
        sorted_chunks = sorted(task_chunks, key=lambda x: x.priority_score, reverse=True)

        for i in range(self.num_days):
            current_date = self.start_datetime.date() + timedelta(days=i)
            if current_date in all_day_events: continue
            
            for slot_time in sorted(self.schedule[current_date].keys()):
                if current_date == self.start_datetime.date() and slot_time < self.start_datetime.time():
                    self.schedule[current_date][slot_time] = "PAST"
                    continue

                if not sorted_chunks: break
                if self.schedule[current_date][slot_time] is None:
                    chunk_to_schedule = sorted_chunks.pop(0)
                    self.schedule[current_date][slot_time] = f"TASK: {chunk_to_schedule.name}"
                    self.scheduled_task_names.add(chunk_to_schedule.name)
            if not sorted_chunks: break

        # --- Pass 4: Fill any remaining empty slots ---
        if sorted_chunks: # If there are still tasks left, fill with them
            for day, slots in self.schedule.items():
                 if day in all_day_events: continue
                 for slot_time in slots:
                    if slots[slot_time] is None:
                        if not sorted_chunks: break
                        chunk = sorted_chunks.pop(0)
                        slots[slot_time] = f"TASK: {chunk.name}"

        self._ensure_diversity()
        return self.schedule

# --- 3. The "Main" Block: Where we define data and run the simulation ---
if __name__ == "__main__":
    start_date = date(2025, 8, 29)
    start_time = time(8, 0)
    
    user_events = [
        # Events for the new week
        ScheduledEvent("CMSCE / marketing meeting with Sara", date(2025, 9, 3), time(10, 0), time(11, 0)),
        ScheduledEvent("CMSCE team meeting", date(2025, 9, 4), time(13, 0), time(14, 30)),
    ]

    user_routines = [
        Routine("Dinner", [0,1,2,3,4,5,6], start_time=time(18,0), end_time=time(19,30)),
        Routine("Answering Email", [0,1,2,3,4], start_time=time(10,0), end_time=time(10,30)),
        Routine("Morning Rituals", [0,1,2,3,4], start_time=time(8,0), end_time=time(9,0)),
        Routine("Morning Rituals", [5,6], start_time=time(8,30), end_time=time(10,0)),
        Routine("Exercise", [0,1,2,3,4,5,6], total_hours=1.5),
    ]

    all_user_tasks = [
        # Assignments
        Task("Give requested Feedback to Rough Draft math", "Assignment", total_hours=2, deadline=date(2025, 9, 15)),
        Task("Organize computer files", "Assignment", total_hours=6, deadline=date(2025, 9, 1)),
        Task("Contracts and MOUs for Angelica", "Assignment", total_hours=2, deadline=date(2025, 9, 5)),
        # Long-term Projects
        Task("Continue work on Activity Advisor program", "Long-term project", total_hours=10),
        Task("Boat stuff", "Long-term project", total_hours=1),
        Task("Solve printer offline", "Long-term project"),
        Task("Get RU-PSU football tickets", "Long-term project"),
        Task("Send keynote video to mom", "Long-term project", total_hours=0.5),
        Task("Boater endorsement on driver's license", "Long-term project"),
        Task("Get UW safety alerts", "Long-term project"),
        Task("Kurt - September plans", "Long-term project"),
        Task("Reply to Beth and Ashley re Maker Cert", "Long-term project"),
        Task("Pursue School 81/consult Angelica", "Long-term project"),
        Task("Get colleague/testers of scheduler", "Long-term project"),
        Task("Get back to Cameron", "Long-term project"),
        Task("Follow up with Erik on Summer Science", "Long-term project"),
        Task("Review AI overview from call", "Long-term project"),
        Task("Black face watch battery", "Long-term project"),
        Task("Prepare for Angelica performance review", "Long-term project"),
        Task("Eddie email - maker / special ed redesign UD, AI", "Long-term project"),
        Task("Send around Educator's Guide to STEAM 2ed review", "Long-term project"),
        Task("Follow up with Beth and Ashley", "Long-term project"),
        Task("email Angelica re School 81?", "Long-term project"),
        Task("care package for Spencer (shirts, bike water bottle)", "Long-term project"),
        Task("Call Spencer's PT", "Long-term project"),
        Task("Singelyn email", "Long-term project"),
        Task("send mom and dad FB post from McNicholls", "Long-term project"),
        # Hobbies
        Task("Pillows", "Hobby"),
        Task("Wine shopping?", "Hobby"),
    ]
    
    # --- Prioritization Engine ---
    
    # Define default ratings and weights
    DEFAULTS = {
        "Assignment": {"I": 7, "E": 4},
        "Long-term project": {"U": 4, "I": 7, "E": 5},
        "Value": {"U": 4, "I": 8, "E": 7},
        "Hobby": {"U": 3, "I": 4, "E": 9}
    }
    WEIGHTS = {"U": 2, "I": 1, "E": 1}

    # Calculate scores for all active tasks
    for task in all_user_tasks:
        if task.status == 'active':
            # Apply defaults
            defaults = DEFAULTS.get(task.category, {})
            task.importance = defaults.get("I", 0)
            task.enjoyment = defaults.get("E", 0)
            
            if task.category == "Assignment":
                # Intelligent Deadline Planning
                work_days_left = (task.deadline - start_date).days
                if work_days_left < 1: work_days_left = 1
                required_pace = task.total_hours / work_days_left
                task.urgency = required_pace + 5 # New Urgency Formula
            else:
                task.urgency = defaults.get("U", 0)

            # Weighted Average Calculation
            numerator = (task.urgency * WEIGHTS["U"]) + (task.importance * WEIGHTS["I"]) + (task.enjoyment * WEIGHTS["E"])
            denominator = WEIGHTS["U"] + WEIGHTS["I"] + WEIGHTS["E"]
            task.priority_score = numerator / denominator

            
    my_scheduler = Scheduler(start_date, start_time, 7, user_events, all_user_tasks, user_routines, {})
    final_schedule = my_scheduler.generate_schedule()

    # (Display Logic)
    print("\n--- Your AI-Generated Daily Schedule (v5.1) ---")
    # ... (Display logic remains the same)```
