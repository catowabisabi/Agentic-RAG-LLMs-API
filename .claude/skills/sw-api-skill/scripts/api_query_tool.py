"""
SolidWorks API Documentation Query Tool
====================================
Agent Skill for extracting SolidWorks API information from database
Returns structured data for agent to use in code generation
"""

import sqlite3
import argparse
import json

def query_api_documentation(search_terms, db_path="asset/sw_api_doc.db"):
    """
    查詢 SolidWorks API 文檔資料庫
    返回結構化的 API 信息給 Agent 使用
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        results = {
            'search_terms': search_terms,
            'documents': [],
            'code_examples': [],
            'api_methods': [],
            'parameters': []
        }
        
        for term in search_terms:
            # 查詢文檔
            cursor.execute("""
                SELECT title, interface_name, doc_type, description, full_text
                FROM documents 
                WHERE title LIKE ? OR interface_name LIKE ? OR full_text LIKE ?
                LIMIT 5
            """, (f'%{term}%', f'%{term}%', f'%{term}%'))
            
            docs = cursor.fetchall()
            for doc in docs:
                results['documents'].append({
                    'title': doc[0],
                    'interface': doc[1],
                    'type': doc[2],
                    'description': doc[3],
                    'content': doc[4][:1000] if doc[4] else ""
                })
            
            # 查詢代碼範例
            cursor.execute("""
                SELECT ce.title, ce.language, ce.code, d.title as doc_title
                FROM code_examples ce
                JOIN documents d ON ce.doc_id = d.id
                WHERE ce.code LIKE ? OR ce.title LIKE ?
                LIMIT 3
            """, (f'%{term}%', f'%{term}%'))
            
            examples = cursor.fetchall()
            for example in examples:
                results['code_examples'].append({
                    'title': example[0],
                    'language': example[1],
                    'code': example[2],
                    'source_doc': example[3]
                })
            
            # 查詢 API 方法和參數
            cursor.execute("""
                SELECT chunk_type, content, context_prefix
                FROM chunks c
                JOIN documents d ON c.doc_id = d.id
                WHERE c.content LIKE ? AND chunk_type IN ('syntax', 'parameters', 'description')
                LIMIT 5
            """, (f'%{term}%',))
            
            chunks = cursor.fetchall()
            for chunk in chunks:
                if chunk[0] == 'syntax':
                    results['api_methods'].append({
                        'method': term,
                        'syntax': chunk[1],
                        'context': chunk[2]
                    })
                elif chunk[0] == 'parameters':
                    results['parameters'].append({
                        'method': term,
                        'parameters': chunk[1],
                        'context': chunk[2]
                    })
        
        conn.close()
        return results
        
    except Exception as e:
        return {
            'error': str(e),
            'search_terms': search_terms,
            'documents': [],
            'code_examples': [],
            'api_methods': [],
            'parameters': []
        }

def main():
    parser = argparse.ArgumentParser(description='SolidWorks API Documentation Query Tool')
    parser.add_argument('--search', '-s', nargs='+', required=True, help='Search terms for API methods')
    parser.add_argument('--output', '-o', choices=['json', 'text'], default='text', help='Output format')
    
    args = parser.parse_args()
    
    # 查詢 API 信息
    results = query_api_documentation(args.search)
    
    if args.output == 'json':
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        # 文字格式輸出
        print("="*60)
        print("SolidWorks API Documentation Query Results")
        print("="*60)
        
        print(f"\n🔍 Search Terms: {', '.join(results['search_terms'])}")
        
        if results.get('error'):
            print(f"❌ Error: {results['error']}")
            return
        
        print(f"\n📚 Found {len(results['documents'])} documents")
        for i, doc in enumerate(results['documents'], 1):
            print(f"\n--- Document {i} ---")
            print(f"Title: {doc['title']}")
            print(f"Interface: {doc['interface']}")
            print(f"Type: {doc['type']}")
            print(f"Description: {doc['description'][:200]}...")
        
        print(f"\n💻 Found {len(results['code_examples'])} code examples")
        for i, example in enumerate(results['code_examples'], 1):
            print(f"\n--- Example {i} ---")
            print(f"Title: {example['title']}")
            print(f"Language: {example['language']}")
            print(f"Code: {example['code'][:300]}...")
        
        print(f"\n⚙️ Found {len(results['api_methods'])} API methods")
        for i, method in enumerate(results['api_methods'], 1):
            print(f"\n--- Method {i} ---")
            print(f"Method: {method['method']}")
            print(f"Syntax: {method['syntax'][:200]}...")
        
        print(f"\n📋 Found {len(results['parameters'])} parameter definitions")
        for i, param in enumerate(results['parameters'], 1):
            print(f"\n--- Parameter {i} ---")
            print(f"Method: {param['method']}")
            print(f"Parameters: {param['parameters'][:200]}...")

if __name__ == "__main__":
    main()