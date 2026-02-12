# LMS Module – Required Data Points (from School Management Module)

Ye document School Management module se LMS ke liye **saari main points aur data needs** list karta hai. Har section me “LMS me chahiye” / “Source model” clearly likha hai.

---

## 1. STUDENT DATA (LMS ke liye)

| # | Field / Data Point | Model | Field Name | LMS Use |
|---|--------------------|-------|------------|---------|
| 1 | Student Name | school.student | name | Profile, display |
| 2 | Roll Number | school.student | roll_number | Login/identity, reports |
| 3 | Admission Number | school.student | admission_number | Unique ID, cards |
| 4 | Date of Birth | school.student | date_of_birth | Profile, age |
| 5 | Gender | school.student | gender | Profile, filters |
| 6 | Email | school.student | email | Login, notifications |
| 7 | Phone | school.student | phone | Contact, SMS/WhatsApp |
| 8 | Photo | school.student | photo | Profile picture |
| 9 | Current Class | school.student | class_id | Class, section, year |
| 10 | Class Display (Name-Section-Year) | school.student | class_display | Read-only display |
| 11 | Subjects (enrolled) | school.student | subject_ids | Course list, modules |
| 12 | Status | school.student | state | draft / admitted / left |
| 13 | Parent/Guardian Name | school.student | parent_name | Contact |
| 14 | Parent Phone | school.student | parent_phone | Notifications |
| 15 | Parent Email | school.student | parent_email | Notifications |
| 16 | Portal User (res.partner) | school.student | partner_id | LMS login, portal |
| 17 | Class History | school.student | class_history_ids | Past classes, promotion |
| 18 | Attendance Records | school.student | attendance_ids | LMS activity / reports |
| 19 | Address | school.student | address | Profile (optional) |
| 20 | Blood Group | school.student | blood_group | Profile (optional) |

**LMS ke liye minimum student keys:**  
`name`, `roll_number`, `admission_number`, `email`, `class_id`, `subject_ids`, `partner_id`, `state`, `class_display`, `attendance_ids`, `class_history_ids`.

---

## 2. TEACHER DATA (LMS ke liye)

| # | Field / Data Point | Model | Field Name | LMS Use |
|---|--------------------|-------|------------|---------|
| 1 | Teacher Name | school.teacher | name | Profile, display |
| 2 | Email | school.teacher | email | Login, notifications |
| 3 | Phone | school.teacher | phone | Contact |
| 4 | Photo | school.teacher | photo | Profile picture |
| 5 | Subjects (assigned) | school.teacher | subject_ids | Which subjects they teach |
| 6 | Employee ID | school.teacher | employee_id | Unique ID |
| 7 | Portal/Partner | school.teacher | partner_id | LMS login, portal |
| 8 | Hire Date | school.teacher | hire_date | Profile (optional) |
| 9 | Active | school.teacher | active | Show/hide in LMS |

**LMS ke liye minimum teacher keys:**  
`name`, `email`, `subject_ids`, `partner_id`, `employee_id`, `active`.

**Note:** Kis teacher ne kis **class** me konsa subject padhana hai, ye **timetable** se aata hai (Section 5).

---

## 3. SUBJECT DATA (LMS ke liye)

| # | Field / Data Point | Model | Field Name | LMS Use |
|---|--------------------|-------|------------|---------|
| 1 | Subject Name | school.subject | name | Course name |
| 2 | Class (subject belongs to) | school.subject | class_id | Class-wise course |
| 3 | Maximum Marks | school.subject | max_marks | Grading, result |
| 4 | Description | school.subject | description | Syllabus / outline |

**LMS ke liye minimum subject keys:**  
`name`, `class_id`, `max_marks`, `description`.

**Important:** Subject me **direct teacher field nahi**; teacher–subject link **school.timetable** se aata hai (class + subject + teacher).

---

## 4. CLASS DATA (LMS ke liye)

| # | Field / Data Point | Model | Field Name | LMS Use |
|---|--------------------|-------|------------|---------|
| 1 | Class Name | school.class | name | e.g. 9th, 10th |
| 2 | Class Code | school.class | code | Unique code |
| 3 | Section | school.class | section | A, B, C |
| 4 | Academic Year | school.class | year | 2024-25, etc. |
| 5 | Display (Name-Section-Year) | school.class | display_name_full | Read-only display |
| 6 | Students | school.class | student_ids | Class roster |
| 7 | Subjects | school.class | subject_ids | Class ke courses |
| 8 | Class Teacher | school.class | class_teacher_id | Homeroom / main teacher |
| 9 | Timetable | school.class | timetable_ids | Schedule → Subject + Teacher |
| 10 | Capacity | school.class | capacity | Optional limit |
| 11 | Active | school.class | active | Filter |

**LMS ke liye minimum class keys:**  
`name`, `code`, `section`, `year`, `display_name_full`, `student_ids`, `subject_ids`, `class_teacher_id`, `timetable_ids`, `active`.

---

## 5. SUBJECT + TEACHER MAPPING (LMS ke liye)

**Source:** `school.timetable`  
Timetable hi batata hai: **kis class me kis subject par kaun teacher hai**.

| # | Field / Data Point | Model | Field Name | LMS Use |
|---|--------------------|-------|------------|---------|
| 1 | Class | school.timetable | class_id | Class |
| 2 | Teacher | school.timetable | teacher_id | Subject teacher |
| 3 | Subject | school.timetable | subject_id | Subject |
| 4 | Day | school.timetable | day_of_week | Schedule |
| 5 | Start Time | school.timetable | start_time | Schedule |
| 6 | End Time | school.timetable | end_time | Schedule |
| 7 | Name/Summary | school.timetable | name | Display |

**LMS ke liye:**  
“Subject details with teacher” = **timetable** se:  
`class_id` + `subject_id` + `teacher_id` (+ optional day/time).

Query example (idea):  
“Class X, Subject Y → Teacher Z” = `timetable` me `class_id`, `subject_id` filter karke `teacher_id` le sakte ho.

---

## 6. RESULT / MARKS DATA (LMS ke liye)

| # | Field / Data Point | Model | Field Name | LMS Use |
|---|--------------------|-------|------------|---------|
| 1 | Student | school.result | student_id | Kiska result |
| 2 | Class | school.result | class_id | Class |
| 3 | Exam | school.result | exam_id | Mid-term, Final, etc. |
| 4 | Roll Number | school.result | roll_number | Identity |
| 5 | Date | school.result | date | Result date |
| 6 | Subject-wise Lines | school.result | line_ids | Per-subject marks |
| 7 | Total Marks | school.result | total_marks | Computed |
| 8 | Obtained Marks | school.result | obtained_marks | Computed |
| 9 | Percentage | school.result | percentage | Computed |
| 10 | Grade | school.result | grade | A/B/C/D/F |
| 11 | Result Line – Subject | school.result.line | subject_id | Subject |
| 12 | Result Line – Obtained | school.result.line | obtained_marks | Marks |

**LMS ke liye minimum result keys:**  
`student_id`, `class_id`, `exam_id`, `line_ids` (subject_id + obtained_marks), `total_marks`, `obtained_marks`, `percentage`, `grade`, `date`.

---

## 7. EXAM DATA (LMS ke liye)

| # | Field / Data Point | Model | Field Name | LMS Use |
|---|--------------------|-------|------------|---------|
| 1 | Exam Name | school.exam | name | Mid-term, Final, etc. |

**LMS ke liye:**  
`school.exam` – sirf `name`; result me `exam_id` se link.

---

## 8. ATTENDANCE DATA (LMS ke liye)

| # | Field / Data Point | Model | Field Name | LMS Use |
|---|--------------------|-------|------------|---------|
| 1 | Student | school.attendance | student_id | Kis student ki |
| 2 | Date | school.attendance | date | Din |
| 3 | Status | school.attendance | status | present / absent / late |
| 4 | Remark | school.attendance | remark | Notes |
| 5 | State | school.attendance | state | draft / confirmed |

**LMS ke liye minimum attendance keys:**  
`student_id`, `date`, `status`, `state`.

---

## 9. STUDENT CLASS HISTORY (LMS ke liye)

| # | Field / Data Point | Model | Field Name | LMS Use |
|---|--------------------|-------|------------|---------|
| 1 | Student | school.student.class.history | student_id | Student |
| 2 | Class | school.student.class.history | class_id | Class |
| 3 | Class Name | school.student.class.history | class_name | Display |
| 4 | Section | school.student.class.history | class_section | Display |
| 5 | Academic Year | school.student.class.history | class_year | Display |
| 6 | Start Date | school.student.class.history | start_date | Session start |
| 7 | End Date | school.student.class.history | end_date | Promotion/end |
| 8 | Is Current | school.student.class.history | is_current | Current class flag |

**LMS ke liye:**  
Promotion history, “previous classes”, “current class” logic.

---

## 10. FEE (optional for LMS)

| # | Field / Data Point | Model | Field Name | LMS Use |
|---|--------------------|-------|------------|---------|
| 1 | Student | school.fee | student_id | Fee vs student |
| 2 | Class | school.fee | class_id | Class |
| 3 | Amount, Due Date, State | school.fee | amount, due_date, state | Fee status / gate for LMS |

Agar “fee clear hone par hi LMS access” doge to ye fields use karo.

---

## 11. RELATIONSHIP SUMMARY (LMS design ke liye)

```
school.student
  ├── class_id → school.class
  ├── subject_ids → school.subject (many)
  ├── partner_id → res.partner (login)
  ├── class_history_ids → school.student.class.history
  ├── attendance_ids → school.attendance
  └── fee_ids → school.fee (optional)

school.teacher
  ├── subject_ids → school.subject (many)
  └── partner_id → res.partner (login)

school.subject
  └── class_id → school.class

school.class
  ├── student_ids → school.student
  ├── subject_ids → school.subject
  ├── class_teacher_id → school.teacher
  └── timetable_ids → school.timetable

school.timetable  ← subject + teacher mapping per class
  ├── class_id → school.class
  ├── teacher_id → school.teacher
  └── subject_id → school.subject

school.result
  ├── student_id → school.student
  ├── class_id → school.class
  ├── exam_id → school.exam
  └── line_ids → school.result.line (subject_id, obtained_marks)

school.attendance
  └── student_id → school.student
```

---

## 12. LMS MODULE KE LIYE CHECKLIST

- [ ] **Student:** name, roll_number, admission_number, email, class_id, subject_ids, partner_id, state, (optional: attendance, class_history).
- [ ] **Teacher:** name, email, subject_ids, partner_id, employee_id, active.
- [ ] **Subject:** name, class_id, max_marks, description.
- [ ] **Class:** name, code, section, year, student_ids, subject_ids, class_teacher_id, timetable_ids.
- [ ] **Subject + Teacher:** timetable se (class_id, subject_id, teacher_id).
- [ ] **Result:** student_id, class_id, exam_id, line_ids (subject, marks), total, percentage, grade.
- [ ] **Exam:** name (exam_id link).
- [ ] **Attendance:** student_id, date, status.
- [ ] **Class history:** student_id, class_id, start/end date, is_current.
- [ ] **Login:** student/teacher ke liye `res.partner` / portal user (partner_id).

Agar tum chaho to isi file me “LMS-specific extra” (e.g. courses, lessons, assignments) bhi alag section me add kar sakte ho; abhi sab points current school module se nikal ke likhe hain.
