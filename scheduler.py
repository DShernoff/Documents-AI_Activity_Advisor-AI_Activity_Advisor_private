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
    def __init__(self, name, category, urgency, importance, total_hours=1):
        self.name = name
        self.category = category
        self.urgency = urgency
        self.importance = importance
        self.total_hours = total_hours
        self.priority_score = (self.urgency * 2) + self.importance
        self.status = 'active'

class Routine:
    def __init__(self, name, days_of_week, start_time=None, end_time=None, total_hours=0):
        self.name = name
        self.days_of_week = days_of_week
        self.start_time = start_time
        self.end_time = end_time
        self.total_hours = total_hours
        self.is_flexible = (start_time is None)

# --- 2. The "Brain" - Scheduler Class v4.5 (Corrected) ---

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
                 if current_activity and "ADVISORY" in current_activity:
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
        advisory_tasks = sorted(self.active_tasks, key=lambda x: x.priority_score, reverse=True)
        for day, slots in self.schedule.items():
            if day in all_day_events: continue
            for slot_time in slots:
                if slots[slot_time] is None:
                    if advisory_tasks:
                        slots[slot_time] = f"ADVISORY: {advisory_tasks[0].category} work"
                    else:
                        slots[slot_time] = "Open / Free Time"
        
        self._ensure_diversity()
        return self.schedule

# --- 3. The "Main" Block ---
if __name__ == "__main__":
    start_date = date(2025, 8, 24)
    start_time = time(12, 0)
    
    user_events = [
        ScheduledEvent("Mom to say goodbye to Spencer", date(2025, 8, 24), time(11, 0), time(13, 0)),
        ScheduledEvent("Trip to Madison", date(2025, 8, 25), None, None),
        ScheduledEvent("Trip to Madison", date(2025, 8, 26), None, None),
        ScheduledEvent("Trip to Madison", date(2025, 8, 27), None, None),
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
        Task("Pack", "Assignment", 10, 5, total_hours=1.5),
        Task("Help Spencer to prepare", "Assignment", 10, 5, total_hours=1.5),
        Task("Compare rental car reservations", "Assignment", 10, 5, total_hours=0.5),
        Task("Cancel one Chicago dinner reservation", "Assignment", 10, 5, total_hours=0.5),
        Task("Tell Dean about our trip?", "Assignment", 10, 5, total_hours=0.5),
        Task("Give requested Feedback to Rough Draft math", "Assignment", 8, 5, total_hours=2),
        Task("Organize computer files", "Assignment", 7, 6, total_hours=6),
        # Long-term Projects
        Task("Continue work on Activity Advisor program", "Long-term project", 6, 7, total_hours=10),
        Task("Boat stuff", "Long-term project", 6, 7, total_hours=1),
        Task("Scanner is offline", "Long-term project", 6, 7, total_hours=1),
        Task("Solve printer offline", "Long-term project", 6, 7),
        Task("Get RU-PSU football tickets", "Long-term project", 6, 7),
        Task("Send keynote video to mom", "Long-term project", 6, 7, total_hours=0.5),
        Task("Boater endorsement on driver's license", "Long-term project", 6, 7),
        Task("Get UW safety alerts", "Long-term project", 6, 7),
        Task("Kurt - September plans", "Long-term project", 6, 7),
        Task("Reply to Beth and Ashley re Maker Cert", "Long-term project", 6, 7),
        Task("Pursue School 81/consult Angelica", "Long-term project", 6, 7),
        Task("Colleen Costigan letter (ai it?)", "Long-term project", 6, 7),
        Task("Get colleague/testers of scheduler", "Long-term project", 6, 7),
        Task("Get back to Cameron", "Long-term project", 6, 7),
        Task("Follow up with Erik on Summer Science", "Long-term project", 6, 7),
        Task("Review AI overview from call", "Long-term project", 6, 7),
        Task("Black face watch battery", "Long-term project", 6, 7),
        # Values
        Task("Call Dad (help with form?)", "Value", 2, 8),
        # Hobbies
        Task("Pillows", "Hobby", 3, 4),
        Task("Wine shopping?", "Hobby", 3, 4),
    ]
    
    completed_tasks = ["Pack", "Help Spencer to prepare", "Scanner is offline", "Compare rental car reservations", "Colleen Costigan letter (ai it?)"]
    for task in all_user_tasks:
        if task.name in completed_tasks:
            task.status = 'completed'

    for task in all_user_tasks:
        if task.status == 'active':
            if "Activity Advisor" in task.name:
                task.urgency = 7.5; task.priority_score = (task.urgency * 2) + task.importance
            if "Call Dad" in task.name:
                task.urgency = 8; task.priority_score = (task.urgency * 2) + task.importance
            
    my_scheduler = Scheduler(start_date, start_time, 8, user_events, all_user_tasks, user_routines, {})
    final_schedule = my_scheduler.generate_schedule()

    # --- CORRECTED AND RESTORED DISPLAY LOGIC ---
    print("\n--- Your AI-Generated Daily Schedule (v4.5.1 Corrected) ---")
    for day, slots in final_schedule.items():
        print(f"\n--- {day.strftime('%A, %B %d, %Y')} ---")
        if "All Day" in slots:
            print(slots["All Day"])
            continue
        
        sorted_times = sorted(slots.keys())
        i = 0
        while i < len(sorted_times):
            start_time = sorted_times[i]
            activity = slots[start_time]
            # Skip PAST slots
            if activity == "PAST":
                i += 1
                continue

            j = i
            # Consolidate identical, consecutive activities
            while j + 1 < len(sorted_times) and slots.get(sorted_times[j+1]) == activity:
                j += 1
            
            end_time = (datetime.combine(date.today(), sorted_times[j]) + timedelta(minutes=30)).time()
            
            start_str = start_time.strftime('%I:%M %p')
            end_str = end_time.strftime('%I:%M %p')
            
            print(f"{start_str} - {end_str}: {activity}")
            i = j + 1
