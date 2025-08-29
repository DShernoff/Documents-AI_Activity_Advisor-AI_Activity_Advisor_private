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
    def __init__(self, name, category, urgency=0, importance=0, enjoyment=0, total_hours=1, deadline=None):
        self.name = name
        self.category = category
        self.urgency = urgency
        self.importance = importance
        self.enjoyment = enjoyment
        self.total_hours = total_hours
        self.deadline = deadline
        self.priority_score = 0
        self.status = 'active'

class Routine:
    def __init__(self, name, days_of_week, start_time=None, end_time=None, total_hours=0):
        self.name = name
        self.days_of_week = days_of_week
        self.start_time = start_time
        self.end_time = end_time
        self.is_flexible = (start_time is None)

# --- 2. The "Brain" - Scheduler Class v6.0 ---

class Scheduler:
    def __init__(self, start_date, start_time, num_days, scheduled_events, tasks, routines, energy_levels, settings):
        self.start_datetime = datetime.combine(start_date, start_time)
        self.num_days = num_days
        self.scheduled_events = scheduled_events
        self.all_tasks = tasks
        self.active_tasks = [t for t in tasks if t.status == 'active']
        self.routines = routines
        self.energy_levels = energy_levels
        self.settings = settings # NEW: App settings
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
    
    def _get_slot_context(self, day, slot_time):
        """NEW: Determines if a time slot is for 'Work' or 'Personal' tasks."""
        if not self.settings.get("work_life_separation"):
            return 'any' # If separation is off, any task can go anywhere

        personal_def = self.settings.get("personal_time_definition")
        
        if personal_def == "Weekends & Evenings":
            if day.weekday() >= 5: # Saturday or Sunday
                return 'Personal'
            if slot_time >= time(18, 0): # Evenings after 6 PM
                return 'Personal'
            return 'Work' # Otherwise, it's work time
        
        # Future logic for "Weekends Only" or "Custom" would go here
        return 'Work' # Default fallback

    def generate_schedule(self):
        # --- Initialization ---
        for i in range(self.num_days):
            current_date = self.start_datetime.date() + timedelta(days=i)
            self.schedule[current_date] = self._create_time_slots(current_date)

        # --- Pass 1: Place all STATIC, non-negotiable items (Events and Static Routines) ---
        # ... (This logic remains the same as v5.1) ...
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

        # --- Pass 2: Place FLEXIBLE Routines (like Exercise) ---
        # ... (This logic remains the same as v5.1) ...
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

        # --- Pass 3: Schedule flexible TASKS by priority and CONTEXT ---
        # NEW: Split tasks into Work and Personal lists
        category_types = self.settings.get("category_types", {})
        work_tasks = [t for t in self.active_tasks if category_types.get(t.category) == 'Work']
        personal_tasks = [t for t in self.active_tasks if category_types.get(t.category) == 'Personal']

        work_chunks = sorted(self._create_task_chunks(work_tasks), key=lambda x: x.priority_score, reverse=True)
        personal_chunks = sorted(self._create_task_chunks(personal_tasks), key=lambda x: x.priority_score, reverse=True)

        for i in range(self.num_days):
            current_date = self.start_datetime.date() + timedelta(days=i)
            if current_date in all_day_events: continue
            
            for slot_time in sorted(self.schedule[current_date].keys()):
                if current_date == self.start_datetime.date() and slot_time < self.start_datetime.time():
                    self.schedule[current_date][slot_time] = "PAST"
                    continue

                if self.schedule[current_date][slot_time] is None:
                    context = self._get_slot_context(current_date, slot_time)
                    chunk_to_schedule = None

                    if context == 'Work' and work_chunks:
                        chunk_to_schedule = work_chunks.pop(0)
                    elif context == 'Personal' and personal_chunks:
                        chunk_to_schedule = personal_chunks.pop(0)
                    
                    if chunk_to_schedule:
                        self.schedule[current_date][slot_time] = f"TASK: {chunk_to_schedule.name}"
                        self.scheduled_task_names.add(chunk_to_schedule.name)

        # --- Pass 4: Fill remaining empty slots with specific tasks ---
        # ... (Logic is now context-aware) ...
        for day, slots in self.schedule.items():
             if day in all_day_events: continue
             for slot_time in slots:
                if slots[slot_time] is None:
                    context = self._get_slot_context(day, slot_time)
                    chunk_to_fill = None
                    if context == 'Work' and work_chunks:
                        chunk_to_fill = work_chunks.pop(0)
                    elif context == 'Personal' and personal_chunks:
                        chunk_to_fill = personal_chunks.pop(0)
                    
                    if chunk_to_fill:
                        slots[slot_time] = f"TASK: {chunk_to_fill.name}"
                    else:
                        slots[slot_time] = "Open / Free Time"
        
        return self.schedule


# --- 3. The "Main" Block: Where we define data and run the simulation ---
if __name__ == "__main__":
    start_date = date(2025, 8, 29)
    start_time = time(8, 0)
    
    # --- NEW: App-level settings defined here for the simulation ---
    app_settings = {
        "work_life_separation": True,
        "personal_time_definition": "Weekends & Evenings",
        "category_types": {
            "Assignment": "Work",
            "Long-term project": "Work",
            "Value": "Personal",
            "Hobby": "Personal"
        }
    }

    user_events = [
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
        Task("Contracts and MOUs for Angelica", "Assignment", total_hours=2, deadline=date(2025, 9, 5)),
        # Long-term Projects
        Task("Continue work on Activity Advisor program", "Long-term project", total_hours=10),
        # ... (rest of the tasks)
        # Values
        # Hobbies
        Task("Pillows", "Hobby"),
        Task("Wine shopping?", "Hobby"),
    ]
    
    # --- Prioritization Engine (remains the same) ---
    DEFAULTS = {
        "Assignment": {"I": 7, "E": 4}, "Long-term project": {"U": 4, "I": 7, "E": 5},
        "Value": {"U": 4, "I": 8, "E": 7}, "Hobby": {"U": 3, "I": 4, "E": 9}
    }
    WEIGHTS = {"U": 2, "I": 1, "E": 1}

    for task in all_user_tasks:
        if task.status == 'active':
            defaults = DEFAULTS.get(task.category, {})
            task.importance = defaults.get("I", 0); task.enjoyment = defaults.get("E", 0)
            if task.category == "Assignment":
                work_days_left = (task.deadline - start_date).days if task.deadline else 1
                if work_days_left < 1: work_days_left = 1
                required_pace = task.total_hours / work_days_left
                task.urgency = required_pace + 5
            else:
                task.urgency = defaults.get("U", 0)
            numerator = (task.urgency * WEIGHTS["U"]) + (task.importance * WEIGHTS["I"]) + (task.enjoyment * WEIGHTS["E"])
            denominator = sum(WEIGHTS.values())
            task.priority_score = numerator / denominator
            
    # Pass the new 'app_settings' to the Scheduler
    my_scheduler = Scheduler(start_date, start_time, 7, user_events, all_user_tasks, user_routines, {}, app_settings)
    final_schedule = my_scheduler.generate_schedule()

    # (Display Logic)
    print("\n--- Your AI-Generated Daily Schedule (v6.0 with Work/Life Separation) ---")
    # ... (Display logic remains the same)
