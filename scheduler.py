# Import necessary libraries
from datetime import time, timedelta, date, datetime
import math
import copy
import google.generativeai as genai
import os

# --- 1. Data Structures ---

class ScheduledEvent:
    def __init__(self, name, event_date, start_time, end_time):
        self.name = name
        self.date = event_date
        self.start_time = start_time
        self.end_time = end_time

class Task:
    def __init__(self, name, category, urgency=0, importance=0, enjoyment=0, total_hours=1, deadline=None, is_for_today=False, one_off_today=False, constraints=None):
        self.name = name
        self.category = category
        self.urgency = urgency
        self.importance = importance
        self.enjoyment = enjoyment
        self.total_hours = total_hours
        self.deadline = deadline
        self.priority_score = 0
        self.status = 'active'
        self.is_for_today = is_for_today
        self.one_off_today = one_off_today
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

# --- 2. The "Brain" - Scheduler Class v9.1 ---

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
        self.scheduled_task_names = set()

    def _create_time_slots(self, day):
        slots = {}
        start_hour, end_hour = self.settings.get("schedule_window", (8, 21))
        duration_hours = end_hour - start_hour
        start_of_day = datetime.combine(day, time(start_hour, 0))
        for i in range(duration_hours * 2):
            slot_time = (start_of_day + timedelta(minutes=30 * i)).time()
            slots[slot_time] = None
        return slots

    def _create_task_chunks(self, tasks, for_today_only=False):
        chunked_list = []
        for task in tasks:
            hours = task.total_hours
            if for_today_only and task.is_for_today:
                hours = getattr(task, 'today_hours', 0.5)
            num_chunks = math.ceil(hours * 2)
            for _ in range(num_chunks):
                chunked_list.append(copy.copy(task))
        return chunked_list
    
    def _check_constraints(self, task, slot_time):
        if 'not_before' in task.constraints and slot_time < task.constraints['not_before']:
            return False
        return True

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
            # Handle dynamic schedule window
            start_hour, _ = self.settings.get("schedule_window", (8, 21))
            # Special case for Elisa's early commute
            if self.user_profile["name"] == "Elisa" and current_date.weekday() < 2:
                 start_hour = 6
            self.schedule[current_date] = self._create_time_slots(current_date)
            # Re-create slots if dynamic start time is needed
            if start_hour != self.settings.get("schedule_window", (8, 21))[0]:
                self.schedule[current_date] = {}
                start_of_day = datetime.combine(current_date, time(start_hour, 30))
                num_slots = (self.settings.get("schedule_window", (8, 21))[1] - start_hour) * 2
                for i in range(int(num_slots)):
                    slot_time = (start_of_day + timedelta(minutes=30 * i)).time()
                    self.schedule[current_date][slot_time] = None


        # Pass 1: Statics
        all_day_events = []
        for event in self.scheduled_events:
            if event.start_time is None: all_day_events.append(event.date); self.schedule[event.date] = {"All Day": f"FIXED: {event.name}"}; continue
            if event.date in self.schedule:
                for slot_time in self.schedule[event.date]:
                    if event.start_time <= slot_time < event.end_time: self.schedule[event.date][slot_time] = f"FIXED: {event.name}"
        
        static_routines = [r for r in self.routines if not r.is_flexible]
        for day, slots in self.schedule.items():
            if day in all_day_events: continue
            for routine in static_routines:
                is_today = (routine.days_of_week and day.weekday() in routine.days_of_week) or \
                           (routine.day_of_month and day.day == routine.day_of_month)
                if is_today:
                    for slot_time in slots:
                        if routine.start_time <= slot_time < routine.end_time: slots[slot_time] = f"ROUTINE: {routine.name}"
        
        # Pass 2: "For Today" tasks
        today_date = self.start_datetime.date()
        if today_date in self.schedule and today_date not in all_day_events:
            for_today_tasks = [t for t in self.active_tasks if t.is_for_today]
            today_chunks = self._create_task_chunks(for_today_tasks, for_today_only=True)
            for chunk in today_chunks: chunk.priority_score = 99
            today_chunks = sorted(today_chunks, key=lambda x: x.priority_score, reverse=True)
            for slot_time in sorted(self.schedule[today_date].keys()):
                if not today_chunks: break
                if self.schedule[today_date][slot_time] is None:
                    found_chunk = False
                    for index, chunk in enumerate(today_chunks):
                        if self._check_constraints(chunk, slot_time):
                            self.schedule[today_date][slot_time] = f"TASK: {chunk.name}"
                            self.scheduled_task_names.add(chunk.name)
                            today_chunks.pop(index); found_chunk = True; break
        
        # Pass 3: Flexible Routines
        flexible_routines = [r for r in self.routines if r.is_flexible]
        for day, slots in self.schedule.items():
            if day in all_day_events: continue
            for routine in flexible_routines:
                if routine.days_of_week and day.weekday() in routine.days_of_week:
                    chunks_needed = math.ceil(routine.total_hours * 2)
                    for slot_start_time in sorted(slots.keys()):
                        is_block_free = True; block_times = []
                        for i in range(chunks_needed):
                            current_slot_time = (datetime.combine(day, slot_start_time) + timedelta(minutes=30 * i)).time()
                            if slots.get(current_slot_time) is not None: is_block_free = False; break
                            block_times.append(current_slot_time)
                        if is_block_free:
                            for t in block_times: slots[t] = f"ROUTINE: {routine.name}"; break

        # Pass 4: Remaining Flexible Tasks
        remaining_tasks = [t for t in self.active_tasks if not t.is_for_today]
        category_types = self.settings.get("category_types", {})
        work_tasks = [t for t in remaining_tasks if category_types.get(t.category) == 'Work']
        personal_tasks = [t for t in remaining_tasks if category_types.get(t.category) == 'Personal']
        work_chunks = sorted(self._create_task_chunks(work_tasks), key=lambda x: x.priority_score, reverse=True)
        personal_chunks = sorted(self._create_task_chunks(personal_tasks), key=lambda x: x.priority_score, reverse=True)

        for i in range(self.num_days):
            current_date = self.start_datetime.date() + timedelta(days=i)
            if current_date in self.schedule and current_date not in all_day_events:
                for slot_time in sorted(self.schedule[current_date].keys()):
                    if current_date == self.start_datetime.date() and slot_time < self.start_datetime.time(): self.schedule[current_date][slot_time] = "PAST"; continue
                    if self.schedule[current_date][slot_time] is None:
                        context = self._get_slot_context(current_date, slot_time)
                        chunk_to_schedule = None
                        if context in ['any', 'Work'] and work_chunks: chunk_to_schedule = work_chunks.pop(0)
                        elif context in ['any', 'Personal'] and personal_chunks: chunk_to_schedule = personal_chunks.pop(0)
                        
                        if chunk_to_schedule:
                            self.schedule[current_date][slot_time] = f"TASK: {chunk_to_schedule.name}"
                            self.scheduled_task_names.add(chunk_to_schedule.name)
        
        # Pass 5: Fill empty slots
        for day, slots in self.schedule.items():
             if day in all_day_events: continue
             for slot_time in slots:
                if slots[slot_time] is None:
                    context = self._get_slot_context(day, slot_time)
                    chunk_to_fill = None
                    if context in ['any', 'Work'] and work_chunks: chunk_to_fill = work_chunks.pop(0)
                    elif context in ['any', 'Personal'] and personal_chunks: chunk_to_fill = personal_chunks.pop(0)
                    if chunk_to_fill:
                        slots[slot_time] = f"TASK: {chunk_to_fill.name}"
                    else:
                        slots[slot_time] = "Open / Free Time"
        
        return self.schedule

# --- FULLY RESTORED AI Companion Module ---
class AI_Companion:
    def __init__(self, api_key):
        try:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-pro')
            self.is_active = True
        except Exception as e:
            print(f"Error configuring AI Companion: {e}")
            self.is_active = False

    def generate_daily_forecast(self, user_name, schedule_for_today):
        if not self.is_active: return "AI Companion is currently unavailable."
        density = "moderately busy"; dominant_category = "Work tasks"
        prompt = f"""
        You are an AI companion for a user named {user_name}. Today is {date.today().strftime('%A, %B %d')}.
        Generate a short, encouraging 'Daily Forecast' (like a mindful horoscope) based on this data:
        - Today's Schedule Density: {density}
        - Dominant Task Categories: {dominant_category}
        Based on this, generate the forecast.
        """
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error getting forecast from AI: {e}"

    def suggest_new_activity(self, user_name, user_hobbies):
        if not self.is_active: return "AI Companion is currently unavailable."
        prompt = f"""
        A user named {user_name} has free time. Their hobbies include: {', '.join(user_hobbies)}.
        Suggest one single, novel, 30-minute activity they might enjoy.
        Format as: SUGGESTION: [Name] RATIONALE: [Reason]
        """
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error getting suggestion from AI: {e}"

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
        "events": [ # David's events
            ScheduledEvent("CMSCE / marketing meeting with Sara", date(2025, 9, 3), time(10, 0), time(11, 0)),
            ScheduledEvent("CMSCE team meeting", date(2025, 9, 4), time(13, 0), time(14, 30)),
        ],
        "routines": [ # David's routines
             Routine("Dinner", [0,1,2,3,4,5,6], start_time=time(18,0), end_time=time(19,30)),
             Routine("Exercise", [0,1,2,3,4,5,6], total_hours=1.5),
        ],
        "tasks": [ # David's tasks
            Task("Continue work on Activity Advisor program", "Long-term project", total_hours=10),
        ]
    }

    elisa_profile = {
        "name": "Elisa",
        "settings": {
            "work_life_separation": True, "personal_time_definition": "Weekends & Evenings",
            "schedule_window": (7, 21), "category_types": { "Assignment": "Work", "Long-term project": "Work",
                                                            "Value": "Personal", "Hobby": "Personal" },
            "DEFAULTS": { "Assignment": {"I": 10, "E": 4}, "Long-term project": {"U": 8, "I": 7, "E": 5},
                         "Value": {"U": 9, "I": 10, "E": 10}, "Hobby": {"U": 3, "I": 4, "E": 9} },
            "WEIGHTS": {"U": 1, "I": 1, "E": 1}
        },
        "events": [ # Elisa's events
            ScheduledEvent("Jennifer Foster?", date(2025, 9, 2), time(9, 0), time(10, 0)),
        ],
        "routines": [ # Elisa's routines
             Routine("Commute to work", [0, 1], start_time=time(6,30), end_time=time(7,15)),
             Routine("Dinner", [0,1,2,3,4], start_time=time(18,0), end_time=time(18,30)),
        ],
        "tasks": [ # Elisa's tasks
            Task("Call liberty corner exxon", "Assignment", total_hours=0.25, deadline=date(2025, 9, 2)),
        ]
    }
    
    user_profiles = {"david": david_profile, "elisa": elisa_profile}
    active_user_id = "elisa" # <-- CHANGE THIS to "david" to run his schedule
    
    # --- Load Active User Data ---
    active_user = user_profiles[active_user_id]
    start_date = date(2025, 9, 2)
    start_time = time(active_user["settings"]["schedule_window"][0], 0)
    
    # --- Prioritization Engine ---
    DEFAULTS = active_user["settings"]["DEFAULTS"]
    WEIGHTS = active_user["settings"]["WEIGHTS"]

    for task in active_user["tasks"]:
        if task.status == 'active':
            defaults = DEFAULTS.get(task.category, {})
            task.importance = defaults.get("I", 0); task.enjoyment = defaults.get("E", 0)
            if task.category == "Assignment" and task.deadline:
                work_days_left = (task.deadline - start_date).days
                if work_days_left < 1: work_days_left = 1
                required_pace = task.total_hours / work_days_left
                # Use different urgency formulas per user
                urgency_add = 5 if active_user_id == "david" else 0
                task.urgency = required_pace + urgency_add
            else:
                task.urgency = defaults.get("U", 0)
            
            numerator = (task.urgency * WEIGHTS["U"]) + (task.importance * WEIGHTS["I"]) + (task.enjoyment * WEIGHTS["E"])
            denominator = sum(WEIGHTS.values());
            task.priority_score = numerator / denominator
            
    # --- Run Scheduler and Print ---
    my_scheduler = Scheduler(start_date, start_time, 7, active_user)
    final_schedule = my_scheduler.generate_schedule()

    print(f"\n--- {active_user['name']}'s AI-Generated Schedule (v9.1) ---")
    for day, slots in final_schedule.items():
        print(f"\n--- {day.strftime('%A, %B %d, %Y')} ---")
        if "All Day" in slots: print(slots["All Day"]); continue
        
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
