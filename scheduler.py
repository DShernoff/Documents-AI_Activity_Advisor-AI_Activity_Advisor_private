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
    def __init__(self, name, category, urgency, importance, total_hours=1, include_every_day=False):
        self.name = name
        self.category = category
        self.urgency = urgency
        self.importance = importance
        self.total_hours = total_hours
        self.include_every_day = include_every_day
        self.priority_score = (self.urgency * 2) + self.importance

# --- 2. The "Brain" - Scheduler Class v3.3 ---

class Scheduler:
    def __init__(self, start_date, num_days, scheduled_events, tasks, energy_levels):
        self.start_date = start_date
        self.num_days = num_days
        self.scheduled_events = scheduled_events
        self.tasks = tasks
        self.energy_levels = energy_levels
        self.schedule = {}

    def _create_time_slots(self, day):
        slots = {}
        start_of_day = datetime.combine(day, time(8, 0))
        for i in range(24): # 12 hours * 2 slots per hour
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

    def generate_schedule(self):
        # --- Initialization ---
        for i in range(self.num_days):
            current_date = self.start_date + timedelta(days=i)
            self.schedule[current_date] = self._create_time_slots(current_date)

        # --- Pass 1: Place all fixed, non-negotiable items ---
        all_day_events = []
        for event in self.scheduled_events:
            if event.start_time is None:
                all_day_events.append(event.date)
                self.schedule[event.date] = {"All Day": f"FIXED: {event.name}"}
                continue
            
            for slot_time in self.schedule[event.date]:
                if event.start_time <= slot_time < event.end_time:
                    self.schedule[event.date][slot_time] = f"FIXED: {event.name}"
        
        for day, slots in self.schedule.items():
            if day in all_day_events: continue
            # Add recurring Dinner
            for slot_time in slots:
                if time(18, 0) <= slot_time < time(19, 30):
                    slots[slot_time] = "FIXED: Dinner"
            # Add recurring weekday Email
            if day.weekday() < 5: # Monday to Friday
                 for slot_time in slots:
                    if time(10, 0) <= slot_time < time(10, 30):
                        slots[slot_time] = "FIXED: Answering Email"

        for day, energy in self.energy_levels.items():
            if energy == "Low" and day not in all_day_events:
                for slot_time in self.schedule[day]:
                    if time(16, 0) <= slot_time < time(18, 0):
                        self.schedule[day][slot_time] = "ADVISORY: Nap"

        # --- Pass 2: Place "Include Every Day" tasks ---
        daily_tasks = [task for task in self.tasks if task.include_every_day]
        for day, slots in self.schedule.items():
            if day in all_day_events or not daily_tasks: continue
            
            daily_task = daily_tasks[0]
            chunks_needed = math.ceil(daily_task.total_hours * 2)
            
            for slot_start_time in sorted(slots.keys()):
                is_block_free = True
                block_times = []
                for i in range(chunks_needed):
                    current_slot_time = (datetime.combine(day, slot_start_time) + timedelta(minutes=30 * i)).time()
                    if slots.get(current_slot_time) is not None:
                        is_block_free = False
                        break
                    block_times.append(current_slot_time)
                
                if is_block_free:
                    for t in block_times:
                        slots[t] = f"TASK: {daily_task.name}"
                    break # Placed for the day, move to next day
                    
        # --- Pass 3: Schedule remaining flexible tasks ---
        regular_tasks = [task for task in self.tasks if not task.include_every_day]
        task_chunks = self._create_task_chunks(regular_tasks)
        sorted_chunks = sorted(task_chunks, key=lambda x: x.priority_score, reverse=True)

        for day, slots in self.schedule.items():
            if day in all_day_events: continue
            
            for slot_time in sorted(slots.keys()):
                if not sorted_chunks: break
                if slots[slot_time] is None:
                    chunk_to_schedule = sorted_chunks.pop(0)
                    slots[slot_time] = f"TASK: {chunk_to_schedule.name}"

        # --- Pass 4: Fill any remaining empty slots ---
        advisory_tasks = sorted([task for task in self.tasks], key=lambda x: x.priority_score, reverse=True)
        for day, slots in self.schedule.items():
            if day in all_day_events: continue
            for slot_time in slots:
                if slots[slot_time] is None:
                    slots[slot_time] = f"ADVISORY: {advisory_tasks[0].category} work"

        return self.schedule


# --- 3. The "Main" Block ---
if __name__ == "__main__":
    start_date = date(2025, 8, 21)
    
    user_events = [
        ScheduledEvent("Call with Erik", date(2025, 8, 21), time(10, 30), time(11, 30)),
        ScheduledEvent("Call with Eddie", date(2025, 8, 21), time(11, 30), time(12, 30)),
        ScheduledEvent("Beach day", date(2025, 8, 22), None, None),
        ScheduledEvent("Trip to Madison", date(2025, 8, 25), None, None),
        ScheduledEvent("Trip to Madison", date(2025, 8, 26), None, None),
        ScheduledEvent("Trip to Madison", date(2025, 8, 27), None, None),
    ]

    user_tasks = [
        Task("Give requested Feedback to Rough Draft math", "Assignment", 8, 5, total_hours=2),
        Task("Make sure we have Spencer's allowance settled", "Assignment", 10, 5, total_hours=1),
        Task("Tell Dean about our trip?", "Assignment", 10, 5, total_hours=0.5),
        Task("Review AI overview from call", "Long-term project", 6, 7),
        Task("Continue work on Activity Advisor program", "Long-term project", 6, 7, total_hours=10),
        Task("Call team meeting re: new course development", "Long-term project", 6, 7),
        Task("Ask Eddie and Brielle about STARS sustainability rating", "Long-term project", 6, 7),
        Task("Help Spencer to prepare", "Long-term project", 6, 7, total_hours=2),
        Task("Boat stuff", "Long-term project", 6, 7, total_hours=1),
        Task("Scanner is offline", "Long-term project", 6, 7, total_hours=1),
        Task("Exercise", "Value", 2, 8, total_hours=1.5, include_every_day=True),
        Task("Call Dad (help with form?)", "Value", 2, 8),
        Task("Mom to say goodbye to Spencer", "Value", 2, 8),
        Task("Pillows", "Hobby", 3, 4),
        Task("Wine shopping?", "Hobby", 3, 4),
    ]
    
    # --- SIMULATING "FLOW MODE" ---
    # To simulate the user pressing the "Flow Mode" button for the Activity Advisor task,
    # we find the task and temporarily boost its urgency before running the scheduler.
    for task in user_tasks:
        if "Activity Advisor" in task.name:
            task.urgency = 9 # Boost from 6 to 9
            task.priority_score = (task.urgency * 2) + task.importance # Recalculate score
            print(f"--- FLOW MODE ACTIVATED for '{task.name}' (New Score: {task.priority_score}) ---")

    user_energy_levels = {date(2025, 8, 21): "Low"}

    my_scheduler = Scheduler(start_date, 7, user_events, user_tasks, user_energy_levels)
    final_schedule = my_scheduler.generate_schedule()

    print("\n--- Your AI-Generated Daily Schedule (v3.3 with Flow Mode) ---")
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
            j = i
            while j + 1 < len(sorted_times) and slots[sorted_times[j+1]] == activity:
                j += 1
            end_time = (datetime.combine(date.today(), sorted_times[j]) + timedelta(minutes=30)).time()
            
            start_str = start_time.strftime('%I:%M %p')
            end_str = end_time.strftime('%I:%M %p')
            
            print(f"{start_str} - {end_str}: {activity}")
            i = j + 1
