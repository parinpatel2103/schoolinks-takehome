
import os
import sys
from typing import Dict, Set, Tuple

import pandas as pd
from django.db import transaction
from django.utils import timezone 

#Django setup so this script can access models

#So we can run college_applications.py and applications.csv
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "schoolinks_takehome.settings")

import django
django.setup()

from core.models import District, Student, College, CollegeApplication


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """ District CSV are often inconsistent. This is to make column names more predictable"""
    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    return df

def parse_attending(value):
    """ Atttending column can be 0/1, empty, or unknown. We will convert it to True False or None
    """
    if pd.isna(value):
        return None
    
    s = str(value).strip().lower()
    if s in {"1", "true", "yes"}:
        return True
    if s in {"0", "false", "no"}:
        return False
    if s in {"unknown", "", "nan", "none"}:
        return None
    # unexpected value we just return none
    return None


def nan_to_none(value):
    #Convert pandas nan to None
    return None if pd.isna(value) else value

def get_or_create_college(ceeb: str, cname: str) -> College:
    """Gets and creates a College from a row. Prefer ceeb_code when present or else match by name when missing """

    ceeb = (ceeb or "").strip()
    cname = (cname or "").strip()

    if ceeb != "":
        college, _ = College.objects.get_or_create(
            ceeb_code = ceeb,
            defaults={"name": cname},
        )
        return college

    #If ceeb_code is missing, match by name to avoid creating duplicates
    college, _ = College.objects.get_or_create(
        name = cname,
        defaults = {"ceeb_code": ""},
    )
    return college


def import_applications_from_csv(csv_path: str) -> Dict[str, int]:
    """ Reads applications.csv and syncs the database to match the file. Returns a small summary for debugging purposes."""

    df = pd.read_csv(csv_path)
    df = clean_column_names(df)

    required_columns = {
        "student_number",
        "college_name",
        "ceeb_code",
        "application_type",
        "application_result",
        "attending",
    }

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"CSV missing required columns: {missing_columns}. Found columns: {list(df.columns)}")
    
    # Clean Strings
    df["student_number"] = df["student_number"].astype(str).str.strip()
    df["ceeb_code"] = df["ceeb_code"].fillna("").astype(str).str.strip()
    df["college_name"] = df["college_name"].fillna("").astype(str).str.strip()

    #Normalize outcomes to lowercase
    df["application_result"] = df["application_result"].fillna("").astype(str).str.strip().str.lower()

    #Just strip application types
    df["application_type"] = df["application_type"].fillna("").astype(str).str.strip()

    #Parse attending values to True Fale None
    df["attending_parsed"] = df["attending"].apply(parse_attending)



    # if ceeb_code exists use that to find college otherwise use college name
    df["college_key"] = df.apply(
        lambda r: r["ceeb_code"] if r["ceeb_code"] != "" else r["college_name"].lower(),
        axis = 1
    )

    # keep the last occurence in the csv
    df = df.drop_duplicates(subset = ["student_number", "college_key"], keep = "last")
    df = df.drop(columns=["college_key"])

    # The prompt states this CSV comes from the SchoolLinks district. The file itself doesn't include a district id,
    # so we attach imported students to a single District created for this import.
    district, _ = District.objects.get_or_create(name = "SchooLinks")

    created = 0
    archived = 0
    updated = 0

    #Track what exists in the CSV so we can archive anything missing 
    existing_applications: Set[Tuple[int, int]] = set()

    with transaction.atomic():
        for _, row in df.iterrows():
            # 1) Makes sure student exists
            student, _ = Student.objects.get_or_create(
                district = district,
                student_number = row["student_number"],
            )

            college = get_or_create_college(row["ceeb_code"], row["college_name"])

            _, created_new = CollegeApplication.objects.update_or_create(
                student = student,
                college = college,
                defaults = {
                    "application_result": row["application_result"] or None,
                    "application_type": row["application_type"] or None,
                    "attending": nan_to_none(row["attending_parsed"]),
                    "is_archived": False,
                    "archived_at": None,
                },
            )

            existing_applications.add((student.id, college.id))
            if created_new:
                created += 1
            else:
                updated += 1


        # Archive any existing application not in the CSV
        now = timezone.now()
        qs = CollegeApplication.objects.filter(student__district = district, is_archived=False).only(
            "id", "student_id", "college_id"
        )

        to_archive_ids = [
            application.id
            for application in qs
            if (application.student_id, application.college_id) not in existing_applications
        ]

        if to_archive_ids:
            archived = CollegeApplication.objects.filter(id__in = to_archive_ids).update(
                is_archived = True,
                archived_at = now,
            )
        
    
    return{
        "total_processed": len(df),
        "created": created,
        "updated": updated,
        "archived": archived,
    }

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "applications.csv"
    summary = import_applications_from_csv(path)
    print("Import Summary:", summary)
             
                