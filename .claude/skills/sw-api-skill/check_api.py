import sqlite3

def check_api():
    conn = sqlite3.connect('asset/sw_api_doc.db')
    cursor = conn.cursor()
    
    # 查詢 FeatureExtrusion 相關的文檔
    cursor.execute('SELECT title, full_text FROM documents WHERE title LIKE ? LIMIT 3', ('%FeatureExtrusion%',))
    results = cursor.fetchall()
    
    for i, (title, text) in enumerate(results):
        print(f'=== {title} ===')
        print(text[:800])
        print('='*50)
        
    # 查詢代碼範例
    cursor.execute('SELECT title, code FROM code_examples WHERE code LIKE ? LIMIT 2', ('%FeatureExtrusion2%',))
    examples = cursor.fetchall()
    
    print('\n=== 代碼範例 ===')
    for title, code in examples:
        print(f'--- {title} ---')
        print(code[:500])
        print('-'*30)
    
    conn.close()

if __name__ == "__main__":
    check_api()