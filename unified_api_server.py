from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict
from sklearn.ensemble import RandomForestRegressor

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# ============================================================================
# DATABASE HELPER FUNCTIONS
# ============================================================================

def get_db_connection():
    """Get database connection, preferring a DB in the same folder as this server.

    Fallback: parent folder (legacy layout).
    """
    import os
    here = os.path.abspath(os.path.dirname(__file__))
    candidates = [
        os.path.join(here, 'employees.db'),
        os.path.abspath(os.path.join(here, '..', 'employees.db')),
    ]
    for path in candidates:
        if os.path.exists(path):
            return sqlite3.connect(path)
    # Last resort: connect to path in sibling root (will likely fail if missing)
    return sqlite3.connect(candidates[0])

# ============================================================================
# ADMIN LOGIN FUNCTIONS
# ============================================================================

def check_admin_login(email, password):
    """Check if admin credentials are valid"""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Authenticate against the dedicated `admin` table (Username / Password)
    # The admin table was added to store admin accounts separately from employees.
    cursor.execute('SELECT AdminID, FirstName, LastName FROM admin WHERE Username=? AND Password=?', (email, password))
    result = cursor.fetchone()
    conn.close()
    return result is not None

@app.route('/admin-login', methods=['POST'])
def admin_login():
    """Handle admin login requests"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if check_admin_login(email, password):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False}), 401

# ============================================================================
# CUSTOMER LOGIN FUNCTIONS
# ============================================================================

def check_customer_login(username, password):
    """Check if customer credentials are valid"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM customers WHERE Username=? AND Password=?', (username, password))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def get_customer_by_credentials(username, password):
    """Return customer info for valid credentials or None"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT CustomerID, FirstName, LastName, Username FROM customers WHERE Username=? AND Password=?', (username, password))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        'customerId': row[0],
        'first_name': row[1],
        'last_name': row[2],
        'username': row[3]
    }

@app.route('/customer-login', methods=['POST'])
def customer_login():
    """Handle customer login requests"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    customer = get_customer_by_credentials(username, password)
    if customer:
        return jsonify({'success': True, 'customer': customer})
    else:
        return jsonify({'success': False}), 401


# ============================================================================
# EMPLOYEE LOGIN / STATS
# ============================================================================

def check_employee_login(email, password):
    """Simple employee auth by email and password"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT EmployeeID, FirstName, LastName FROM employees WHERE employee_email=? AND employee_password=?', (email, password))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {'id': row[0], 'first_name': row[1], 'last_name': row[2]}


@app.route('/employee-login', methods=['POST'])
def employee_login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')
    emp = check_employee_login(email, password)
    if emp:
        return jsonify({'success': True, 'employee': emp})
    else:
        return jsonify({'success': False}), 401


@app.route('/employee/<int:employee_id>/stats', methods=['GET'])
def get_employee_stats(employee_id):
    """Return the salary/hours and recent sales for a given employee."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT EmployeeID, FirstName, LastName, employee_email, Salary, HoursWorked FROM employees WHERE EmployeeID=?', (employee_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Employee not found'}), 404

        employee = {
            'id': row[0],
            'first_name': row[1],
            'last_name': row[2],
            'email': row[3],
            'salary': float(row[4]) if row[4] is not None else None,
            'hours_worked': float(row[5]) if row[5] is not None else None
        }

        # Recent sales by this employee (max 10)
        cursor.execute('''
            SELECT s.SalesID, s.SalesDate, p.ProductName, s.Quantity, (s.Quantity * p.Price) as revenue
            FROM sales s
            JOIN products p ON s.ProductID = p.ProductID
            WHERE s.SalesPersonID = ?
            ORDER BY s.SalesDate DESC, s.SalesID DESC
            LIMIT 10
        ''', (employee_id,))
        sales = []
        for r in cursor.fetchall():
            sales.append({'sale_id': r[0], 'date': r[1], 'product': r[2], 'quantity': r[3], 'revenue': r[4]})

        employee['recent_sales'] = sales
        return jsonify({'employee': employee})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# ============================================================================
# CUSTOMER SIGNUP FUNCTIONS
# ============================================================================

def get_next_customer_id():
    """Get the next available CustomerID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(CustomerID) FROM customers')
    result = cursor.fetchone()
    conn.close()
    return (result[0] or 0) + 1

def check_username_exists(username):
    """Check if username already exists"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM customers WHERE Username=?', (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] > 0

def register_customer(customer_data):
    """Register a new customer in the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO customers (CustomerID, FirstName, MiddleInitial, LastName, CityID, Address, Username, Password)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            customer_data['CustomerID'],
            customer_data['FirstName'],
            customer_data['MiddleInitial'],
            customer_data['LastName'],
            customer_data['CityID'],
            customer_data['Address'],
            customer_data['Username'],
            customer_data['Password']
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        print(f"Database error: {e}")
        return False

@app.route('/customer-signup', methods=['POST'])
def customer_signup():
    """Handle customer registration requests"""
    data = request.get_json()
    
    # Extract and validate required fields
    required_fields = ['firstName', 'lastName', 'address', 'cityId', 'username', 'password']
    for field in required_fields:
        if field not in data or not str(data[field]).strip():
            return jsonify({'success': False, 'message': f'Missing required field: {field}'}), 400
    
    # Check if username already exists
    if check_username_exists(data['username']):
        return jsonify({'success': False, 'message': 'Username already exists'}), 400
    
    # Prepare customer data
    customer_data = {
        'CustomerID': get_next_customer_id(),
        'FirstName': str(data['firstName']).strip(),
        'MiddleInitial': str(data.get('middleInitial', '')).strip() or None,
        'LastName': str(data['lastName']).strip(),
        'CityID': int(data['cityId']),
        'Address': str(data['address']).strip(),
        'Username': str(data['username']).strip(),
        'Password': str(data['password'])
    }
    
    # Register the customer
    if register_customer(customer_data):
        return jsonify({
            'success': True, 
            'message': 'Account created successfully!',
            'customerId': customer_data['CustomerID']
        })
    else:
        return jsonify({'success': False, 'message': 'Failed to create account'}), 500

@app.route('/check-username', methods=['POST'])
def check_username():
    """Check if username is available"""
    data = request.get_json()
    username = str(data.get('username', '')).strip()
    
    if not username:
        return jsonify({'available': False, 'message': 'Username is required'})
    
    available = not check_username_exists(username)
    return jsonify({
        'available': available,
        'message': 'Username is available' if available else 'Username already taken'
    })

# ============================================================================
# PRODUCT CATALOG FUNCTIONS
# ============================================================================

@app.route('/products', methods=['GET'])
def get_products():
    """Get all products with category information"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get query parameters for filtering and pagination
    category_id = request.args.get('category_id')
    search = request.args.get('search', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    offset = (page - 1) * per_page
    
    # Build query with optional filters
    base_query = '''
        SELECT p.ProductID, p.ProductName, p.Price, p.CategoryID, p.Class, 
               p.Resistant, p.IsAllergic, p.VitalityDays, c.CategoryName
        FROM products p
        JOIN categories c ON p.CategoryID = c.CategoryID
    '''
    
    conditions = []
    params = []
    
    if category_id:
        conditions.append('p.CategoryID = ?')
        params.append(category_id)
    
    if search:
        conditions.append('(p.ProductName LIKE ? OR c.CategoryName LIKE ?)')
        params.extend([f'%{search}%', f'%{search}%'])
    
    if conditions:
        base_query += ' WHERE ' + ' AND '.join(conditions)
    
    base_query += ' ORDER BY p.ProductName LIMIT ? OFFSET ?'
    params.extend([per_page, offset])
    
    cursor.execute(base_query, params)
    products = cursor.fetchall()
    
    # Get total count for pagination
    count_query = 'SELECT COUNT(*) FROM products p JOIN categories c ON p.CategoryID = c.CategoryID'
    if conditions:
        # Use the same conditions as in the main query; only remove LIMIT/OFFSET params
        count_query += ' WHERE ' + ' AND '.join(conditions)
        count_params = params[:-2]  # drop per_page and offset
        cursor.execute(count_query, count_params)
    else:
        cursor.execute(count_query)
    
    total_count = cursor.fetchone()[0]
    conn.close()
    
    # Format products for response
    products_list = []
    for product in products:
        products_list.append({
            'id': product[0],
            'name': product[1],
            'price': product[2],
            'category_id': product[3],
            'class': product[4],
            'resistant': product[5],
            'is_allergic': product[6],
            'vitality_days': product[7],
            'category_name': product[8]
        })
    
    return jsonify({
        'products': products_list,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'pages': (total_count + per_page - 1) // per_page
        }
    })

@app.route('/categories', methods=['GET'])
def get_categories():
    """Get all categories"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT CategoryID, CategoryName FROM categories ORDER BY CategoryName')
    categories = cursor.fetchall()
    conn.close()
    
    categories_list = [{'id': cat[0], 'name': cat[1]} for cat in categories]
    return jsonify({'categories': categories_list})

@app.route('/cities', methods=['GET'])
def get_cities():
    """Get all cities for dropdowns"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT CityID, CityName FROM cities ORDER BY CityName')
    cities = cursor.fetchall()
    conn.close()
    
    cities_list = [{'id': city[0], 'name': city[1]} for city in cities]
    return jsonify({'cities': cities_list})

@app.route('/product/<int:product_id>', methods=['GET'])
def get_product_details(product_id):
    """Get detailed information for a specific product"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.ProductID, p.ProductName, p.Price, p.CategoryID, p.Class, 
               p.ModifyDate, p.Resistant, p.IsAllergic, p.VitalityDays, c.CategoryName
        FROM products p
        JOIN categories c ON p.CategoryID = c.CategoryID
        WHERE p.ProductID = ?
    ''', (product_id,))
    
    product = cursor.fetchone()
    conn.close()
    
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    return jsonify({
        'id': product[0],
        'name': product[1],
        'price': product[2],
        'category_id': product[3],
        'class': product[4],
        'modify_date': product[5],
        'resistant': product[6],
        'is_allergic': product[7],
        'vitality_days': product[8],
        'category_name': product[9]
    })

# ============================================================================
# ADMIN DASHBOARD FUNCTIONS
# ============================================================================

@app.route('/admin/dashboard-stats', methods=['GET'])
def get_dashboard_stats():
    """Get overall dashboard statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get counts from all tables
        cursor.execute('SELECT COUNT(*) FROM employees')
        employee_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM customers')
        customer_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM products')
        product_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM categories')
        category_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM cities')
        city_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM sales')
        sales_count = cursor.fetchone()[0]
        
        # Get total revenue
        cursor.execute('SELECT SUM(s.Quantity * p.Price) FROM sales s JOIN products p ON s.ProductID = p.ProductID')
        total_revenue = cursor.fetchone()[0] or 0
        
        # Get top selling products
        cursor.execute('''
            SELECT p.ProductName, SUM(s.Quantity) as total_sold
            FROM sales s 
            JOIN products p ON s.ProductID = p.ProductID 
            GROUP BY p.ProductID, p.ProductName 
            ORDER BY total_sold DESC 
            LIMIT 5
        ''')
        top_products = [{'name': row[0], 'sold': row[1]} for row in cursor.fetchall()]
        
        # Get sales by category
        cursor.execute('''
            SELECT c.CategoryName, SUM(s.Quantity) as total_sold
            FROM sales s 
            JOIN products p ON s.ProductID = p.ProductID 
            JOIN categories c ON p.CategoryID = c.CategoryID
            GROUP BY c.CategoryID, c.CategoryName 
            ORDER BY total_sold DESC
        ''')
        category_sales = [{'category': row[0], 'sold': row[1]} for row in cursor.fetchall()]
        
        # Get monthly sales trend (all available data, limited to most recent 12 months)
        cursor.execute('''
            SELECT strftime('%Y-%m', s.SalesDate) as month, 
                   SUM(s.Quantity * p.Price) as revenue
            FROM sales s 
            JOIN products p ON s.ProductID = p.ProductID 
            WHERE s.SalesDate IS NOT NULL
            GROUP BY strftime('%Y-%m', s.SalesDate)
            ORDER BY month DESC
            LIMIT 12
        ''')
        rows = cursor.fetchall()
        # Reverse to show chronological order, filter out any null months
        monthly_trend = [{'month': row[0], 'revenue': row[1]} for row in reversed(rows) if row[0]]
        
        return jsonify({
            'counts': {
                'employees': employee_count,
                'customers': customer_count,
                'products': product_count,
                'categories': category_count,
                'cities': city_count,
                'sales': sales_count
            },
            'revenue': {
                'total': float(total_revenue),
                'monthly_trend': monthly_trend
            },
            'top_products': top_products,
            'category_sales': category_sales
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/admin/employees', methods=['GET'])
def get_admin_employees():
    """Get all employees for admin management"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT e.EmployeeID, e.FirstName, e.LastName, e.employee_email, 
                   e.Gender, c.CityName, e.MiddleInitial, e.Salary, e.HoursWorked
            FROM employees e
            JOIN cities c ON e.CityID = c.CityID
            ORDER BY e.EmployeeID
        ''')
        
        employees = []
        for row in cursor.fetchall():
            employees.append({
                'id': row[0],
                'first_name': row[1],
                'last_name': row[2],
                'email': row[3],
                'gender': row[4],
                'city_name': row[5],
                'middle_initial': row[6],
                'salary': float(row[7]) if row[7] is not None else None,
                'hours_worked': float(row[8]) if row[8] is not None else None
            })
        
        return jsonify({'employees': employees})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/admin/recent-sales', methods=['GET'])
def get_recent_sales():
    """Get recent sales transactions"""
    limit = request.args.get('limit', 50, type=int)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT s.SalesID, s.SalesDate, p.ProductName as product_name, 
                   c.CategoryName as category_name, s.Quantity, p.Price,
                   (s.Quantity * p.Price) as total_amount,
                   ci.CityName, s.CustomerID
            FROM sales s
            JOIN products p ON s.ProductID = p.ProductID
            JOIN categories c ON p.CategoryID = c.CategoryID
            JOIN customers cust ON s.CustomerID = cust.CustomerID
            JOIN cities ci ON cust.CityID = ci.CityID
            ORDER BY s.SalesDate DESC, s.SalesID DESC
            LIMIT ?
        ''', (limit,))
        
        sales = []
        for row in cursor.fetchall():
            sales.append({
                'sale_id': row[0],
                'sale_date': row[1],
                'product_name': row[2],
                'category_name': row[3],
                'quantity': row[4],
                'price': row[5],
                'total_amount': row[6],
                'city': row[7],
                'customer_id': row[8]
            })
        
        return jsonify({'sales': sales})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/admin/products', methods=['GET'])
def get_admin_products():
    """Get products for admin management (with category names)"""
    limit = request.args.get('limit', 50, type=int)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT p.ProductID, p.ProductName, p.Price, c.CategoryName,
                   p.Class, p.Resistant, p.IsAllergic, p.VitalityDays
            FROM products p
            JOIN categories c ON p.CategoryID = c.CategoryID
            ORDER BY p.ProductID
            LIMIT ?
        ''', (limit,))
        
        products = []
        for row in cursor.fetchall():
            products.append({
                'id': row[0],
                'name': row[1],
                'price': row[2],
                'category_name': row[3],
                'class': row[4],
                'resistant': row[5],
                'is_allergic': row[6],
                'vitality_days': row[7]
            })
        
        return jsonify({'products': products})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

# ============================================================================
# INVENTORY MANAGEMENT APIs
# ============================================================================

@app.route('/inventory/stock-levels', methods=['GET'])
def get_stock_levels():
    """Get current stock levels for all products"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            p.ProductID,
            p.ProductName,
            p.Price,
            c.CategoryName,
            p.VitalityDays,
            COALESCE(SUM(i.quantity), 0) as current_stock,
            COUNT(DISTINCT i.inventory_id) as batch_count,
            MIN(i.expiry_date) as nearest_expiry
        FROM products p
        LEFT JOIN categories c ON p.CategoryID = c.CategoryID
        LEFT JOIN inventory i ON p.ProductID = i.product_id
        GROUP BY p.ProductID
        ORDER BY current_stock ASC
    """)
    
    columns = ['product_id', 'product_name', 'price', 'category', 'shelf_life_days', 
               'current_stock', 'batch_count', 'nearest_expiry']
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(zip(columns, row)) for row in rows])


@app.route('/inventory/expiring-soon', methods=['GET'])
def get_expiring_stock():
    """Get stock expiring within the next N days (default 7)"""
    days = request.args.get('days', 7, type=int)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            i.inventory_id,
            i.batch_number,
            p.ProductName,
            c.CategoryName,
            i.quantity,
            i.arrival_date,
            i.expiry_date,
            s.supplier_name,
            CAST((julianday(i.expiry_date) - julianday('now')) AS INTEGER) as days_until_expiry
        FROM inventory i
        JOIN products p ON i.product_id = p.ProductID
        JOIN categories c ON p.CategoryID = c.CategoryID
        JOIN suppliers s ON i.supplier_id = s.supplier_id
        WHERE i.expiry_date IS NOT NULL
          AND i.expiry_date BETWEEN date('now') AND date('now', '+' || ? || ' days')
        ORDER BY i.expiry_date ASC
    """, (days,))
    
    columns = ['inventory_id', 'batch_number', 'product_name', 'category', 'quantity',
               'arrival_date', 'expiry_date', 'supplier', 'days_until_expiry']
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'days_threshold': days,
        'total_batches': len(rows),
        'total_units': sum(row[4] for row in rows),
        'expiring_items': [dict(zip(columns, row)) for row in rows]
    })


@app.route('/inventory/expired', methods=['GET'])
def get_expired_stock():
    """Get already expired stock"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            i.inventory_id,
            i.batch_number,
            p.ProductName,
            c.CategoryName,
            i.quantity,
            i.expiry_date,
            s.supplier_name,
            CAST((julianday('now') - julianday(i.expiry_date)) AS INTEGER) as days_expired
        FROM inventory i
        JOIN products p ON i.product_id = p.ProductID
        JOIN categories c ON p.CategoryID = c.CategoryID
        JOIN suppliers s ON i.supplier_id = s.supplier_id
        WHERE i.expiry_date IS NOT NULL
          AND i.expiry_date < date('now')
        ORDER BY i.expiry_date ASC
    """)
    
    columns = ['inventory_id', 'batch_number', 'product_name', 'category', 'quantity',
               'expiry_date', 'supplier', 'days_expired']
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'total_batches': len(rows),
        'total_units': sum(row[4] for row in rows),
        'expired_items': [dict(zip(columns, row)) for row in rows]
    })


@app.route('/inventory/product/<int:product_id>', methods=['GET'])
def get_product_inventory(product_id):
    """Get all inventory batches for a specific product"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            i.inventory_id,
            i.batch_number,
            i.quantity,
            i.arrival_date,
            i.expiry_date,
            s.supplier_name,
            s.contact_info,
            CASE 
                WHEN i.expiry_date IS NULL THEN 'NON-PERISHABLE'
                WHEN i.expiry_date < date('now') THEN 'EXPIRED'
                WHEN i.expiry_date < date('now', '+7 days') THEN 'EXPIRING SOON'
                ELSE 'GOOD'
            END as status
        FROM inventory i
        JOIN suppliers s ON i.supplier_id = s.supplier_id
        WHERE i.product_id = ?
        ORDER BY 
            CASE 
                WHEN i.expiry_date IS NULL THEN 999999
                ELSE julianday(i.expiry_date) - julianday('now')
            END ASC
    """, (product_id,))
    
    columns = ['inventory_id', 'batch_number', 'quantity', 'arrival_date', 'expiry_date',
               'supplier_name', 'contact_info', 'status']
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'product_id': product_id,
        'total_batches': len(rows),
        'total_quantity': sum(row[2] for row in rows),
        'batches': [dict(zip(columns, row)) for row in rows]
    })


@app.route('/suppliers', methods=['GET'])
def get_suppliers():
    """Get all suppliers"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            s.supplier_id,
            s.supplier_name,
            s.contact_info,
            COUNT(i.inventory_id) as total_batches,
            SUM(i.quantity) as total_units_supplied
        FROM suppliers s
        LEFT JOIN inventory i ON s.supplier_id = i.supplier_id
        GROUP BY s.supplier_id
        ORDER BY total_batches DESC
    """)
    
    columns = ['supplier_id', 'supplier_name', 'contact_info', 'total_batches', 'total_units_supplied']
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(zip(columns, row)) for row in rows])


# ============================================================================
# MACHINE LEARNING FORECASTING ENGINE
# ============================================================================

def generate_ml_forecast(product_id, days=30):
    """
    Generate demand forecast using Random Forest Regressor based on historical sales data.
    Uses time-series features: day of week, day of month, week of year, lag features.
    
    Returns: list of forecast dictionaries with dates and predictions
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get historical sales data (last 90 days)
        cursor.execute("""
            SELECT DATE(s.SalesDate) as sale_date, SUM(s.Quantity) as total_qty
            FROM sales s
            WHERE s.ProductID = ?
              AND s.SalesDate >= date('now', '-90 days')
              AND s.SalesDate < date('now')
            GROUP BY DATE(s.SalesDate)
            ORDER BY sale_date
        """, (product_id,))
        
        history = cursor.fetchall()
        
        if len(history) < 14:
            # Need at least 2 weeks for Random Forest
            return None
        
        # Build feature matrix from historical data
        X_train = []
        y_train = []
        
        for i, (date_str, qty) in enumerate(history):
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            
            # Time-based features
            day_of_week = dt.weekday()
            day_of_month = dt.day
            week_of_year = dt.isocalendar()[1]
            month = dt.month
            
            # Lag features (previous days' sales)
            lag_1 = history[i-1][1] if i >= 1 else qty
            lag_7 = history[i-7][1] if i >= 7 else qty
            
            # Rolling average features
            if i >= 7:
                recent_avg = np.mean([history[j][1] for j in range(i-7, i)])
            else:
                recent_avg = qty
            
            features = [
                day_of_week,
                day_of_month,
                week_of_year,
                month,
                lag_1,
                lag_7,
                recent_avg
            ]
            
            X_train.append(features)
            y_train.append(qty)
        
        # Train Random Forest model
        rf_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=2,
            min_samples_leaf=1,
            random_state=42,
            n_jobs=-1
        )
        
        rf_model.fit(X_train, y_train)
        
        # Calculate statistics for confidence and factors
        quantities = [float(row[1]) for row in history]
        mean_demand = np.mean(quantities)
        std_demand = np.std(quantities)
        
        # Day-of-week seasonality (for season_factor reporting)
        day_quantities = defaultdict(list)
        for date_str, qty in history:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            day_quantities[dt.weekday()].append(qty)
        
        day_factors = {}
        overall_avg = mean_demand if mean_demand > 0 else 1
        for day in range(7):
            if day in day_quantities and len(day_quantities[day]) > 0:
                day_avg = np.mean(day_quantities[day])
                day_factors[day] = day_avg / overall_avg
            else:
                day_factors[day] = 1.0
        
        # Generate forecasts
        forecasts = []
        last_qty = quantities[-1]
        last_7_qty = quantities[-7] if len(quantities) >= 7 else last_qty
        last_7_avg = np.mean(quantities[-7:]) if len(quantities) >= 7 else mean_demand
        
        for i in range(days):
            forecast_date = datetime.now() + timedelta(days=i+1)
            date_str = forecast_date.strftime('%Y-%m-%d')
            
            # Build features for prediction
            day_of_week = forecast_date.weekday()
            day_of_month = forecast_date.day
            week_of_year = forecast_date.isocalendar()[1]
            month = forecast_date.month
            
            # Use last known values for lag features
            lag_1 = forecasts[-1]['predicted_demand'] if forecasts else last_qty
            lag_7 = forecasts[-7]['predicted_demand'] if len(forecasts) >= 7 else last_7_qty
            
            # Rolling average
            if len(forecasts) >= 7:
                recent_avg = np.mean([f['predicted_demand'] for f in forecasts[-7:]])
            else:
                recent_avg = last_7_avg
            
            features = [[
                day_of_week,
                day_of_month,
                week_of_year,
                month,
                lag_1,
                lag_7,
                recent_avg
            ]]
            
            # Predict
            predicted_demand = max(0, rf_model.predict(features)[0])
            
            # Calculate factors for reporting
            season_factor = day_factors.get(day_of_week, 1.0)
            
            # Market factor (momentum)
            market_factor = last_7_avg / mean_demand if mean_demand > 0 else 1.0
            market_factor = max(0.5, min(1.5, market_factor))
            
            # Confidence based on Random Forest's prediction variance and CV
            cv = std_demand / mean_demand if mean_demand > 0 else 1.0
            base_confidence = max(0.6, min(0.95, 1.0 - cv * 0.3))
            
            # Random Forest gives us implicit confidence through ensemble
            confidence = base_confidence
            
            forecasts.append({
                'forecast_date': date_str,
                'predicted_demand': round(predicted_demand, 2),
                'season_factor': round(season_factor, 3),
                'market_factor': round(market_factor, 3),
                'confidence_level': round(confidence, 3)
            })
        
        return forecasts
        
    except Exception as e:
        print(f"Error in Random Forest forecast for product {product_id}: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        conn.close()


def generate_ml_summary():
    """
    Generate forecast summary for all products with sufficient sales history.
    Returns top products by predicted 30-day demand.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get products with recent sales
        cursor.execute("""
            SELECT DISTINCT p.ProductID, p.ProductName, c.CategoryName
            FROM products p
            JOIN categories c ON p.CategoryID = c.CategoryID
            JOIN sales s ON p.ProductID = s.ProductID
            WHERE s.SalesDate >= date('now', '-90 days')
            ORDER BY p.ProductID
            LIMIT 100
        """)
        
        products = cursor.fetchall()
        summaries = []
        
        for product_id, product_name, category_name in products:
            forecasts = generate_ml_forecast(product_id, days=30)
            
            if forecasts and len(forecasts) > 0:
                avg_daily = np.mean([f['predicted_demand'] for f in forecasts])
                total_30day = sum([f['predicted_demand'] for f in forecasts])
                avg_confidence = np.mean([f['confidence_level'] for f in forecasts])
                
                summaries.append({
                    'product_name': product_name,
                    'category': category_name,
                    'avg_daily_demand': round(avg_daily, 2),
                    'total_30day_demand': round(total_30day, 2),
                    'avg_confidence': round(avg_confidence, 3)
                })
        
        # Sort by total demand descending
        summaries.sort(key=lambda x: x['total_30day_demand'], reverse=True)
        return summaries[:50]
        
    except Exception as e:
        print(f"Error generating ML summary: {e}")
        return []
    finally:
        conn.close()


# ============================================================================
# FORECASTING APIs (ML-POWERED)
# ============================================================================

@app.route('/forecasts/product/<int:product_id>', methods=['GET'])
def get_product_forecast(product_id):
    """Get ML-generated demand forecast for a specific product"""
    days = request.args.get('days', 30, type=int)
    days = min(90, max(1, days))  # clamp to 1-90 days
    
    # Try ML forecast first
    forecasts = generate_ml_forecast(product_id, days)
    
    if forecasts:
        return jsonify({
            'product_id': product_id,
            'forecast_days': days,
            'forecasts': forecasts,
            'source': 'ml'
        })
    
    # Fallback to database if ML fails (not enough data)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            forecast_date,
            predicted_demand,
            season_factor,
            market_factor,
            confidence_level
        FROM forecasts
        WHERE product_id = ?
          AND forecast_date BETWEEN date('now') AND date('now', '+' || ? || ' days')
        ORDER BY forecast_date ASC
    """, (product_id, days))
    
    columns = ['forecast_date', 'predicted_demand', 'season_factor', 'market_factor', 'confidence_level']
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'product_id': product_id,
        'forecast_days': days,
        'forecasts': [dict(zip(columns, row)) for row in rows],
        'source': 'database'
    })


@app.route('/forecasts/summary', methods=['GET'])
def get_forecast_summary():
    """Get ML-generated aggregated forecast summary"""
    
    # Try ML summary first
    ml_summary = generate_ml_summary()
    
    if ml_summary and len(ml_summary) > 0:
        return jsonify(ml_summary)
    
    # Fallback to database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            p.ProductName,
            c.CategoryName,
            AVG(f.predicted_demand) as avg_daily_demand,
            SUM(f.predicted_demand) as total_30day_demand,
            AVG(f.confidence_level) as avg_confidence
        FROM forecasts f
        JOIN products p ON f.product_id = p.ProductID
        JOIN categories c ON p.CategoryID = c.CategoryID
        WHERE f.forecast_date BETWEEN date('now') AND date('now', '+30 days')
        GROUP BY f.product_id
        ORDER BY total_30day_demand DESC
        LIMIT 50
    """)
    
    columns = ['product_name', 'category', 'avg_daily_demand', 'total_30day_demand', 'avg_confidence']
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(zip(columns, row)) for row in rows])


# ============================================================================
# PROCUREMENT RECOMMENDATIONS APIs
# ============================================================================

@app.route('/procurement/recommendations', methods=['GET'])
def get_procurement_recommendations():
    """Get all procurement recommendations"""
    priority = request.args.get('priority', None)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            pr.recommendation_id,
            p.ProductName,
            c.CategoryName,
            pr.recommended_quantity,
            pr.reason,
            pr.priority,
            pr.status,
            pr.created_date,
            COALESCE(SUM(i.quantity), 0) as current_stock
        FROM procurement_recommendations pr
        JOIN products p ON pr.product_id = p.ProductID
        JOIN categories c ON p.CategoryID = c.CategoryID
        LEFT JOIN inventory i ON p.ProductID = i.product_id
        WHERE pr.status = 'PENDING'
    """
    
    if priority:
        query += f" AND pr.priority = '{priority.upper()}'"
    
    query += """
        GROUP BY pr.recommendation_id
        ORDER BY 
            CASE pr.priority 
                WHEN 'HIGH' THEN 1 
                WHEN 'MEDIUM' THEN 2 
                WHEN 'LOW' THEN 3 
            END,
            pr.created_date DESC
    """
    
    cursor.execute(query)
    
    columns = ['recommendation_id', 'product_name', 'category', 'recommended_quantity',
               'reason', 'priority', 'status', 'created_date', 'current_stock']
    rows = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'total_recommendations': len(rows),
        'filter_priority': priority,
        'recommendations': [dict(zip(columns, row)) for row in rows]
    })


@app.route('/procurement/stats', methods=['GET'])
def get_procurement_stats():
    """Get procurement statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Priority breakdown
    cursor.execute("""
        SELECT priority, COUNT(*), SUM(recommended_quantity)
        FROM procurement_recommendations
        WHERE status = 'PENDING'
        GROUP BY priority
    """)
    priority_stats = [{'priority': row[0], 'count': row[1], 'total_units': row[2]} 
                      for row in cursor.fetchall()]
    
    # Total recommendations
    cursor.execute("SELECT COUNT(*) FROM procurement_recommendations WHERE status = 'PENDING'")
    total = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total_pending': total,
        'priority_breakdown': priority_stats
    })


# ============================================================================
# PROCUREMENT CART/APPROVAL APIs
# ============================================================================

def _ensure_po_tables(cursor):
    """Create purchase order tables if missing (idempotent)."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_orders (
            po_id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL DEFAULT 'DRAFT',
            created_date TEXT NOT NULL DEFAULT (datetime('now'))
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_order_items (
            poi_id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id)
        )
    ''')

def _get_or_create_draft_po(cursor):
    cursor.execute("SELECT po_id FROM purchase_orders WHERE status='DRAFT' ORDER BY po_id DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO purchase_orders(status) VALUES('DRAFT')")
    return cursor.lastrowid


@app.route('/procurement/recommendations/<int:rec_id>/approve', methods=['POST'])
def approve_recommendation(rec_id):
    """Approve a procurement recommendation and add it to the draft PO (cart)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        _ensure_po_tables(cursor)

        # Fetch recommendation
        cursor.execute('''
            SELECT recommendation_id, product_id, recommended_quantity, status
            FROM procurement_recommendations
            WHERE recommendation_id = ?
        ''', (rec_id,))
        rec = cursor.fetchone()
        if not rec:
            return jsonify({'error': 'Recommendation not found'}), 404

        _, product_id, qty, status = rec

        # Optional quantity override from request body
        try:
            body = request.get_json(silent=True) or {}
        except Exception:
            body = {}
        override_qty = body.get('quantity') if isinstance(body, dict) else None
        if override_qty is not None:
            try:
                override_qty = int(override_qty)
            except Exception:
                override_qty = None

        # Update status to APPROVED if pending
        if status == 'PENDING':
            cursor.execute("UPDATE procurement_recommendations SET status='APPROVED' WHERE recommendation_id=?", (rec_id,))

        # Determine quantity to add (override > recommended)
        add_qty = None
        if override_qty is not None and override_qty > 0:
            add_qty = override_qty
        elif qty and qty > 0:
            add_qty = qty

        # Add to cart if there is a quantity to order (>0)
        if add_qty and add_qty > 0:
            po_id = _get_or_create_draft_po(cursor)
            # If item already in cart, increase quantity
            cursor.execute('''
                SELECT poi_id, quantity FROM purchase_order_items 
                WHERE po_id=? AND product_id=?
            ''', (po_id, product_id))
            existing = cursor.fetchone()
            if existing:
                poi_id, existing_qty = existing
                cursor.execute('UPDATE purchase_order_items SET quantity=? WHERE poi_id=?', (existing_qty + add_qty, poi_id))
            else:
                cursor.execute('INSERT INTO purchase_order_items(po_id, product_id, quantity) VALUES(?, ?, ?)', (po_id, product_id, add_qty))

        # Return updated cart summary
        cursor.execute("""
            SELECT po.po_id, po.status, COUNT(poi.poi_id) as items, COALESCE(SUM(poi.quantity),0) as total_units
            FROM purchase_orders po
            LEFT JOIN purchase_order_items poi ON po.po_id = poi.po_id
            WHERE po.status='DRAFT'
            GROUP BY po.po_id
            ORDER BY po.po_id DESC
            LIMIT 1
        """)
        cart = cursor.fetchone()
        conn.commit()

        if not cart:
            return jsonify({'cart': None, 'message': 'Approved'}), 200

        return jsonify({
            'cart': {
                'po_id': cart[0],
                'status': cart[1],
                'items': cart[2],
                'total_units': cart[3]
            },
            'message': 'Approved and added to cart' if (add_qty and add_qty>0) else 'Approved'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/procurement/cart', methods=['GET'])
def get_cart():
    """Return current draft purchase order (cart) with items."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        _ensure_po_tables(cursor)
        cursor.execute("SELECT po_id FROM purchase_orders WHERE status='DRAFT' ORDER BY po_id DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return jsonify({'cart': None})
        po_id = row[0]
        cursor.execute('''
            SELECT poi.poi_id, poi.product_id, p.ProductName, poi.quantity
            FROM purchase_order_items poi
            JOIN products p ON poi.product_id = p.ProductID
            WHERE poi.po_id=?
            ORDER BY poi.poi_id
        ''', (po_id,))
        items = [{'item_id': r[0], 'product_id': r[1], 'product_name': r[2], 'quantity': r[3]} for r in cursor.fetchall()]
        return jsonify({'cart': {'po_id': po_id, 'status': 'DRAFT', 'items': items, 'total_items': len(items), 'total_units': sum(i['quantity'] for i in items)}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/procurement/cart/checkout', methods=['POST'])
def checkout_cart():
    """Submit the current draft PO and mark approved recommendations as ORDERED where applicable."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        _ensure_po_tables(cursor)
        cursor.execute("SELECT po_id FROM purchase_orders WHERE status='DRAFT' ORDER BY po_id DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return jsonify({'message': 'Cart empty'}), 200
        po_id = row[0]

        # Submit PO
        cursor.execute("UPDATE purchase_orders SET status='SUBMITTED' WHERE po_id=?", (po_id,))

        # Optionally mark recommendations as ORDERED for product_ids present in the cart
        cursor.execute('SELECT DISTINCT product_id FROM purchase_order_items WHERE po_id=?', (po_id,))
        product_ids = [r[0] for r in cursor.fetchall()]
        if product_ids:
            cursor.execute(
                f"UPDATE procurement_recommendations SET status='ORDERED' WHERE status IN ('PENDING','APPROVED') AND product_id IN ({','.join(['?']*len(product_ids))})",
                product_ids
            )

        conn.commit()
        return jsonify({'message': 'Purchase Order submitted', 'po_id': po_id})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ============================================================================
# CUSTOMER CART CHECKOUT API
# ============================================================================

@app.route('/customer/checkout', methods=['POST'])
def customer_checkout():
    """Record cart items as sales for a given customer.

    Request JSON:
    {
      "customer_id": <int>,
      "items": [{"product_id": <int>, "quantity": <int>}, ...]
    }
    """
    data = request.get_json(silent=True) or {}
    customer_id = data.get('customer_id')
    items = data.get('items') or []

    if not isinstance(customer_id, int) or customer_id <= 0:
        return jsonify({'error': 'Invalid or missing customer_id'}), 400
    if not isinstance(items, list) or not items:
        return jsonify({'error': 'No items to checkout'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Validate customer exists
        cursor.execute('SELECT 1 FROM customers WHERE CustomerID=?', (customer_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Customer not found'}), 404

        # Insert each cart line as a sale
        total_amount = 0.0
        total_qty = 0
        lines = []
        for line in items:
            try:
                pid = int(line.get('product_id'))
                qty = int(line.get('quantity'))
            except Exception:
                return jsonify({'error': 'Invalid item format'}), 400
            if pid <= 0 or qty <= 0:
                return jsonify({'error': 'Invalid product or quantity'}), 400

            # Get price to compute amount
            cursor.execute('SELECT Price, ProductName FROM products WHERE ProductID=?', (pid,))
            prod = cursor.fetchone()
            if not prod:
                return jsonify({'error': f'Product not found: {pid}'}), 404
            price, pname = prod[0], prod[1]

            cursor.execute(
                """
                INSERT INTO sales (SalesDate, ProductID, Quantity, SalesPersonID, CustomerID)
                VALUES (datetime('now'), ?, ?, NULL, ?)
                """,
                (pid, qty, customer_id)
            )
            line_amount = float(price) * qty
            total_amount += line_amount
            total_qty += qty
            lines.append({'product_id': pid, 'product_name': pname, 'quantity': qty, 'unit_price': float(price), 'line_total': line_amount})

        conn.commit()
        return jsonify({'message': 'Checkout successful', 'customer_id': customer_id, 'total_quantity': total_qty, 'total_amount': total_amount, 'lines': lines})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'Shelfware API Server is running',
        'endpoints': {
            'admin_login': '/admin-login',
            'customer_login': '/customer-login', 
            'customer_signup': '/customer-signup',
            'check_username': '/check-username',
            'products': '/products',
            'categories': '/categories',
            'product_details': '/product/<id>',
            'inventory_stock': '/inventory/stock-levels',
            'inventory_expiring': '/inventory/expiring-soon',
            'suppliers': '/suppliers',
            'forecasts': '/forecasts/product/<id>',
            'procurement': '/procurement/recommendations'
        }
    })

@app.route('/', methods=['GET'])
def home():
    """Home endpoint with API information"""
    return jsonify({
        'message': 'Shelfware - Shelf-Aware Grocery Inventory System',
        'version': '2.0',
        'description': 'Sales-Driven Forecasting & Market-Aligned Procurement',
        'endpoints': {
            'authentication': [
                'POST /admin-login - Admin authentication',
                'POST /customer-login - Customer authentication',
                'POST /customer-signup - Customer registration',
                'POST /check-username - Username availability'
            ],
            'products': [
                'GET /products - Get products with filtering/pagination',
                'GET /categories - Get all categories',
                'GET /cities - Get all cities',
                'GET /product/<id> - Get product details'
            ],
            'inventory': [
                'GET /inventory/stock-levels - Current stock for all products',
                'GET /inventory/expiring-soon?days=7 - Stock expiring soon',
                'GET /inventory/expired - Already expired stock',
                'GET /inventory/product/<id> - Inventory batches for product',
                'GET /suppliers - All suppliers with stats'
            ],
            'forecasting': [
                'GET /forecasts/product/<id>?days=30 - Demand forecast for product',
                'GET /forecasts/summary - Top 50 products by predicted demand'
            ],
            'procurement': [
                'GET /procurement/recommendations?priority=HIGH - Procurement recommendations',
                'GET /procurement/stats - Procurement statistics'
            ],
            'customer': [
                'POST /customer/checkout - Submit a customer cart as sales'
            ],
            'admin': [
                'GET /admin/dashboard-stats - Dashboard KPIs',
                'GET /admin/recent-sales - Recent sales transactions',
                'GET /admin/products - Admin product management'
            ],
            'system': [
                'GET /health - Health check',
                'GET / - API documentation'
            ]
        }
    })

# ============================================================================
# MAIN APPLICATION
# ============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("Starting Shelfware - Shelf-Aware Grocery Inventory System")
    print("=" * 70)
    print("\nAvailable API endpoints:")
    print("\nAuthentication:")
    print("   - POST /admin-login - Admin authentication")
    print("   - POST /customer-login - Customer authentication")
    print("   - POST /customer-signup - Customer registration")
    print("   - POST /check-username - Username availability")
    print("\nProducts & Categories:")
    print("   - GET /products - Get products with filtering/pagination")
    print("   - GET /categories - Get all categories")
    print("   - GET /cities - Get all cities")
    print("   - GET /product/<id> - Get product details")
    print("\nInventory Management:")
    print("   - GET /inventory/stock-levels - Current stock for all products")
    print("   - GET /inventory/expiring-soon?days=7 - Stock expiring soon")
    print("   - GET /inventory/expired - Already expired stock")
    print("   - GET /inventory/product/<id> - Inventory batches for product")
    print("   - GET /suppliers - All suppliers with statistics")
    print("\nDemand Forecasting:")
    print("   - GET /forecasts/product/<id>?days=30 - Demand forecast for product")
    print("   - GET /forecasts/summary - Top 50 products by predicted demand")
    print("\nSmart Procurement:")
    print("   - GET /procurement/recommendations?priority=HIGH - Get recommendations")
    print("   - GET /procurement/stats - Procurement statistics")
    print("\nCustomer:")
    print("   - POST /customer/checkout - Submit a customer cart as sales")
    print("\nAdmin Dashboard:")
    print("   - GET /admin/dashboard-stats - Dashboard KPIs")
    print("   - GET /admin/recent-sales - Recent sales transactions")
    print("   - GET /admin/products - Admin product management")
    print("\nSystem:")
    print("   - GET /health - Health check")
    print("   - GET / - API documentation")
    print("=" * 70)
    print("Server running on http://127.0.0.1:5000")
    print("=" * 70 + "\n")
    
    app.run(port=5000, debug=True, host='127.0.0.1')