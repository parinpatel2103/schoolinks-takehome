from django.db import models


class District(models.Model):
    """ Model to store school districts and their relevant information."""
    name = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.name


class Student(models.Model):
    """ Model to store students and their relevant information."""
    student_number = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    district = models.ForeignKey(District, related_name="students", on_delete=models.CASCADE)
    
    def __str__(self) -> str:
        return f"{self.district.name} - {self.student_number}"
    
    
class College(models.Model):
    """Model to store colleges and their relevant information."""
    name = models.CharField(max_length=128)
    ceeb_code = models.CharField(max_length=255, default="", blank=True, db_index=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.ceeb_code})"


class StudentAcademics(models.Model):
    """ Stores core academic information that colleges commonly evaluate."""
    student = models.OneToOneField(Student, related_name="academic_profile", on_delete=models.CASCADE)
    graduation_year = models.IntegerField(null=True, blank=True)

    #GPA formats vary by school( weight vs unweighted, 4.0 vs 5.0 scale), so we store the scale as well.
    gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    gpa_scale = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    class_rank = models.IntegerField(null=True, blank=True)
    class_size = models.IntegerField(null=True, blank=True)

    #Using a count to keep things consistent since districts label advanced courses differently.
    num_advanced_courses = models.IntegerField(null=True, blank=True)

    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Academics for {self.student}"


class StudentTestScore(models.Model):
    """ Students may take the SAT or ACT multiple times, so we store each test date and score separately. This makes it easy later to analyze scores"""
   
    EXAM_TYPE_CHOICES =[
        ("SAT", "SAT"),
        ("ACT", "ACT"),
    ]
    student = models.ForeignKey(Student, related_name="test_scores", on_delete=models.CASCADE)
    exam_type = models.CharField(max_length=8, choices=EXAM_TYPE_CHOICES)

    overall_score = models.IntegerField(null=True, blank=True)

    test_date = models.DateField(null=True, blank=True)

    math_score = models.IntegerField(null=True, blank=True)
    english_reading_score = models.IntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.exam_type} score for {self.student}"

    


class ExtracurricularActivity(models.Model):
    """Activities that students participate in outside of academics. These activities show initiative and leadership skills that colleges value. """

    student = models.ForeignKey(Student, related_name="activities", on_delete=models.CASCADE)

    name = models.CharField(max_length=128)
    role = models.CharField(max_length=128, null=True, blank=True) 
    years_participated = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    hours_per_week = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)

    in_leadership = models.BooleanField(default=False)

    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.student})"
    
class CollegeApplication(models.Model):
    """Stores a student's application to a college. We have to archive missing rows """

    student = models.ForeignKey(Student, related_name="applications", on_delete=models.CASCADE)
    college = models.ForeignKey(College, related_name="applications", on_delete=models.CASCADE)

    application_result = models.CharField(max_length=64, null=True, blank=True)
    application_type = models.CharField(max_length=64, null=True, blank=True)
    attending = models.BooleanField(null=True, blank=True)

    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        #We store one current application record per student per college
        #If the CSV contains duplicates, the ingestion script will dedulicates before inserting
        unique_together = ("student", "college")
        indexes = [
            models.Index(fields=["student","is_archived"]),
        ]

    def __str__(self) -> str:
        return f"{self.student.student_number} -> {self.college.name}"
    