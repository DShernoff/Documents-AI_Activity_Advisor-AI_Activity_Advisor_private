### **The Definitive Python Script (Brain v13.0)**```python
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
    def __init__(self, name, category, urgency=0, importance=0, enjoyment=0, total_hours=1, deadline=None, constraints=None, status='active', source_event=None):
        self.name = name
        self.category = category
        self.urgency = urgency
        self.importance = importance
        self.enjoyment = enjoyment
        self.total_hours = total_hours
        self.deadline = deadline
        self.priority_score = 0
        self.status = status
        self.source_event = source_event
        self.constraints = constraints or {}
        self.rationale = "" # For the "Why this now?" feature

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
        self.daily_log = {}

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
                    if any(event.start_time < routine.end_time and event.end_time > routine.start_time for event in self.scheduled_events if event.date == day and event.start_time):
                        continue
                    for slot_time in slots:
                        if routine.start_time and routine.start_time <= slot_time < routine.end_time: slots[slot_time] = f"ROUTINE: {routine.name}"
        
        # Pass 2: Flexible Routines
        flexible_routines = [r for r in self.routines if r.is_flexible]
        for day, slots in self.schedule.items():
            for routine in flexible_routines:
                if routine.days_of_week and day.weekday() in routine.days_of_week:
                    if routine.name.lower() == 'exercise' and any("triathlon" in str(v) for v in slots.values()):
                        continue
                    chunks_needed = math.ceil(routine.total_hours * 2)
                    for slot_start_time in sorted(slots.keys()):
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

# --- "Rationale Engine" & "Training Mode" Logic ---
def generate_rationale(task, a_user_profile):
    weights = a_user_profile["settings"]["WEIGHTS"]
    score_string = f"This is one of your high-priority tasks with a score of **{task.priority_score:.2f}**."
    
    urg_score = task.urgency * weights["U"]
    imp_score = task.importance * weights["I"]
    enj_score = task.enjoyment * weights["E"]
    max_score = max(urg_score, imp_score, enj_score)
    
    primary_driver = ""
    if max_score == urg_score and task.urgency > 0:
        if task.category == "Assignment" and task.deadline:
            primary_driver = f"Its priority is driven by its upcoming **{task.deadline.strftime('%B %d')} deadline**, making it highly urgent."
        else:
            primary_driver = f"Its priority is driven by its high **Urgency** rating."
    elif max_score == imp_score:
        primary_driver = f"Its priority is driven by its high **Importance** rating, aligning with your key goals."
    else:
        primary_driver = f"Its priority is driven by its high **Enjoyment** rating, making it a great choice for this time."

    conclusion = ""
    if task.category == "Hobby" and enj_score > (urg_score + imp_score):
         conclusion = "Taking a break for a hobby you love is a great way to recharge your creative energy."
    elif task.category == "Assignment":
         conclusion = "Scheduling it now ensures you make steady progress and avoid a last-minute rush."
    
    final_rationale = f"{score_string}\n- {primary_driver}\n- {conclusion}"
    task.rationale = final_rationale
    return final_rationale

def log_activity(schedule_log, day, time_slot, planned_activity, actual_activity, reason=None):
    if day not in schedule_log: schedule_log[day] = []
    log_entry = { "time": time_slot, "planned": planned_activity, "actual": actual_activity, "reason": reason }
    schedule_log[day].append(log_entry)
    print(f"LOGGED: At {time_slot.strftime('%I:%M %p')} on {day.strftime('%A')}, you did '{actual_activity}'.")

def end_of_day_review(schedule_log, day):
    print(f"\n--- AI End-of-Day Review for {day.strftime('%A')} ---")
    log_for_day = schedule_log.get(day)
    if not log_for_day: print("No activities were logged for today."); return
    insights = []
    for entry in log_for_day:
        if entry["planned"] != entry["actual"]:
            insight = f"At {entry['time'].strftime('%I:%M %p')}, the plan was '{entry['planned']}', but you chose '{entry['actual']}' instead."
            if entry["reason"]: insight += f" Your reason was: '{entry['reason']}'. This is a valuable signal!"
            else: insight += " I will learn from this choice."
            insights.append(insight)
    if not insights: print("You followed the schedule perfectly today! Great job.")
    else:
        print("Found the following learning opportunities:")
        for insight in insights: print(f"- {insight}")

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
            ScheduledEvent("Peer mentoring session", date(2025, 9, 9), time(9, 30), time(12, 30)),
            ScheduledEvent("Drive mom and Bry to the procedure", date(2025, 9, 10), None, None),
            ScheduledEvent("Call with Eddie and Chris", date(2025, 9, 10), time(14, 0), time(15, 30)),
            ScheduledEvent("Division-wide meeting with Angelica (small presentation)", date(2025, 9, 16), time(14, 0), time(15, 30)),
            ScheduledEvent("Dad call?", date(2025, 9, 16), time(13, 0), time(14, 0)),
            ScheduledEvent("Performance review - Angelica", date(2025, 9, 18), time(11, 0), time(12, 0)),
            ScheduledEvent("Mandy Jansen interview", date(2025, 9, 26), time(15, 0), time(16, 0)),
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
            Task("slides to Angelica re: presentation", "Assignment", total_hours=2, deadline=date(2025, 9, 11)),
            Task("update slides for 16th and send to Angelica", "Assignment", total_hours=2, deadline=date(2025, 9, 11)),
            Task("New Goal setting (email on 9/8 form SR VP Hum Resources)", "Assignment", total_hours=2, deadline=date(2025, 9, 30)),
            Task("3 peaks deposit due Oct 1", "Assignment", total_hours=0.5, deadline=date(2025, 10, 1)),
            Task("Gifts for Elisa", "Assignment", total_hours=2, deadline=date(2025, 9, 20)),
            Task("Elisa's birthday", "Assignment", total_hours=2, deadline=date(2025, 9, 20)),
            Task("triathlon training", "Assignment", total_hours=3, deadline=date(2025, 9, 7)),
            Task("Continue work on Activity Advisor program", "Long-term project", urgency=10, importance=9.5, enjoyment=9),
            Task("Boat stuff", "Long-term project", urgency=7, importance=6, enjoyment=7),
            Task("Send keynote video to mom", "Long-term project", urgency=3, importance=4, enjoyment=6),
            Task("Boater endorsement on driver's license", "Long-term project", urgency=5, importance=5, enjoyment=2),
            Task("Get UW safety alerts", "Long-term project", urgency=4, importance=4, enjoyment=1),
            Task("Kurt - September plans", "Long-term project", urgency=8, importance=5, enjoyment=4),
            Task("Pursue School 81/consult Angelica", "Long-term project", urgency=6, importance=8, enjoyment=2),
            Task("Get back to Cameron", "Long-term project", urgency=4, importance=3, enjoyment=5),
            Task("Follow up with Erik on Summer Science", "Long-term project", urgency=2, importance=4, enjoyment=7),
            Task("Review AI overview from call", "Long-term project", urgency=3, importance=4, enjoyment=4),
            Task("Prepare for Angelica performance review", "Long-term project", urgency=4, importance=8, enjoyment=3),
            Task("Eddie email - maker / special ed redesign UD, AI", "Long-term project", urgency=2, importance=2, enjoyment=4),
            Task("Send around Educator's Guide to STEAM 2ed review", "Long-term project", urgency=2, importance=3, enjoyment=7),
            Task("email Angelica re School 81?", "Long-term project", urgency=4, importance=4, enjoyment=3),
            Task("Call Spencer's PT", "Long-term project", urgency=5, importance=4, enjoyment=3),
            Task("send mom and dad FB post from McNicholls", "Long-term project", urgency=2, importance=2, enjoyment=4),
            Task("new reverse osmosis", "Long-term project", urgency=4, importance=4, enjoyment=1),
            Task("Spencer's car", "Long-term project", urgency=3, importance=4, enjoyment=4),
            Task("September and October trip planning", "Long-term project", urgency=7, importance=5, enjoyment=3),
            Task("sink backed up again", "Long-term project", urgency=5, importance=5, enjoyment=1),
            Task("Ask Mitch about Dad call", "Long-term project", urgency=8, importance=5, enjoyment=6),
            Task("Announce/organize happy hour on 16th", "Long-term project", urgency=9, importance=5, enjoyment=3),
            Task("Spencer meal plan", "Long-term project", urgency=1, importance=5, enjoyment=3),
            Task("Tech/AI Ed needs assessment", "Long-term project", urgency=6, importance=8, enjoyment=5),
            Task("Project New Masters program", "Long-term project", urgency=4, importance=8, enjoyment=4),
            Task("Do something with Autism-Makerspace data", "Long-term project", urgency=3, importance=5, enjoyment=4),
            Task("Host NJTEEA site visit", "Long-term project", urgency=5, importance=6, enjoyment=6),
            Task("Yes tickets debacle", "Long-term project", urgency=8, importance=4, enjoyment=6),
            Task("Colleen Costagan - check when scholarship will be applied", "Long-term project", urgency=9, importance=7, enjoyment=2),
            Task("Boat!", "Long-term project", urgency=4, importance=3, enjoyment=8),
            Task("Check Spencer's tuition balance around the 24th", "Long-term project", urgency=4, importance=3, enjoyment=2),
            Task("Check w team re who does what on 16th - again", "Long-term project", urgency=9, importance=5, enjoyment=4),
            Task("Give mentoring group fair warning canceling the 16th", "Long-term project", urgency=9, importance=4, enjoyment=3),
            Task("Tweek slides for next Tues again for just Eddie and me", "Long-term project", urgency=9, importance=8, enjoyment=3),
            Task("Colleen Costagan - check when scholarship will be applied - check hyunjo on Mon", "Long-term project", urgency=8, importance=6, enjoyment=2),
            Task("Ray?", "Long-term project", urgency=3, importance=5, enjoyment=4),
            Task("Matt email - reply, send to eddie, pay marketing fee", "Long-term project", urgency=5, importance=5, enjoyment=2),
            Task("Gifts for Elisa", "Long-term project", urgency=9, importance=7, enjoyment=6),
            Task("Matt: NJTEEA conference and session/table", "Long-term project", urgency=5, importance=4, enjoyment=3),
            Task("Matt: NJTEEA marketing billing", "Long-term project", urgency=8, importance=5, enjoyment=2),
            Task("Patty - Gilbert and it certificaton - student program — sponsor, credit, marketing, etc.", "Long-term project", urgency=6, importance=4, enjoyment=1),
            Task("Gandhi", "Long-term project", urgency=8, importance=8, enjoyment=8),
            Task("Ezra!", "Long-term project", urgency=7, importance=7, enjoyment=7),
            Task("Talk to Rebecca Reynolds", "Long-term project", urgency=5, importance=5, enjoyment=5),
            Task("Spencer: meal plan", "Long-term project", urgency=2, importance=5, enjoyment=5),
            Task("Spencer: letter; write back?", "Long-term project", urgency=4, importance=8, enjoyment=8),
            Task("Time with my mom", "Value", total_hours=2),
            Task("Communicate with family and friends", "Value", total_hours=1),
            Task("Pillows", "Hobby"),
            Task("Wine shopping?", "Hobby"),
            Task("movies -- try Paul's rec", "Hobby", constraints={'preferred_days': [4,5], 'preferred_context': 'evening'}),
        ]
    }
    
    clark_profile = {
        "name": "Clark",
        # ... (full, correct data profile for Clark)
    }

    elisa_profile = {
        "name": "Elisa",
        # ... (full, correct data profile for Elisa)
    }
    
    user_profiles = {"david": david_profile, "clark": clark_profile, "elisa": elisa_profile}
    active_user_id = "david"
    
    active_user = user_profiles[active_user_id]
    start_date = date(2025, 9, 10)
    start_time_hour, _ = active_user["settings"]["schedule_window"]
    start_time = time(start_time_hour, 0)
    
    # Prioritization Engine
    DEFAULTS = active_user["settings"]["DEFAULTS"]
    WEIGHTS = active_user["settings"]["WEIGHTS"]

    for task in active_user["tasks"]:
        if task.status == 'active':
            # This logic now correctly handles overrides vs defaults
            defaults = DEFAULTS.get(task.category, {})
            task.urgency = task.urgency or defaults.get("U", 0)
            task.importance = task.importance or defaults.get("I", 0)
            task.enjoyment = task.enjoyment or defaults.get("E", 0)
            
             # --- UPGRADED: Universal Temporal Urgency Logic ---
            if hasattr(task, 'deadline') and task.deadline:
                # This logic now applies to ANY task with a deadline
                work_days_left = (task.deadline - start_date).days
                if work_days_left < 1: work_days_left = 1
                required_pace = task.total_hours / work_days_left
        
        # The +5 modifier is specific to David's Assignments
        urgency_add = 0
        if active_user_id == "david" and task.category == "Assignment":
            urgency_add = 5
            
        task.urgency = required_pace + urgency_add
    else:
        # This is for tasks without a deadline
        task.urgency = task.urgency or defaults.get("U", 0)
            
        numerator = (task.urgency * WEIGHTS["U"]) + (task.importance * WEIGHTS["I"]) + (task.enjoyment * WEIGHTS["E"])
        denominator = sum(WEIGHTS.values());
        task.priority_score = numerator / denominator
            
        generate_rationale(task, active_user)
            
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
    
    # --- AI Training Mode Simulation ---
    print("\n\n=============================================")
    print("--- AI TRAINING MODE SIMULATION ---")
    print("=============================================")

    first_day_date = sorted(final_schedule.keys())[0]
    
    log_activity(my_scheduler.daily_log, first_day_date, time(9, 0), "slides to Angelica re: presentation", "slides to Angelica re: presentation")
    log_activity(my_scheduler.daily_log, first_day_date, time(12, 0), "update slides for 16th and send to Angelica", "Project New Masters program", reason="Sudden inspiration")
    log_activity(my_scheduler.daily_log, first_day_date, time(13, 0), "Continue work on Activity Advisor program", "Pillows")

    end_of_day_review(my_scheduler.daily_log, first_day_date)
    
     # --- NEW: "Why This Now?" Rationale Simulation ---
    print("\n\n=============================================")
    print("--- 'WHY THIS NOW?' RATIONALE SIMULATION ---")
    print("=============================================")

    # Find a specific task in the schedule to test
    # Let's find the 'Pack' task from today's schedule
    today_date = start_date
    task_to_test = None
    for task in active_user["tasks"]:
        if "Continue work on Activity Advisor program" in task.name:
            task_to_test = task
            break

    if task_to_test:
        print(f"You asked for the rationale for the task: '{task_to_test.name}'")
        print("--------------------------------------------------")
        # The rationale was already generated and stored when we calculated priorities
        print(task_to_test.rationale)
    else:
        print("Could not find the 'Pack' task to test the rationale.")
