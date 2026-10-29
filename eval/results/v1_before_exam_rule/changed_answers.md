# Answers that changed

## Between repeated runs of the same configuration

### P11 (multi-agent, llama3.1-8b): How many total credits are required for a B.Tech. degree?

- **run1** (wrong): The total credits required for a B.Tech. degree are not explicitly mentioned in the passages provided. However, it can be inferred that students need to complete a certain number of credits to earn their degree. According to the passage from "Academic_Regulations_Final_03_09_2019.pdf", students are allowed to overload only when they need 70 or less additional credits to complete all the requirements of their programme. This suggests that there is a minimum credit requirement for the B.Tech. degree, but it is not explicitly stated. Similarly, the passage from "Circular_29_Guideline for B.Tech. 
- **run2** (wrong): The total credits required for a B.Tech. degree is not explicitly mentioned in the provided passages. However, it can be inferred that students need to complete a certain number of credits to earn their degree. According to the passage from "Circular_29_Guideline for B.Tech. in Engineering Science programmes.pdf", page 1, students can use 10 credits out of stipulated electives and 10 additional credits to earn minor/specialization as an add-on to the B.Tech degree. However, this does not provide a total credit requirement. The passage from "Academic_Regulations_Final_03_09_2019.pdf", page 17, 

### P13 (multi-agent, llama3.1-8b): If a student withdraws from a minor, what happens to the credits already earned in it?

- **run1** (wrong): According to the Academic Regulations Final 03 09 2019.pdf, page 35, if a student withdraws from a minor, the credits already earned in it are retained. The document states that "The withdrawn course will be mentioned in the Student's grade card with a letter grade 'W'." Source: Academic_Regulations_Final_03_09_2019.pdf, page 35
- **run2** (correct): If a student withdraws from a minor, the credits already earned in it will be considered in the Open Elective category for the purpose of degree requirements. Source: 2799_Circular_UG Specilization and Minors 27 March 2023.pdf, page 1

### P14 (multi-agent, llama3.1-8b): How early should students be seated in the examination hall for the Minor examinations of Semester I, 2026-27?

- **run1** (wrong): Students should be seated in the examination hall at least 30 minutes before the scheduled start time of their Minor examinations. Source: AY 2026-27 Semester-I Slot System (B.Tech. 1st Year).xlsx, page sheet Examination
- **run2** (wrong): Based on the passages, it is not explicitly mentioned when students should be seated in the examination hall for the Minor examinations of Semester I, 2026-27. However, according to the guidelines for the Minor Examination Semester I of Academic Year 2026-27, the Institute follows a zero-tolerance policy towards any form of malpractice or misconduct during examinations. Source: AY 2026-27 Semester-I Slot System (B.Tech. 1st Year).xlsx, page sheet Examination Indian Institute of Technology Jodhpur Mail - Guidelines for the Minor Examination Semester I of Academic Year 2026-27.pdf, page 1

### P01 (multi-agent, llama3.2-3b): What is the attendance requirement to sit in the Major exam?

- **run1** (wrong): Source: 7.1_Circular_51Circular-No.-IITJOAACircular2024-2551682-dated-08-July-2024.pdf, page 1 and Academic_Regulations_Final_03_09_2019.pdf, page 26 According to the circular, there is no specific attendance requirement mentioned for the Major exam. However, it is mentioned that a student should have full attendance in each course unless they take a leave of absence. Source: 7.1_Circular_51Circular-No.-IITJOAACircular2024-2551682-dated-08-July-2024.pdf, page 1 and Academic_Regulations_Final_03_09_2019.pdf, page 26
- **run2** (wrong): Source: 7.1_Circular_51Circular-No.-IITJOAACircular2024-2551682-dated-08-July-2024.pdf, page 1 and Academic_Regulations_Final_03_09_2019.pdf, page 26. The attendance requirement for the Major exam at IIT Jodhpur is not explicitly mentioned in the provided passages. However, according to Academic_Regulations_Final_03_09_2019.pdf, page 26, a minimum of 60% marks for GEN/OBC (55% for SC/ST) category in aggregate or a minimum CGPA of 6.0 for GEN/OBC (5.5 for SC/ST) category is required on the scale of 10. I don't know - the available documents do not contain this information. Your question has bee

### P14 (multi-agent, llama3.2-3b): How early should students be seated in the examination hall for the Minor examinations of Semester I, 2026-27?

- **run1** (wrong): Students should arrive at least 30 minutes before the scheduled start time of their Minor examination to ensure they can take their seat in time. Source: Indian Institute of Technology Jodhpur Mail - Guidelines for the Minor Examination Semester I of Academic Year 2026-27.pdf, page 1
- **run2** (wrong): To determine the seating time for Minor examinations of Semester I, 2026-27, students should arrive at least 30 minutes before the scheduled examination time. According to the tentative timetable for Minor Examinations (Semester-I of Academic Year 2026-27), the timings are as follows: * 08:00 AM to 10:00 AM * 10:30 AM to 12:30 PM * 02:00 PM to 04:00 PM * 04:30 PM to 06:30 PM * 07:00 PM to 09:00 PM It is recommended that students arrive at least 30 minutes before the scheduled examination time to allow for check-in and seating arrangements. Source: AY 2026-27 Semester-I Slot System (B.Tech. 1st

### S04 (multi-agent, llama3.2-3b): When is the minor examination for slot K courses?

- **run1** (wrong): I don't know - the available documents do not contain this information. Your question has been logged so that a human can answer it. Source: search_documents
- **run2** (correct): Slot K classes: Mon 8:00-8:50, Wed 8:00-8:50, Fri 8:00-8:50. Minor examination for slot K: 17 September 2026, Thursday, 02:00 PM to 04:00 PM (tentative). Source: AY 2026-27_Semester I_Slot System (2nd Year onwards).xlsx (sheet: Examination); AY 2026-27_Semester I_Slot System (2nd Year onwards).xlsx (sheet: Slot System)

## When the LLM was replaced

### P01 (multi-agent): What is the attendance requirement to sit in the Major exam?

- **llama3.1-8b** (correct, policy_agent): According to the revised policy (Circular No.-IITJOAACircular2024-2551682-dated-08-July-2024, page 1), a student is expected to have full attendance in each course unless they take a leave of absence for valid medical or bonafide reasons. In any case, the attendance of a student should not fall below 75% in a course. Source: 7.1_Circular_51Circular-No.-IITJOAACircular2024-2551682-dated-08-July-2024.pdf, page 1
- **llama3.2-3b** (wrong, policy_agent): Source: 7.1_Circular_51Circular-No.-IITJOAACircular2024-2551682-dated-08-July-2024.pdf, page 1 and Academic_Regulations_Final_03_09_2019.pdf, page 26 According to the circular, there is no specific attendance requirement mentioned for the Major exam. However, it is mentioned that a student should have full attendance in each course unless they take a leave of absence. Source: 7.1_Circular_51Circular-No.-IITJOAACircular2024-2551682-dated-08-July-2024.pdf, page 1 and Academic_Regulations_Final_03_09_2019.pdf, page 26

### P02 (multi-agent): How many Open Elective credits do I need to earn in order to get a B.Tech. Degree?

- **llama3.1-8b** (wrong, policy_agent): To get a B.Tech. Degree, you need to earn 160 credits in total. Source: Circular_29_Guideline for B.Tech. in Engineering Science programmes.pdf, page 1 and Academic_Regulations_Final_03_09_2019.pdf, page 17
- **llama3.2-3b** (correct, policy_agent): To earn a B.Tech. Degree, you need to earn 10 credits out of stipulated electives and 10 additional credits. Source: Circular_29_Guideline for B.Tech. in Engineering Science programmes.pdf, page 1

### P03 (multi-agent): What is the fine if a student does not register by the registration date given in the academic calendar?

- **llama3.1-8b** (correct, policy_agent): If a student does not register by the registration date given in the academic calendar, they can register by paying a fine of Rs. 1,500. Source: Circular_2283 (1).pdf, page 1 and Academic_Regulations_Final_03_09_2019.pdf, page 3
- **llama3.2-3b** (wrong, policy_agent): If a student does not register by the registration date given in the academic calendar, they will be deregistered and may be permitted to continue their registration on payment of an appropriate fine, which is Rs. 10,000. Source: Circular_2283 (1).pdf, page 1; Academic_Regulations_Final_03_09_2019.pdf, page 3

### P11 (multi-agent): How many total credits are required for a B.Tech. degree?

- **llama3.1-8b** (wrong, policy_agent): The total credits required for a B.Tech. degree are not explicitly mentioned in the passages provided. However, it can be inferred that students need to complete a certain number of credits to earn their degree. According to the passage from "Academic_Regulations_Final_03_09_2019.pdf", students are allowed to overload only when they need 70 or less additional credits to complete all the requirements of their programme. This suggests that there is a minimum credit requirement for the B.Tech. degree, but it is not explicitly stated. Similarly, the passage from "Circular_29_Guideline for B.Tech. 
- **llama3.2-3b** (wrong, policy_agent): The total credits required for a B.Tech degree at IIT Jodhpur is not explicitly stated in the passages provided. However, it is mentioned that students can use 10 credits out of stipulated electives and 10 additional credits to earn minor/interdisciplinary specializations or department area specializations. Source: Engineering Science _ Office of Academics Affairs _ IIT Jodhpur.pdf, page 2 Circular_29_Guideline for B.Tech. in Engineering Science programmes.pdf, page 1 Academic_Regulations_Final_03_09_2019.pdf, page 14 Circular 31_4-year B.Tech. in X + Engineering Science for B.Tech. students j

### P13 (multi-agent): If a student withdraws from a minor, what happens to the credits already earned in it?

- **llama3.1-8b** (wrong, policy_agent): According to the Academic Regulations Final 03 09 2019.pdf, page 35, if a student withdraws from a minor, the credits already earned in it are retained. The document states that "The withdrawn course will be mentioned in the Student's grade card with a letter grade 'W'." Source: Academic_Regulations_Final_03_09_2019.pdf, page 35
- **llama3.2-3b** (correct, policy_agent): If a student withdraws from a minor, the credits already earned in it will be considered in the Open Elective category for the purpose of degree requirements. Source: 28_Credit_Revision 11 Jan 2024.pdf, page 1 and 2799_Circular_UG Specilization and Minors 27 March 2023.pdf, page 4

### P14 (multi-agent): How early should students be seated in the examination hall for the Minor examinations of Semester I, 2026-27?

- **llama3.1-8b** (wrong, policy_agent): Students should be seated in the examination hall at least 30 minutes before the scheduled start time of their Minor examinations. Source: AY 2026-27 Semester-I Slot System (B.Tech. 1st Year).xlsx, page sheet Examination
- **llama3.2-3b** (wrong, schedule_agent): Students should arrive at least 30 minutes before the scheduled start time of their Minor examination to ensure they can take their seat in time. Source: Indian Institute of Technology Jodhpur Mail - Guidelines for the Minor Examination Semester I of Academic Year 2026-27.pdf, page 1

### S03 (multi-agent): Who is teaching Database Systems this semester, and in which slot?

- **llama3.1-8b** (wrong, schedule_agent): CSL7650 Autonomous Systems: slot E (Tue 11:00-11:50, Thu 11:00-11:50, Fri 11:00-11:50); instructor Gaurav Harit; 3 credits (L-T-P 3-0-0); classroom LHC 106; minor exam 18 September 2026, Friday, 08:00 AM to 10:00 AM (tentative). Source: AY 2026-27_Semester I_Slot System (2nd Year onwards).xlsx (sheet: Classroom Allocation); AY 2026-27_Semester I_Slot System (2nd Year onwards).xlsx (sheet: Examination); AY 2026-27_Semester I_Slot System (2nd Year onwards).xlsx (sheet: Slot System)
- **llama3.2-3b** (correct, schedule_agent): CSL3050 Database Systems: slot A (Mon 9:00-9:50, Tue 9:00-9:50, Thu 9:00-9:50); instructor Awathare Nitin Niranjan; 4 credits (L-T-P 3-0-2); classroom LHC 2 101; minor exam 19 September 2026, Saturday, 08:00 AM to 10:00 AM (tentative). Source: AY 2026-27_Semester I_Slot System (2nd Year onwards).xlsx (sheet: Classroom Allocation); AY 2026-27_Semester I_Slot System (2nd Year onwards).xlsx (sheet: Examination); AY 2026-27_Semester I_Slot System (2nd Year onwards).xlsx (sheet: Slot System)

### S04 (multi-agent): When is the minor examination for slot K courses?

- **llama3.1-8b** (correct, schedule_agent): Slot K classes: Mon 8:00-8:50, Wed 8:00-8:50, Fri 8:00-8:50. Minor examination for slot K: 17 September 2026, Thursday, 02:00 PM to 04:00 PM (tentative). Source: AY 2026-27_Semester I_Slot System (2nd Year onwards).xlsx (sheet: Examination); AY 2026-27_Semester I_Slot System (2nd Year onwards).xlsx (sheet: Slot System)
- **llama3.2-3b** (wrong, schedule_agent): I don't know - the available documents do not contain this information. Your question has been logged so that a human can answer it. Source: search_documents