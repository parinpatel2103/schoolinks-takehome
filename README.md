# SchooLinks Take-Home Challenge (Pandas + Django)

This repository contains my solutions for the SchooLinks take-home challenge. The goal of this challenge was to design Django models to gauge student competitiveness, ingest a district CSV file of college applications using Pandas, and write unit tests to verify the behavior.

---

## Repository Contents

- `core/models.py`  
  Django data models for:
  - Student competitiveness: `District`, `Student`, `College`, `StudentAcademics`, `StudentTestScore`, `ExtracurricularActivity`
  - College application data: `CollegeApplication`

- `college_applications.py`  
  CSV ingestion script using Pandas + Django ORM
  - Updates the database to match the latest CSV rather than appending new rows
  - Archives applications missing from the latest file

- `test_college_applications.py`  
  Unit tests performed using `pytest` to verify:
  - import behavior
  - handling duplicate applications
  - updates
  - archiving
  - failure cases (missing columns)

- `applications.csv`  
  Example dataset provided in the prompt.

---

## Setup & Running Locally

1) Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

2) Run migrations
python manage.py makemigrations
python manage.py migrate

3) Run the ingestion script
python college_applications.py applications.csv

4) Run tests
pytest -q

---


## Task 1: Django Data Model Design

To understand student competitiveness, I focused on data points that colleges typically look at during admissions and that districts can realistically collect.

### Models added

#### StudentAcademics
- Stores GPA, GPA scale, rank, class size, and a count of advanced courses  
- GPA scale is stored because districts may have weighted vs unweighted GPAs and use different scales based on advanced courses such as IB, AP, or Honors (4.0 vs 5.0)

#### StudentTestScore
- Stores scores for the most common standardized tests (SAT/ACT), allowing multiple attempts to be recorded for each student over time  
- Allows selecting a student's highest score, most recent score, or combining best section scores across multiple test attempts

#### ExtracurricularActivity
- Stores activity name, role, years, and hours/week  
- Includes a simple `in_leadership` flag to identify leadership involvement without assigning subjective scores

---

## Task 2: Data Ingestion with Pandas (`applications.csv`)

### The CSV columns used
- `student_number`
- `ceeb_code`
- `college_name`
- `application_result`
- `application_type`
- `attending`

### Approach

My script does the following:

1. **Reads the CSV file**
   - Uses Pandas to load the CSV so it's easy to work with

2. **Cleans and standardizes the data**
   - Standardizes column names (lowercase, stripped)
   - Strips extra whitespace from key string fields
   - Normalizes `application_result` to lowercase
   - Parses `attending` into `True`, `False`, or `None` to handle `0/1`, `"unknown"`, and blanks

3. **Handles duplicate rows**
   - Keeps the last occurrence if the CSV contains multiple rows for the same student and college
   - Uses `ceeb_code` when available, otherwise falls back to a case-insensitive college name match

4. **Syncs the data into the database**
   - Creates or retrieves the `District` (assumed to be SchooLinks since district info is not in the file)
   - Creates or retrieves the related `Student` and `College`
   - Uses `update_or_create` on `CollegeApplication` to update existing records instead of duplicating them

5. **Archives applications missing from the latest file**
   - Any existing application not present in the new CSV is archived with:
     - `is_archived = True`
     - `archived_at = <timestamp>`

---

## Task 3: Unit Tests

Tests are written in `test_college_applications.py` using `pytest`.

### Tests verify:
- New records are created correctly when importing a new CSV
- Duplicate rows keep the most recent entry
- Re-importing the same application updates the existing record instead of creating duplicates
- Applications missing from the latest file are properly archived
- The script fails early with a clear error when required columns are missing

---

## Assumptions

- The CSV does not include a district identifier. Since the prompt specifies that this file comes from the SchooLinks district, all imported students are attached to a single `District` record created as `"SchooLinks"`.

- `ceeb_code` is stored as a string rather than a numeric field because the provided dataset includes non-numeric values (e.g., `CC4220`, `MC2081`, `1324A`, `7775UK`), even though CEEB codes are sometimes described as 4-digit identifiers.

- A student can have at most one active application per college in this simplified model. If multiple rows exist for the same student and college, the most recent row in the CSV is treated as the current state (`unique_together = (student, college)`).

- The `attending` field can be unknown in the source data, so it is stored as a boolean (`True`, `False`, or `None`) to accurately represent `1`, `0`, `"unknown"`, or missing values.

---

## Known Limitations / Improvements

This solution uses a simplified model focused on clarity within the scope of the take-home challenge. If this were extended beyond the assignment, there are a few areas I would improve.

### Performance for very large districts
- The ingestion script processes each row individually using Django’s ORM. This works for the dataset size here, but for much larger CSVs I would look into bulk inserts/updates to reduce database overhead.

### College matching edge cases
- Colleges are matched by `ceeb_code` when available, otherwise matched by college name. This works for the provided data, but in a real system I would want better handling for cases where identifiers are missing, inconsistent, or misspelled.

### Messy or unexpected values
- Fields like `attending` and `application_result` are normalized, but unexpected values are currently set to `None`. In a production setting, I would add logging so these cases can be reviewed instead of silently ignored.

### Import tracking
- The script currently returns a summary of created, updated, and archived records. If this were productionized, I would store basic import metadata (such as timestamps and row counts) to make debugging and audits easier.

---

## Task 4: College Classification

### 1) What data points would I use?

#### Student-side (competitiveness signals)

I’d focus on things that are both common in admissions and realistically available from districts:

**Academics**
- GPA + scale (weighted/unweighted, 4.0 vs 5.0)
- Class rank percentile (rank / class size)
- Course rigor (number of AP/IB/Honors)

**Testing**
- SAT/ACT best score

**Activities**
- Basic time commitment (hours/week, years involved)
- Leadership involvement for added context

#### College-side

**Baseline selectivity**
- Admit rate / acceptance rate (from public sources when available)
- Typical test score ranges (if reported publicly)

**Platform past outcomes (SchooLinks data)**
- Past acceptance/denial outcomes for students who applied to the same college
- Comparison of students with similar academic profiles when enough data exists
- Additional context from district-level outcomes when available

#### Additional sources I’d consider

**IPEDS (Integrated Postsecondary Education Data System)**  
Used mainly for high-level baseline information such as admit rates and enrollment size.

**Common Data Set (when available)**  
Used to understand how colleges weigh factors like GPA and test scores when that information is published.

**Internal research or curated datasets**  
Used to standardize and maintain college-level metadata before it’s used for classification.