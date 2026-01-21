from flask import Blueprint, render_template, redirect, url_for, request, flash, g
from models import User, Bill, db
from datetime import datetime, timedelta

employee_bp = Blueprint('employee', __name__, url_prefix='/employee')

@employee_bp.before_request
def check_employee():
    if not g.get('user') or g.user.role != 'employee':
        return redirect(url_for('auth.login'))

@employee_bp.route('/dashboard')
def dashboard():
    return render_template('employee_dashboard.html')

@employee_bp.route('/generate_bill', methods=['POST'])
def generate_bill():
    meter_number = request.form.get('meter_number')
    try:
        current_reading = float(request.form.get('current_reading'))
    except (ValueError, TypeError):
        flash("Invalid Current Reading")
        return redirect(url_for('employee.dashboard'))

    if not meter_number:
        flash("Meter Number Required")
        return redirect(url_for('employee.dashboard'))
    
    if current_reading < 0:
        flash("Current reading cannot be negative")
        return redirect(url_for('employee.dashboard'))
    
    consumer = User.query.filter_by(meter_number=meter_number, role='consumer').first()
    if not consumer:
        flash('Consumer not found')
        return redirect(url_for('employee.dashboard'))
        
    last_bill = Bill.query.filter_by(user_id=consumer.id).order_by(Bill.bill_date.desc()).first()
    previous_reading = last_bill.current_reading if last_bill else 0.0
    
    if current_reading < previous_reading:
        flash('Error: Current reading less than previous')
        return redirect(url_for('employee.dashboard'))
        
    units = current_reading - previous_reading
    amount = 0.0
    

    if consumer.connection_type == 'Household':
        rem = units
        if rem > 0:
            slab1 = min(rem, 50)
            amount += slab1 * 1.25
            rem -= slab1
        if rem > 0:
            slab2 = min(rem, 50)
            amount += slab2 * 1.50
            rem -= slab2
        if rem > 0:
            amount += rem * 2.00
    elif consumer.connection_type == 'Commercial':
        amount = units * 4.0
    elif consumer.connection_type == 'Industrial':
        amount = units * 6.0
        
    now = datetime.utcnow()
    due = now + timedelta(days=30)
    penalty = amount * 0.10
    
    new_bill = Bill(
        user_id=consumer.id,
        previous_reading=previous_reading,
        current_reading=current_reading,
        units_consumed=units,
        total_amount=amount,
        bill_date=now,
        due_date=due,
        penalty_amount=penalty,
        status='Unpaid'
    )
    
    db.session.add(new_bill)
    db.session.commit()
    
    rate_desc = ""
    if consumer.connection_type == 'Household':
        rate_desc = "Tiered: 0-50@1.25, 51-100@1.50, >100@2.00"
    elif consumer.connection_type == 'Commercial':
        rate_desc = "Flat Rate: Rs 4.0/unit"
    else:
        rate_desc = "Flat Rate: Rs 6.0/unit"

    return render_template('bill_receipt.html', bill=new_bill, consumer=consumer, rate_desc=rate_desc)
