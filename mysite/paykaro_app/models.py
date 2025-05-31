from django.db import models
from decimal import Decimal


class Department(models.Model):
    dept_id=models.AutoField(primary_key=True)
    dept_name=models.CharField(max_length=15)
    def __str__(self):
        return f"{self.dept_name}"

# Create your models here.
class Employee(models.Model):
    GENDERS=[('M','Male'),('F','Female'),('O','Other')]
    emp_id=models.AutoField(primary_key=True)
    f_name=models.CharField(max_length=10)
    l_name=models.CharField(max_length=10)
    emp_pass=models.CharField(max_length=20,null=False, blank=False)
    emp_email=models.EmailField(unique=True,null=False,blank=False,default='example@email.com')
    age=models.IntegerField()
    gender=models.CharField(max_length=1,choices=GENDERS)
    city=models.CharField(max_length=10)
    sal=models.DecimalField(max_digits=10,decimal_places=2,default=0)
    dept_id=models.ForeignKey('Department',on_delete=models.SET_NULL,null=True)
    man_id=models.ForeignKey('self',on_delete=models.SET_NULL,null=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)

    def __str__(self):
        return f"{self.f_name}"



class Job(models.Model):
    job_id=models.AutoField(primary_key=True)
    job_name=models.CharField(max_length=20)
    description=models.CharField(max_length=20)
    sal_range=models.CharField(max_length=30)
    dept_id=models.ForeignKey(Department,on_delete=models.CASCADE,null=True)
    def __str__(self):
        return f"{self.job_name}"

class Salary(models.Model):
    salary_id=models.AutoField(primary_key=True)
    basic = models.DecimalField(max_digits=10, decimal_places=2, help_text="Basic salary")
    DA = models.DecimalField(max_digits=10, decimal_places=2, help_text="Dearness Allowance")
    HRA = models.DecimalField(max_digits=10, decimal_places=2, help_text="House Rent Allowance")
    bonus = models.DecimalField(max_digits=10, decimal_places=2, help_text="Bonus amount")
    income_tax = models.DecimalField(max_digits=10, decimal_places=2, help_text="Income tax deducted")
    PF = models.DecimalField(max_digits=10, decimal_places=2, help_text="Provident Fund contribution")
    health_ins = models.DecimalField(max_digits=10, decimal_places=2, help_text="Health insurance deduction",default=1000)
    emp_id = models.OneToOneField(Employee, on_delete=models.CASCADE,null=True)
    def __str__(self):
        return f"{self.salary_id}"

    def save(self, *args, **kwargs):
        # Get the actual Decimal values from the fields
        basic_value = self.basic or Decimal('0')
        bonus_value = self.bonus or Decimal('0')

        # Calculate other values
        self.DA = basic_value * Decimal('0.10')
        self.HRA = basic_value * Decimal('0.20')
        self.PF = basic_value * Decimal('0.12')

        gross = basic_value + self.DA + self.HRA + bonus_value
        self.income_tax = gross * Decimal('0.10')
        # health_ins assumed fixed at 1000

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Salary for Basic: {self.basic}"

class Payroll(models.Model):
    payroll_id=models.AutoField(primary_key=True)
    tot_amt=models.DecimalField(max_digits=15,decimal_places=2,default=0)
    report = models.FileField(upload_to='payroll_reports/', null=True, blank=True)
    date=models.DateField()
    salary_id=models.ForeignKey(Salary,on_delete=models.CASCADE,null=True)

class Leave(models.Model):
    STATUSES=[('P','Pending'),('A','Approved'),('R','Rejected')]
    leave_id=models.AutoField(primary_key=True)
    start_date=models.DateField()
    end_date=models.DateField()
    status=models.CharField(max_length=1,choices=STATUSES,default='P')
    reason=models.CharField(max_length=20,default='')
    emp_id=models.ForeignKey(Employee,on_delete=models.CASCADE,null=True,blank=True)
    payroll_id=models.ForeignKey(Payroll,on_delete=models.CASCADE,null=True)
    def __str__(self):
        return f"{self.leave_id}"

    @property
    def duration(self):
        """Calculate the duration of leave in days"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0