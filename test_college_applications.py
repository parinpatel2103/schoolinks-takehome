

import pandas as pd
import pytest

from college_applications import import_applications_from_csv
from core.models import CollegeApplication, District, Student

def _write_test_csv(tmp_path, rows, filename = "applications.csv"):
    """ Helper to write a list of dict rows into a CSV file for tests to make the tests easier to read."""
    df = pd.DataFrame(rows)
    path = tmp_path / filename
    df.to_csv(path, index=False)
    return str(path)


# Test 1 - Import creates new records

@pytest.mark.django_db
def test_import_creates_newapps(tmp_path):
    """ If the database is empty, the import should create new records matching the CSV file( District, Student, College, CollegeApplication)
        Also checks attending parsing ( 1/0/unknown to True/False/None)
    """
    rows = [
            {
                "student_number": "974228",
                "ceeb_code": "2295",
                "college_name": "Stonehill College",
                "application_result": "accepted",
                "application_type": "Early Action",
                "attending": "1",
            },
            {
                "student_number": "996713",                        
                "ceeb_code": "",                                   
                "college_name": "Lasell University",               
                "application_result": "",
                "application_type": "Rolling Decision",
                "attending": "0"
            },
            {
                "student_number": "974424",
                "ceeb_code": "3771",
                "college_name": "Suffolk University",
                "application_result": "accepted",
                "application_type": "Rolling",
                "attending": "unknown",    
            },
        ]
    
    csv_path = _write_test_csv(tmp_path, rows, filename=  "applications.csv")
    summary = import_applications_from_csv(csv_path)

    assert summary["total_processed"] == 3
    assert summary["created"] == 3
    assert summary["updated"] == 0
    assert summary["archived"] == 0

    assert District.objects.filter(name = "SchooLinks").exists()
    assert Student.objects.count() == 3
    assert CollegeApplication.objects.count() == 3

    application_true = CollegeApplication.objects.get(student__student_number="974228")
    assert application_true.attending is True

    application_false = CollegeApplication.objects.get(student__student_number="996713")
    assert application_false.attending is False

    application_none = CollegeApplication.objects.get(student__student_number="974424")
    assert application_none.attending is None



#Test 2 - Import deduplicates rows and keeps last occurence

@pytest.mark.django_db
def test_import_keeps_latest_application_for_duplicates(tmp_path):
    """
    If the CSV includes duplicates for the same student and college, we should only keep the last occurence in the file.
    1. Duplicates with ceeb_code
    2. Duplicates without ceeb_code ( matching by college name, case insensitive)
    """
    rows = [
        #Second row should win, duplicate with ceeb_code
        {
            "student_number": "974472",        
            "ceeb_code": "3771",               
            "college_name": "Suffolk University",   
            "application_result": "denied",
            "application_type": "Early Action",
            "attending": "0",
        },
        {
            "student_number": "974472",       
            "ceeb_code": "3771",                
            "college_name": "Suffolk University",
            "application_result": "accepted",   
            "application_type": "Early Action",
            "attending": "1",
        },
        #Duplicate by name, second row should win
        {
            "student_number": "974195",             
            "ceeb_code": "",
            "college_name": "Quinnipiac University",  
            "application_result": "",
            "application_type": "Rolling Decision",
            "attending": "unknown",
        },
        {
            "student_number": "974195",
            "ceeb_code": "",
            "college_name": "quinnipiac university",  # same name different case
            "application_result": "accepted",
            "application_type": "Rolling Decision",
            "attending": "1",
        }
    ]
    

    csv_path = _write_test_csv(tmp_path, rows, filename = "applications_duplicates.csv")
    summary = import_applications_from_csv(csv_path)
   
    assert summary["total_processed"] == 2
    assert CollegeApplication.objects.count() == 2

    application_1 = CollegeApplication.objects.get(student__student_number = "974472")
    assert application_1.application_result == "accepted"
    assert application_1.attending is True

    application_2 = CollegeApplication.objects.get(student__student_number = "974195")
    assert application_2.application_result == "accepted"
    assert application_2.attending is True



#Test 3 - Import updates existing records

@pytest.mark.django_db
def test_import_updates_existing_record(tmp_path):
    """ Reimporting a CSV with an existing student and college should update the existing record not create a new one."""
    # First import
    csv1 = _write_test_csv( 
        tmp_path,
        [
            {
                "student_number": "974228",     
                "ceeb_code": "3780",            
                "college_name": "Sacred Heart University",
                "application_result": "unknown",
                "application_type": "Early Action",
                "attending": "unknown",
            }
        ],
        filename = "application_initial.csv",
    )

    summary1 = import_applications_from_csv(csv1)
    assert summary1["created"] == 1
    assert summary1["updated"] == 0

    # Second import updates same record
    csv2 = _write_test_csv(
        tmp_path,
        [
            {
                "student_number": "974228",     
                "ceeb_code": "3780",            
                "college_name": "Sacred Heart University",
                "application_result": "accepted",
                "application_type": "Early Action",
                "attending": "1",
            }
        ],
        filename = "application_update.csv",
    )

    summary2 = import_applications_from_csv(csv2)
    assert summary2["created"] == 0
    assert summary2["updated"] == 1
    assert CollegeApplication.objects.count() == 1

    app = CollegeApplication.objects.get(student__student_number = "974228")
    assert app.application_result == "accepted"
    assert app.attending is True
    assert app.is_archived is False



# Test 4 - Archiving missing records

@pytest.mark.django_db
def test_import_archives_rows_missing_from_latest_file(tmp_path):
    """ Any application not present in the latest file should be archived."""
    # Import with two applications
    csv_full = _write_test_csv(
        tmp_path,
        [
            {
                "student_number": "974150",     
                "ceeb_code": "3369",            
                "college_name": "Endicott College",
                "application_result": "accepted",
                "application_type": "Rolling Decision",
                "attending": "0",
            },
            {
                "student_number": "975900",     
                "ceeb_code": "2400",            
                "college_name": "Marist College",
                "application_result": "accepted",
                "application_type": "Early Action",
                "attending": "1",
            },
        ],
        filename = "application_full.csv",
    )

    import_applications_from_csv(csv_full)
    assert CollegeApplication.objects.filter(is_archived=False).count() == 2

    # Next day's file contains only one of them
    csv_partial = _write_test_csv(
        tmp_path,
        [
            {
                "student_number": "974150",     
                "ceeb_code": "3369",            
                "college_name": "Endicott College",
                "application_result": "accepted",
                "application_type": "Rolling Decision",
                "attending": "0",
            }
        ],
        filename = "application_partial.csv",
    )

    summary = import_applications_from_csv(csv_partial)
    assert summary["archived"] == 1

    assert CollegeApplication.objects.filter(is_archived=False).count() == 1
    assert CollegeApplication.objects.filter(is_archived=True).count() == 1

    archived_app = CollegeApplication.objects.get(student__student_number = "975900")
    assert archived_app.is_archived is True
    assert archived_app.archived_at is not None

# Test 5 - Test missing Columns 

@pytest.mark.django_db
def test_missing_columns(tmp_path):
    """
    Edge case: district sends a disorganized CSV that's missing required columns.
    We should fail fast with an Error instead of continuting to do the wrong thing.
    """
    rows = [
        {
            "student_number": "1",
            # ceeb_code missing
            "college_name": "Test College",
            "application_result": "accepted",
            "application_type": "Rolling",
            "attending": "1",
        },
    ]
    csv_path = _write_test_csv(tmp_path, rows, filename = "bad.csv")


    with pytest.raises(ValueError) as exc:
        import_applications_from_csv(csv_path)
    assert "ceeb_code" in str(exc.value)
