import calendar
import csv
import json
import os
import mimetypes
# Make sure the path to your models is correct
from decimal import Decimal, InvalidOperation
from io import BytesIO
from functools import wraps
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import models
from django.http import HttpResponse , JsonResponse ,FileResponse , Http404
from django.shortcuts import redirect
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from .forms import EmployeeSignupForm
from .forms import ProfilePhotoForm
from .models import Employee, Leave, Salary, Payroll

from PIL import Image, UnidentifiedImageError

def serve_media(request, path):
    full_path = os.path.join(settings.MEDIA_ROOT, path)

    if not os.path.isfile(full_path):
        raise Http404("Media file not found.")

    try:
        # Validate image integrity before serving (optional but powerful)
        with open(full_path, 'rb') as f:
            try:
                Image.open(f).verify()
            except UnidentifiedImageError:
                print(f"Corrupted image: {full_path}")
                raise Http404("Invalid image file.")

        return FileResponse(open(full_path, 'rb'))
    except Exception as e:
        print(f"Error serving media: {e}")
        raise Http404("Cannot open media file.")

        
def generate_pdf_payroll(payroll_records, department, year, month):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50,
        title=repr(f'Payroll Report - {department.dept_name}')
    )

    styles = getSampleStyleSheet()

    # Define styles with default Times-Roman and Helvetica fonts
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1,
        textColor=colors.HexColor('#1e40af'),
        leading=32,
        fontName='Helvetica-Bold'
    )

    heading_style = ParagraphStyle(
        'EmployeeHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1e40af'),
        spaceBefore=20,
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )

    label_style = ParagraphStyle(
        'LabelStyle',
        parent=styles['Normal'],
        fontSize=11,
        spaceBefore=6,
        fontName='Times-Roman'
    )

    amount_style = ParagraphStyle(
        'AmountStyle',
        parent=styles['Normal'],
        fontSize=11,
        spaceBefore=6,
        alignment=2,  # Right alignment
        fontName='Helvetica'
    )

    elements = []

    # Title section with company logo and report details
    title_text = (
        '<para align="center">'
        '<b>PayKaro - Payroll Report</b><br/>'
        f'<font size="14">{department.dept_name} Department</font><br/>'
        f'<font size="12">Period: {calendar.month_name[month]} {year}</font>'
        '</para>'
    )
    elements.append(Paragraph(title_text, title_style))
    elements.append(Spacer(1, 20))

    def format_currency(amount):
        """Format currency with thousand separators and proper decimal places"""
        try:
            amount = float(amount)
            if amount.is_integer():
                return f"INR {int(amount):,}"
            return f"INR {amount:,.2f}"
        except (ValueError, TypeError):
            return f"INR {amount}"

    # Employee records
    for record in payroll_records:
        # Employee name as heading
        elements.append(Paragraph(f"Employee: {record['employee_name']}", heading_style))

        # Salary components
        salary_items = [
            ("Basic Salary", format_currency(record['basic'])),
            ("Dearness Allowance (DA)", format_currency(record['da'])),
            ("House Rent Allowance (HRA)", format_currency(record['hra'])),
            ("Bonus", format_currency(record['bonus'])),
            ("Provident Fund (PF)", format_currency(record['pf'])),
            ("Income Tax", format_currency(record['tax'])),
            ("Health Insurance", format_currency(record['health_ins'])),
            ("Leave Deduction", format_currency(record['leave_deduction']))
        ]

        # Create earnings and deductions sections
        for label, value in salary_items:
            data = [[Paragraph(label, label_style), Paragraph(value, amount_style)]]
            t = Table(data, colWidths=[350, 150], rowHeights=25)
            t.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(t)

        # Net Salary (highlighted)
        elements.append(Spacer(1, 10))
        net_salary_data = [[
            Paragraph("<b>Net Salary</b>", label_style),
            Paragraph(f"<b>{format_currency(record['net_salary'])}</b>", amount_style)
        ]]
        net_salary_table = Table(net_salary_data, colWidths=[350, 150], rowHeights=30)
        net_salary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ]))
        elements.append(net_salary_table)

        # Separator between employees
        elements.append(Spacer(1, 30))

    # Footer with generation timestamp and page number
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.gray,
        alignment=1,
        fontName='Helvetica'
    )

    footer_text = (
        f'Generated on: {timezone.now().strftime("%d %B %Y, %H:%M")}<br/>'
        'This is a computer-generated document. No signature is required.'
    )
    elements.append(Paragraph(footer_text, footer_style))

    # Build PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def manager_login_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.session.get('emp_id') or request.session.get('role') != 'manager':
            return redirect('manager_login')
        return view_func(request, *args, **kwargs)
    return wrapped

def manager_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            emp = Employee.objects.get(emp_email=email, emp_pass=password)
            # Check if this employee is a manager by seeing if any employees report to them
            if emp.role== 'manager':
                request.session['emp_id'] = emp.emp_id
                request.session['role'] = 'manager'
                return redirect('manager_dashboard')
            else:
                messages.error(request, 'This user is not a manager.')
        except Employee.DoesNotExist:
            messages.error(request, 'Invalid credentials.')
    return render(request, 'paykaro_app/manager_login.html')


def employee_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            emp = Employee.objects.get(emp_email=email, emp_pass=password)

            if emp.role=='employee':
                request.session['emp_id'] = emp.emp_id
                request.session['role'] = 'employee'
                return redirect('employee_dashboard')
            else:
                messages.error(request, 'This user is a manager. Please use manager login.')

        except Employee.DoesNotExist:
            messages.error(request, 'Invalid credentials.')
    return render(request, 'paykaro_app/employee_login.html')

def employee_login_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.session.get('emp_id') or request.session.get('role') != 'employee':
            return redirect('employee_login')
        return view_func(request, *args, **kwargs)
    return wrapped

# paykaro_app/views.py
@manager_login_required
def view_department_employees(request):
    if request.session.get('role') != 'manager':
        return redirect('manager_login')

    manager_id = request.session.get('emp_id')
    try:
        manager = Employee.objects.get(emp_id=manager_id)
        department = manager.dept_id
        employees = Employee.objects.filter(dept_id=department)

        # Calculate additional statistics
        total_employees = employees.exclude(emp_id=manager_id).count()
        gender_distribution = {
            'Male': employees.filter(gender='M').exclude(emp_id=manager_id).count(),
            'Female': employees.filter(gender='F').exclude(emp_id=manager_id).count(),
            'Other': employees.filter(gender='O').exclude(emp_id=manager_id).count(),
        }

        # Calculate average salary
        avg_salary = employees.exclude(emp_id=manager_id).aggregate(
            avg_salary=models.Avg('sal')
        )['avg_salary'] or 0

        # Get active leaves count
        active_leaves = Leave.objects.filter(
            emp_id__dept_id=department,
            status='A',
            end_date__gte=timezone.now().date()
        ).count()

        # Get employees on leave today
        employees_on_leave = Leave.objects.filter(
            emp_id__dept_id=department,
            status='A',
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        ).select_related('emp_id')

        context = {
            'department': department,
            'manager': manager,
            'total_employees': total_employees,
            'gender_distribution': gender_distribution,
            'avg_salary': avg_salary,
            'active_leaves': active_leaves,
            'employees_on_leave': employees_on_leave,
            'employees': employees,
        }

        return render(request, 'paykaro_app/department_employees.html', context)

    except Employee.DoesNotExist:
        messages.error(request, 'Manager not found.')
        return redirect('manager_login')



@manager_login_required
def manage_employees(request):
    manager_id = request.session.get('emp_id')
    try:
        manager = Employee.objects.get(emp_id=manager_id)
        department = manager.dept_id
        employees = Employee.objects.filter(dept_id=department).exclude(emp_id=manager_id)

        # Handle search and filters
        search_query = request.GET.get('search', '')
        gender_filter = request.GET.get('gender', '')
        min_age = request.GET.get('min_age', '')
        max_age = request.GET.get('max_age', '')
        min_salary = request.GET.get('min_salary', '')
        max_salary = request.GET.get('max_salary', '')

        if search_query:
            employees = employees.filter(
                models.Q(f_name__icontains=search_query) |
                models.Q(l_name__icontains=search_query) |
                models.Q(emp_email__icontains=search_query) |
                models.Q(city__icontains=search_query)
            )

        if gender_filter:
            employees = employees.filter(gender=gender_filter)

        if min_age:
            employees = employees.filter(age__gte=min_age)
        if max_age:
            employees = employees.filter(age__lte=max_age)

        if min_salary:
            employees = employees.filter(sal__gte=min_salary)
        if max_salary:
            employees = employees.filter(sal__lte=max_salary)

        # Handle POST requests (adding new employee)
        if request.method == 'POST':
        # ... (keep your existing POST handling code)
            pass
        return render(request, 'paykaro_app/manage_employees.html', {
            'employees': employees,
            'department': department,
            'manager': manager,
            'search_query': search_query,
            'gender_filter': gender_filter,
            'min_age': min_age,
            'max_age': max_age,
            'min_salary': min_salary,
            'max_salary': max_salary
            })

    except Employee.DoesNotExist:
        messages.error(request, 'Manager not found.')
        return redirect('manager_dashboard')

def approve_leaves(request):
    if request.session.get('role') != 'manager':
        return redirect('manager_login')

    manager_id = request.session.get('emp_id')
    try:
        manager = Employee.objects.get(emp_id=manager_id)
        department = manager.dept_id

        pending_leaves = Leave.objects.filter(
            emp_id__dept_id=department,
            status='P'
        ).select_related('emp_id')

        if request.method == 'POST':
            leave_id = request.POST.get('leave_id')
            action = request.POST.get('action')

            leave = get_object_or_404(Leave, leave_id=leave_id)
            if leave.emp_id.dept_id != department:
                messages.error(request, 'Unauthorized: Leave belongs to employee from different department')
                return redirect('approve_leaves')

            if action == 'approve':
                leave.status = 'A'
                if not leave.payroll_id:
                    try:
                        salary = Salary.objects.get(emp_id=leave.emp_id)
                        payroll = Payroll.objects.create(
                            employee=leave.emp_id,
                            salary=salary,
                            pay_period_start=timezone.now().date(),
                            pay_period_end=timezone.now().date(),
                            processed_by=manager
                        )
                        payroll.calculate_net_salary()
                        payroll.save()
                        leave.payroll_id = payroll
                    except Salary.DoesNotExist:
                        messages.warning(request, 'Leave approved but no salary record found for payroll creation')
            elif action == 'reject':
                leave.status = 'R'

            leave.save()
            messages.success(request, f'Leave {action}d successfully')
            return redirect('approve_leaves')

        return render(request, 'paykaro_app/approve_leaves.html', {
            'pending_leaves': pending_leaves
        })

    except Employee.DoesNotExist:
        messages.error(request, 'Manager not found.')
        return redirect('manager_login')



@manager_login_required
def generate_payroll(request):
    if request.session.get('role') != 'manager':
        return redirect('manager_login')

    manager_id = request.session.get('emp_id')
    try:
        manager = Employee.objects.get(emp_id=manager_id)
        department = manager.dept_id

        # Exclude manager from the employee list
        employees = Employee.objects.filter(dept_id=department).exclude(emp_id=manager_id)

        if request.method == 'POST':
            try:
                selected_employees = request.POST.getlist('employees')
                if not selected_employees:
                    messages.error(request, 'Please select at least one employee')
                    return redirect('generate_payroll')

                month = int(request.POST.get('month', timezone.now().month))
                year = int(request.POST.get('year', timezone.now().year))

                start_date = timezone.datetime(year, month, 1).date()
                end_date = timezone.datetime(year, month,
                                             calendar.monthrange(year, month)[1]).date()

                payroll_records = []

                # Process each selected employee
                for emp_id in selected_employees:
                    # Skip if this is the manager's ID
                    if int(emp_id) == manager_id:
                        continue

                    try:
                        employee = Employee.objects.get(emp_id=emp_id, dept_id=department)
                    except Employee.DoesNotExist:
                        messages.warning(request, f'Employee with ID {emp_id} not found or not in your department')
                        continue

                    # Get or create salary record
                    salary, created = Salary.objects.get_or_create(
                        emp_id=employee,
                        defaults={
                            'basic': Decimal('0.00'),
                            'bonus': Decimal('0.00'),
                            'DA': Decimal('0.00'),
                            'HRA': Decimal('0.00'),
                            'PF': Decimal('0.00'),
                            'income_tax': Decimal('0.00'),
                            'health_ins': Decimal('1000.00')
                        }
                    )

                    # Update salary if provided
                    basic_salary = request.POST.get(f'basic_{emp_id}')
                    bonus = request.POST.get(f'bonus_{emp_id}', '0.00')

                    if basic_salary:
                        try:
                            salary.basic = Decimal(basic_salary)
                            salary.bonus = Decimal(bonus)
                            salary.save()  # This will trigger the calculations in the save method
                        except (ValueError, InvalidOperation) as e:
                            messages.warning(request, f'Invalid salary values for employee {employee.f_name}: {str(e)}')
                            continue

                    # Get or create payroll record
                    payroll, created = Payroll.objects.get_or_create(
                        employee=employee,
                        pay_period_start=start_date,
                        pay_period_end=end_date,
                        defaults={
                            'salary': salary,
                            'processed_by': manager
                        }
                    )

                    if not created:
                        payroll.salary = salary
                        payroll.processed_by = manager

                    payroll.calculate_net_salary()
                    payroll.save()

                    payroll_records.append({
                        'employee_name': f"{employee.f_name} {employee.l_name}",
                        'basic': str(salary.basic),
                        'da': str(salary.DA),
                        'hra': str(salary.HRA),
                        'bonus': str(salary.bonus),
                        'pf': str(salary.PF),
                        'tax': str(salary.income_tax),
                        'health_ins': str(salary.health_ins),
                        'leave_deduction': str(payroll.leave_deduction),
                        'net_salary': str(payroll.net_salary)
                    })

                # Generate report based on format
                if payroll_records:
                    report_format = request.POST.get('format', 'csv')

                    if report_format == 'csv':
                        response = HttpResponse(
                            content_type='text/csv',
                            headers={
                                'Content-Disposition': f'attachment; filename="payroll_{department.dept_name}_{year}_{month}.csv"',
                                'Cache-Control': 'no-cache'
                            },
                        )

                        writer = csv.writer(response)
                        writer.writerow([
                            'Employee Name', 'Basic', 'DA (10%)', 'HRA (20%)', 'Bonus',
                            'PF (12%)', 'Tax (10%)', 'Health Insurance', 'Leave Deduction', 'Net Salary'
                        ])

                        for record in payroll_records:
                            writer.writerow([
                                record['employee_name'],
                                record['basic'],
                                record['da'],
                                record['hra'],
                                record['bonus'],
                                record['pf'],
                                record['tax'],
                                record['health_ins'],
                                record['leave_deduction'],
                                record['net_salary']
                            ])

                        return response

                    elif report_format == 'pdf':
                        # Generate PDF
                        pdf = generate_pdf_payroll(payroll_records, department, year, month)

                        # Create response
                        response = HttpResponse(content_type='application/pdf')
                        response[
                            'Content-Disposition'] = f'attachment; filename="payroll_{department.dept_name}_{year}_{month}.pdf"'
                        response['Cache-Control'] = 'no-cache'

                        # Write PDF to response
                        response.write(pdf)
                        return response

                messages.success(request, f'Successfully generated payroll for {len(payroll_records)} employees')
                return redirect('manager_dashboard')

            except Exception as e:
                messages.error(request, f'Error generating payroll: {str(e)}')
                return redirect('generate_payroll')

        context = {
            'employees': employees,  # This now excludes the manager
            'current_month': timezone.now().month,
            'current_year': timezone.now().year,
        }
        return render(request, 'paykaro_app/generate_payroll.html', context)

    except Employee.DoesNotExist:
        messages.error(request, 'Manager not found.')
        return redirect('manager_login')


from django.views.decorators.cache import never_cache
@never_cache
def manager_dashboard(request):
    if request.session.get('role') == 'manager':
        manager_id = request.session.get('emp_id')
        try:
            manager = Employee.objects.get(emp_id=manager_id)
            department = manager.dept_id
            employee_count = Employee.objects.filter(dept_id=department).exclude(emp_id=manager_id).count()

            # Get additional statistics
            active_leaves = Leave.objects.filter(
                emp_id__dept_id=department,
                status='A',
                end_date__gte=timezone.now().date()
            ).count()

            pending_requests = Leave.objects.filter(
                emp_id__dept_id=department,
                status='P'
            ).count()

            context = {
                'manager': manager,
                'department': department,
                'employee_count': employee_count,
                'active_leaves': active_leaves,
                'pending_requests': pending_requests
            }
            return render(request, 'paykaro_app/manager_dashboard.html', context)

        except Employee.DoesNotExist:
            messages.error(request, 'Manager not found.')

    return redirect('manager_login')


@never_cache
@employee_login_required
def employee_dashboard(request):
    if request.session.get('role') != 'employee':
        return redirect('employee_login')

    try:
        # Get employee details
        emp_id = request.session.get('emp_id')
        employee = Employee.objects.get(emp_id=emp_id)

        # Get leave statistics
        current_year = timezone.now().year
        all_leaves = Leave.objects.filter(
            emp_id=employee,
            start_date__year=current_year
        )

        leaves_taken = all_leaves.filter(status='A').count()
        leaves_remaining = 12 - leaves_taken  # Assuming 12 leaves per year

        # Get recent leave applications
        recent_leaves = Leave.objects.filter(
            emp_id=employee
        ).order_by('-start_date')[:5]  # Get last 5 leaves

        context = {
            'employee': employee,
            'leaves_taken': leaves_taken,
            'leaves_remaining': leaves_remaining,
            'recent_leaves': recent_leaves,
        }

        return render(request, 'paykaro_app/employee_dashboard.html', context)

    except Employee.DoesNotExist:
        messages.error(request, 'Employee not found.')
        return redirect('employee_login')


def logout_view(request):
    role = request.session.get('role')  # Check the user's role before logout
    request.session.flush()  # Clear session (logs the user out)

    if role == 'manager':
        return redirect('manager_login')  # Use your named URL
    else:
        return redirect('employee_login')  # Default to employee if not manager

def signup(request):
    if request.method == 'POST':
        form = EmployeeSignupForm(request.POST)
        if form.is_valid():
            employee = form.save()
            role = form.cleaned_data['role']

            # Store session
            request.session['emp_id'] = employee.emp_id
            request.session['role'] = role

            # Redirect based on role
            if role == 'manager':
                return redirect('manager_dashboard')
            else:
                return redirect('employee_dashboard')
    else:
        form = EmployeeSignupForm()

    return render(request, 'paykaro_app/signup.html', {'form': form})

@manager_login_required
@csrf_exempt  # Add this decorator
@require_http_methods(["POST"])
def update_employee(request, employee_id):
    if request.session.get('role') != 'manager':
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)

    try:
        # Get the manager's department
        manager = Employee.objects.get(emp_id=request.session.get('emp_id'))
        department = manager.dept_id

        # Get the employee and verify they belong to the manager's department
        employee = get_object_or_404(Employee, emp_id=employee_id, dept_id=department)

        try:
            # Parse the JSON data from request
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            }, status=400)

        # Update allowed fields
        allowed_fields = ['f_name', 'l_name', 'emp_email', 'age', 'gender', 'city', 'sal']

        for field in allowed_fields:
            if field in data:
                try:
                    if field == 'age':
                        setattr(employee, field, int(data[field]))
                    elif field == 'sal':
                        setattr(employee, field, Decimal(data[field]))
                    else:
                        setattr(employee, field, data[field])
                except (ValueError, TypeError) as e:
                    return JsonResponse({
                        'success': False,
                        'message': f'Invalid value for field {field}: {str(e)}'
                    }, status=400)

        try:
            employee.full_clean()  # Validate the model
            employee.save()
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)

        return JsonResponse({
            'success': True,
            'message': 'Employee updated successfully',
            'data': {
                'emp_id': employee.emp_id,
                'f_name': employee.f_name,
                'l_name': employee.l_name,
                'emp_email': employee.emp_email,
                'age': employee.age,
                'gender': employee.get_gender_display(),
                'city': employee.city,
                'sal': str(employee.sal)
            }
        })

    except Employee.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Employee or manager not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred while updating the employee: {str(e)}'
        }, status=500)

@manager_login_required
@require_http_methods(["POST"])
def delete_employee(request, employee_id):
    if request.session.get('role') != 'manager':
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)

    try:
        # Get the manager's department
        manager = Employee.objects.get(emp_id=request.session.get('emp_id'))
        department = manager.dept_id

        # Get the employee and verify they belong to the manager's department
        employee = get_object_or_404(Employee, emp_id=employee_id, dept_id=department)
        employee.delete()

        return JsonResponse({
            'success': True,
            'message': 'Employee deleted successfully'
        })

    except Employee.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Employee or manager not found'
        }, status=404)

@employee_login_required
def apply_leave(request):
    if request.method == 'POST':
        emp_id = request.session.get('emp_id')
        try:
            employee = Employee.objects.get(emp_id=emp_id)

            # Get form data
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            reason = request.POST.get('reason')

            # Handle 'Other' reason
            if reason == 'Other':
                reason = request.POST.get('other_reason')

            # Validate dates
            start_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()

            # Check for overlapping leaves
            overlapping_leaves = Leave.objects.filter(
                emp_id=employee,
                start_date__lte=end_date,
                end_date__gte=start_date,
                status__in=['P', 'A']  # Pending or Approved
            ).exists()

            if overlapping_leaves:
                messages.error(request, 'You already have a leave request for these dates')
                return redirect('employee_dashboard')

            # Calculate number of days
            leave_days = (end_date - start_date).days + 1

            # Get leave statistics
            current_year = timezone.now().year
            approved_leaves = Leave.objects.filter(
                emp_id=employee,
                status='A',
                start_date__year=current_year
            ).count()

            if approved_leaves + leave_days > 12:  # Assuming 12 leaves per year
                messages.error(request, 'Insufficient leave balance')
                return redirect('employee_dashboard')

            # Create leave request
            Leave.objects.create(
                start_date=start_date,
                end_date=end_date,
                reason=reason,
                emp_id=employee,
                status='P'  # Set as Pending
            )

            messages.success(request, 'Leave application submitted successfully!')

        except Employee.DoesNotExist:
            messages.error(request, 'Employee not found.')
        except ValueError as e:
            messages.error(request, f'Invalid date format: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error applying for leave: {str(e)}')

    return redirect('employee_dashboard')

@employee_login_required
def view_salary(request):
    if request.session.get('role') != 'employee':
        return redirect('employee_login')

    emp_id = request.session.get('emp_id')
    try:
        employee = Employee.objects.get(emp_id=emp_id)
        salary = Salary.objects.get(emp_id=employee)

        context = {
            'employee': employee,
            'salary': salary
        }

        return render(request, 'paykaro_app/view_salary.html', context)

    except Employee.DoesNotExist:
        messages.error(request, 'Employee not found.')
        return redirect('employee_login')
    except Salary.DoesNotExist:
        messages.error(request, 'Salary information not found.')
        return redirect('employee_dashboard')

from functools import wraps

def any_user_login_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.session.get('emp_id'):
            return redirect('employee_login')
        return view_func(request, *args, **kwargs)
    return wrapped

@any_user_login_required
def update_profile_photo(request):
    if request.method == 'POST':
        try:
            employee = Employee.objects.get(emp_id=request.session.get('emp_id'))
            form = ProfilePhotoForm(request.POST, request.FILES, instance=employee)
            if form.is_valid():
                form.save()
                messages.success(request, 'Profile photo updated successfully!')
            else:
                messages.error(request, 'Error updating profile photo')
        except Employee.DoesNotExist:
            messages.error(request, 'Employee not found')

    return redirect('manager_dashboard' if request.session.get('role') == 'manager' else 'employee_dashboard')
