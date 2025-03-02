import sqlite3
import json
from datetime import datetime

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect('comparisons.db')
    c = conn.cursor()
    
    # Check if the table already exists
    c.execute('''
        SELECT count(name) 
        FROM sqlite_master 
        WHERE type='table' AND name='comparisons'
    ''')
    
    # Create table only if it doesn't exist
    if c.fetchone()[0] == 0:
        c.execute('''
            CREATE TABLE comparisons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url1 TEXT NOT NULL,
                url2 TEXT NOT NULL,
                content1 TEXT,
                content2 TEXT,
                css1 TEXT,
                css2 TEXT,
                comparison TEXT,
                error1 TEXT,
                error2 TEXT,
                broken_links1 TEXT,
                broken_links2 TEXT,
                images1 TEXT,
                images2 TEXT,
                results1 TEXT,
                results2 TEXT,
                links1 TEXT,
                links2 TEXT,
                links_comparison TEXT,
                text_comparison TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        print("Database table 'comparisons' created successfully")
    else:
        print("Database table 'comparisons' already exists")
    
    conn.close()

def store_comparison(data):
    """Store comparison results in the database"""
    conn = sqlite3.connect('comparisons.db')
    c = conn.cursor()
    
    # Convert complex data structures to JSON strings
    serialized_data = {
        'url1': data['url1'],
        'url2': data['url2'],
        'content1': data['content1'],
        'content2': data['content2'],
        'css1': json.dumps(data['css1']),
        'css2': json.dumps(data['css2']),
        'comparison': json.dumps(data['comparison']) if data['comparison'] else None,
        'error1': data['error1'],
        'error2': data['error2'],
        'broken_links1': json.dumps(data['broken_links1']),
        'broken_links2': json.dumps(data['broken_links2']),
        'images1': json.dumps(data['images1']),
        'images2': json.dumps(data['images2']),
        'results1': json.dumps(data['results1']),
        'results2': json.dumps(data['results2']),
        'links1': json.dumps(data['links1']),
        'links2': json.dumps(data['links2']),
        'links_comparison': json.dumps(data['links_comparison']),
        'text_comparison': json.dumps(data['text_comparison'])
    }
    
    # Insert the data
    c.execute('''
        INSERT INTO comparisons (
            url1, url2, content1, content2, css1, css2, comparison,
            error1, error2, broken_links1, broken_links2, images1, images2,
            results1, results2, links1, links2, links_comparison, text_comparison
        ) VALUES (
            :url1, :url2, :content1, :content2, :css1, :css2, :comparison,
            :error1, :error2, :broken_links1, :broken_links2, :images1, :images2,
            :results1, :results2, :links1, :links2, :links_comparison, :text_comparison
        )
    ''', serialized_data)
    
    conn.commit()
    conn.close()

def get_recent_comparisons(limit=10):
    """Get the most recent comparisons"""
    conn = sqlite3.connect('comparisons.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT id, url1, url2, timestamp 
        FROM comparisons 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (limit,))
    
    results = c.fetchall()
    conn.close()
    
    return results

def get_comparison(comparison_id):
    """Get a specific comparison by ID"""
    conn = sqlite3.connect('comparisons.db')
    c = conn.cursor()
    
    c.execute('SELECT * FROM comparisons WHERE id = ?', (comparison_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        # Convert column names and values into a dictionary
        columns = [description[0] for description in c.description]
        data = dict(zip(columns, result))
        
        # Deserialize JSON strings back to Python objects
        json_fields = ['css1', 'css2', 'comparison', 'broken_links1', 'broken_links2',
                      'images1', 'images2', 'results1', 'results2', 'links1', 'links2',
                      'links_comparison', 'text_comparison']
        
        for field in json_fields:
            if data[field]:
                data[field] = json.loads(data[field])
        
        return data
    
    return None 