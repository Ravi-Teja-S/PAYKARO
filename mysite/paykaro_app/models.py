from django.db import models
from decimal import Decimal
from django.utils import timezone


class Department(models.Model):
    dept_id=models.AutoField(primary_key=True)
    dept_name=models.CharField(max_length=15)
    def __str__(self):
        return f"{self.dept_name}"

class Job(models.Model):
    job_id=models.AutoField(primary_key=True)
    job_name=models.CharField(max_length=20)
    description=models.CharField(max_length=20)
    sal_range=models.CharField(max_length=30)
    dept_id=models.ForeignKey(Department,on_delete=models.CASCADE,null=True)
    def __str__(self):
        return f"{self.job_name}"

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
    man_id=models.ForeignKey('self',on_delete=models.SET_NULL,null=True,blank=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True)
    def __str__(self):
        return f"{self.f_name}"





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
    PAYMENT_STATUS = [
        ('P', 'Pending'),
        ('C', 'Completed'),
        ('F', 'Failed')
    ]

    payroll_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, null=True)  # Changed from emp_id
    salary = models.ForeignKey('Salary', on_delete=models.CASCADE, null=True)  # Changed from salary_id
    
    # Payment Period
    pay_period_start = models.DateField(null=True, blank=True)
    pay_period_end = models.DateField(null=True, blank=True)
    
    # Leave Deductions
    leave_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Final Amount
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Status and Tracking
    status = models.CharField(max_length=1, choices=PAYMENT_STATUS, default='P')
    generation_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    payment_date = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey('Employee', on_delete=models.SET_NULL, 
                                   null=True, related_name='processed_payrolls')
    remarks = models.TextField(blank=True, null=True)
    report = models.FileField(upload_to='payroll_reports/', null=True, blank=True)

    class Meta:
        ordering = ['-generation_date']
        indexes = [
            models.Index(fields=['employee', 'pay_period_start', 'pay_period_end']),  # Changed from emp_id
            models.Index(fields=['status', 'generation_date']),
        ]
        unique_together = ['employee', 'pay_period_start', 'pay_period_end']  # Changed from emp_id

    # Update the calculate_net_salary method to use new field names
    def calculate_net_salary(self):
        """Calculate net salary including leave deductions"""
        salary = self.salary
        
        # Calculate leave deductions
        leaves = Leave.objects.filter(
            emp_id=self.employee,
            status='A',
            start_date__lte=self.pay_period_end,
            end_date__gte=self.pay_period_start
        )
        
        total_leave_days = 0
        for leave in leaves:
            # Calculate overlapping days
            leave_start = max(leave.start_date, self.pay_period_start)
            leave_end = min(leave.end_date, self.pay_period_end)
            leave_days = (leave_end - leave_start).days + 1
            total_leave_days += leave_days
        
        working_days = (self.pay_period_end - self.pay_period_start).days + 1
        per_day_salary = salary.basic / Decimal(working_days)
        self.leave_deduction = per_day_salary * Decimal(total_leave_days)
        
        gross = (salary.basic + salary.DA + salary.HRA + salary.bonus)
        total_deductions = (salary.PF + salary.income_tax + 
                          salary.health_ins + self.leave_deduction)
        self.net_salary = gross - total_deductions

    def __str__(self):
        return f"Payroll-{self.payroll_id} for {self.employee.f_name} {self.employee.l_name} - {self.get_payment_period_display()}"

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