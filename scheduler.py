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
    def __init__(self, name, category, urgency=0, importance=0, enjoyment=0, total_hours=1, deadline=None, constraints=None):
        self.name = name
        self.category = category
        self.urgency = urgency
        self.importance = importance
        self.enjoyment = enjoyment
        self.total_hours = total_hours
        self.deadline = deadline
        self.priority_score = 0
        self.status = 'active'
        self.constraints = constraints or {}

class Routine:
    def __init__(self, name, days_of_week=None, day_of_month=None, start_time=None, end_time=None, total_hours=0, constraints=None):
        self.name = name
        self.days_of_week = days_of_week
        self.day_of_month = day_of_month
        self.start_time = start_time
        self.end_time = end_time
        self.total_hours = total_hours
        self.is_flexible = (start_time is None)
        self.constraints = constraints or {}

# --- 2. The "Brain" - Scheduler Class ---

class Scheduler:
    def __init__(self, start_date, start_time, num_days, user_profile):
        self.start_datetime = datetime.combine(start_date, start_time)
        self.num_days = num_days
        self.user_profile = user_profile
        self.scheduled_events = user_profile.get("events", [])
        self.all_tasks = user_profile.get("tasks", [])
        self.active_tasks = [t for t in self.all_tasks if t.status == 'active']
        self.routines = user_profile.get("routines", [])
        self.settings = user_profile.get("settings", {})
        self.schedule = {}
        self.all_day_event_notes = {}

    def _create_time_slots(self, day):
        slots = {}
        start_hour, end_hour = self.settings.get("schedule_window", (8, 21))
        dynamic_start_hour = start_hour
        for r in self.routines:
            if r.start_time and r.days_of_week and day.weekday() in r.days_of_week and r.start_time.hour < dynamic_start_hour:
                dynamic_start_hour = r.start_time.hour
        
        start_of_day = datetime.combine(day, time(dynamic_start_hour, 0))
        duration_hours = end_hour - dynamic_start_hour
        for i in range(int(duration_hours * 2)):
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
        if not self.settings.get("work_life_separation"): return 'any'
        personal_def = self.settings.get("personal_time_definition");
        if personal_def == "Weekends & Evenings":
            if day.weekday() >= 5: return 'Personal'
            if slot_time >= time(18, 0): return 'Personal'
            return 'Work'
        return 'Work'

    def generate_schedule(self):
        # Initialization
        for i in range(self.num_days):
            current_date = self.start_datetime.date() + timedelta(days=i)
            self.schedule[current_date] = self._create_time_slots(current_date)

        # Pass 1: Statics
        for event in self.scheduled_events:
            if event.start_time is None: self.all_day_event_notes[event.date] = event.name; continue
            if event.date in self.schedule:
                for slot_time in self.schedule[event.date]:
                    if event.start_time <= slot_time < event.end_time: self.schedule[event.date][slot_time] = f"FIXED: {event.name}"
        
        static_routines = [r for r in self.routines if not r.is_flexible]
        for day, slots in self.schedule.items():
            for routine in static_routines:
                is_today = (routine.days_of_week and day.weekday() in routine.days_of_week)
                if is_today:
                    for slot_time in slots:
                        if routine.start_time and routine.start_time <= slot_time < routine.end_time: slots[slot_time] = f"ROUTINE: {routine.name}"
        
        # Pass 2: Flexible Routines
        flexible_routines = [r for r in self.routines if r.is_flexible]
        for day, slots in self.schedule.items():
            for routine in flexible_routines:
                if routine.days_of_week and day.weekday() in routine.days_of_week:
                    if routine.name.lower() == 'exercise' and any("gym" in str(v) or "walk" in str(v) or "spin" in str(v) for v in slots.values()):
                        continue
                    if 'not_after' in routine.constraints and any(slot_time >= routine.constraints['not_after'] for slot_time, activity in slots.items() if activity is None):
                        pass # Constraint check will happen when placing
                    chunks_needed = math.ceil(routine.total_hours * 2)
                    for slot_start_time in sorted(slots.keys()):
                        # Constraint check
                        if 'not_after' in routine.constraints and slot_start_time >= routine.constraints['not_after']:
                            continue
                        
                        is_block_free = True; block_times = []
                        for i in range(chunks_needed):
                            current_slot_time = (datetime.combine(day, slot_start_time) + timedelta(minutes=30 * i)).time()
                            if slots.get(current_slot_time) is not None: is_block_free = False; break
                            block_times.append(current_slot_time)
                        if is_block_free:
                            for t in block_times: slots[t] = f"ROUTINE: {routine.name}"; break
        
        # Pass 3: Flexible Tasks
        category_types = self.settings.get("category_types", {})
        work_tasks = [t for t in self.active_tasks if category_types.get(t.category) == 'Work']
        personal_tasks = [t for t in self.active_tasks if category_types.get(t.category) == 'Personal']
        if not self.settings.get("work_life_separation"):
            work_tasks = self.active_tasks; personal_tasks = self.active_tasks

        work_chunks = sorted(self._create_task_chunks(work_tasks), key=lambda x: x.priority_score, reverse=True)
        personal_chunks = sorted(self._create_task_chunks(personal_tasks), key=lambda x: x.priority_score, reverse=True)

        for i in range(self.num_days):
            current_date = self.start_datetime.date() + timedelta(days=i)
            if current_date in self.schedule:
                for slot_time in sorted(self.schedule[current_date].keys()):
                    if current_date == self.start_datetime.date() and slot_time < self.start_datetime.time(): self.schedule[current_date][slot_time] = "PAST"; continue
                    if self.schedule[current_date][slot_time] is None:
                        context = self._get_slot_context(current_date, slot_time)
                        chunk_to_schedule = None
                        if context in ['any', 'Work'] and work_chunks: chunk_to_schedule = work_chunks.pop(0)
                        elif context in ['any', 'Personal'] and personal_chunks: chunk_to_schedule = personal_chunks.pop(0)
                        
                        if chunk_to_schedule: self.schedule[current_date][slot_time] = f"TASK: {chunk_to_schedule.name}"
        
        # Pass 4: Fill empty slots
        for day, slots in self.schedule.items():
             for slot_time in slots:
                if slots[slot_time] is None:
                    context = self._get_slot_context(day, slot_time)
                    chunk_to_fill = None
                    if context in ['any', 'Work'] and work_chunks: chunk_to_fill = work_chunks.pop(0)
                    elif context in ['any', 'Personal'] and personal_chunks: chunk_to_fill = personal_chunks.pop(0)
                    if chunk_to_fill: slots[slot_time] = f"TASK: {chunk_to_fill.name}"
                    else: slots[slot_time] = "Open / Free Time"
        
        return self.schedule, self.all_day_event_notes

# --- 3. The "Main" Block ---
if __name__ == "__main__":
    
    # --- Multi-user "Filing Cabinet" ---
    david_profile = {
        "name": "David",
        "settings": {
            "work_life_separation": False, "schedule_window": (8, 21),
            "DEFAULTS": { "Assignment": {"I": 7, "E": 4}, "Long-term project": {"U": 4, "I": 7, "E": 5},
                         "Value": {"U": 4, "I": 8, "E": 7}, "Hobby": {"U": 3, "I": 4, "E": 9} },
            "WEIGHTS": {"U": 2, "I": 1, "E": 1}
        },
        "events": [
            ScheduledEvent("CMSCE / marketing meeting with Sara", date(2025, 9, 3), time(10, 0), time(11, 0)),
            ScheduledEvent("CMSCE team meeting", date(2025, 9, 4), time(13, 0), time(14, 30)),
            ScheduledEvent("Peer mentoring session", date(2025, 9, 9), time(9, 30), time(12, 30)),
            ScheduledEvent("Dad call?", date(2025, 9, 9), time(14, 0), time(15, 0)),
            ScheduledEvent("GSAPP welcome picnic", date(2025, 9, 2), time(16, 45), time(18, 15)),
            ScheduledEvent("Drive home and drop off Elisa's car", date(2025, 9, 2), time(18, 15), time(19, 15)),
            ScheduledEvent("Performance review - Angelica", date(2025, 9, 18), time(11, 0), time(12, 0)),
            ScheduledEvent("Drive mom and Bry to the procedure", date(2025, 9, 10), None, None),
        ],
        "routines": [
             Routine("Dinner", [0,1,2,3,4,5,6], start_time=time(18,0), end_time=time(19,30)),
             Routine("Answering Email", [0,1,2,3,4], start_time=time(10,0), end_time=time(10,30)),
             Routine("Morning Rituals", [0,1,2,3,4], start_time=time(8,0), end_time=time(9,0)),
             Routine("Morning Rituals", [5,6], start_time=time(8,30), end_time=time(10,0)),
             Routine("Exercise", [0,1,2,3,4,5,6], total_hours=1.5, constraints={'not_after': time(17,0)}),
             Routine("Trash (and recycling)", [0,3], start_time=time(17,30), end_time=time(18,0)),
        ],
        "tasks": [
            Task("Contracts and MOUs for Angelica", "Assignment", total_hours=2, deadline=date(2025, 9, 5)),
            Task("slides to Angelica re: presentation", "Assignment", total_hours=2, deadline=date(2025, 9, 11)),
            Task("update slides for 16th and send to Angelica", "Assignment", total_hours=2, deadline=date(2025, 9, 11)),
            Task("Continue work on Activity Advisor program", "Long-term project", total_hours=10),
            Task("Boat stuff", "Long-term project", total_hours=1),
            Task("Solve printer offline", "Long-term project"),
            Task("Get RU-PSU football tickets", "Long-term project"),
            Task("Send keynote video to mom", "Long-term project", total_hours=0.5),
            Task("Boater endorsement on driver's license", "Long-term project"),
            Task("Get UW safety alerts", "Long-term project"),
            Task("Kurt - September plans", "Long-term project"),
            Task("Pursue School 81/consult Angelica", "Long-term project"),
            Task("Get back to Cameron", "Long-term project"),
            Task("Follow up with Erik on Summer Science", "Long-term project"),
            Task("Review AI overview from call", "Long-term project"),
            Task("Prepare for Angelica performance review", "Long-term project"),
            Task("Eddie email - maker / special ed redesign UD, AI", "Long-term project"),
            Task("Send around Educator's Guide to STEAM 2ed review", "Long-term project"),
            Task("email Angelica re School 81?", "Long-term project"),
            Task("Call Spencer's PT", "Long-term project"),
            Task("send mom and dad FB post from McNicholls", "Long-term project"),
            Task("new reverse osmosis", "Long-term project"),
            Task("Spencer's car", "Long-term project"),
            Task("Elisa's birthday", "Long-term project"),
            Task("September and October trip planning", "Long-term project"),
            Task("sink backed up again", "Long-term project"),
            Task("Ask Mitch about Dad call", "Long-term project"),
            Task("Tech/AI Ed needs assessment", "Long-term project", importance=9),
            Task("Project New Masters program", "Long-term project", importance=8),
            Task("Do something with Autism-Makerspace data", "Long-term project"),
            Task("register for Waterman?", "Long-term project"),
            Task("Announce/organize happy hour on 16th", "Long-term project"),
            Task("Behavioral sciences review - recommend Janice McDonnell", "Long-term project"),
            Task("Matt: NJTEEA conference and session/table", "Long-term project"),
            Task("Matt: NJTEEA marketing billing", "Long-term project"),
            Task("Patty - Gilbert and it certificaton - student program — sponsor, credit, marketing, etc.", "Long-term project"),
            Task("Gandhi", "Long-term project"),
            Task("Ezra!", "Long-term project"),
            Task("Talk to Rebecca Reynolds", "Long-term project"),
            Task("Spencer: meal plan", "Long-term project"),
            Task("Spencer: letter; write back?", "Long-term project"),
            Task("DOE info for Chris Anderson", "Long-term project"),
            Task("Call wine outlet for mom re credit card order", "Long-term project"),
            Task("This weekend: make plans for Elisa's birthday and for Sept-Oct", "Long-term project"),
            Task("Joel Cohen - mom's car", "Long-term project"),
            Task("Pillows", "Hobby"),
            Task("Wine shopping?", "Hobby"),
            Task("movies -- try Paul's rec", "Hobby", constraints={'preferred_days': [4,5], 'preferred_context': 'evening'}),
            Task("Time with my mom", "Value", total_hours=2, constraints={'preferred_days': [4,5,6,0]}),
            Task("Communicate with family and friends", "Value", total_hours=1),
        ]
    }
    
    clark_profile = { # ... Clark's full data profile ...
    }
    
    user_profiles = {"david": david_profile, "clark": clark_profile}
    active_user_id = "david" # <-- Set active user here
    
    active_user = user_profiles[active_user_id]
    start_date = date(2025, 9, 6) # Set start date here
    start_time_hour = active_user["settings"]["schedule_window"][0]
    start_time = time(start_time_hour, 0)
    
    # Prioritization Engine
    DEFAULTS = active_user["settings"]["DEFAULTS"]
    WEIGHTS = active_user["settings"]["WEIGHTS"]

    for task in active_user["tasks"]:
        if task.status == 'active':
            defaults = DEFAULTS.get(task.category, {})
            task.importance = getattr(task, 'importance', 0) or defaults.get("I", 0)
            task.enjoyment = getattr(task, 'enjoyment', 0) or defaults.get("E", 0)
            
            if task.category == "Assignment" and hasattr(task, 'deadline') and task.deadline:
                if isinstance(task.deadline, datetime): deadline_date = task.deadline.date()
                else: deadline_date = task.deadline
                work_days_left = (deadline_date - start_date).days
                if work_days_left < 1: work_days_left = 1
                required_pace = task.total_hours / work_days_left
                urgency_add = 5 if active_user_id == "david" else 0
                task.urgency = required_pace + urgency_add
            else:
                task.urgency = getattr(task, 'urgency', 0) or defaults.get("U", 0)
            
            numerator = (task.urgency * WEIGHTS["U"]) + (task.importance * WEIGHTS["I"]) + (task.enjoyment * WEIGHTS["E"])
            denominator = sum(WEIGHTS.values());
            task.priority_score = numerator / denominator
            
    my_scheduler = Scheduler(start_date, start_time, 7, active_user)
    final_schedule, all_day_notes = my_scheduler.generate_schedule()

    print(f"\n--- {active_user['name']}'s AI-Generated Schedule ---")
    for day, slots in final_schedule.items():
        print(f"\n--- {day.strftime('%A, %B %d, %Y')} ---")
        if day in all_day_notes: print(f"ALL DAY: {all_day_notes[day]}")
        
        sorted_times = sorted(slots.keys())
        i = 0
        while i < len(sorted_times):
            start_time = sorted_times[i]
            activity = slots[start_time]
            if activity == "PAST": i += 1; continue
            j = i
            while j + 1 < len(sorted_times) and slots.get(sorted_times[j+1]) == activity: j += 1
            end_time = (datetime.combine(date.today(), sorted_times[j]) + timedelta(minutes=30)).time()
            start_str = start_time.strftime('%I:%M %p')
            end_str = end_time.strftime('%I:%M %p')
            print(f"{start_str} - {end_str}: {activity}")
            i = j + 1
