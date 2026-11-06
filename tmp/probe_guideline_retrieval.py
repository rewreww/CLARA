import os
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'ai-services'))
from rag.retriever import retrieve, infer_diagnosis_hint, is_management_query
import chromadb
collection = chromadb.PersistentClient(path=str(root / 'ai-services/rag/chroma_db')).get_collection('clara_guidelines')
records = collection.get(include=['documents','metadatas'])
for doc, meta in zip(records['documents'], records['metadatas']):
    if 'Management of Hypertension in the Philippines' in meta.get('source','') and meta.get('page') in [26,27,28,75]:
        print('INDEX',meta,'WORDS',len(doc.split()),flush=True)
question = 'What antihypertensives should be used according to what comorbid conditions are present?'
for query in [question, 'How should blood pressure be measured?\nWhen is ambulatory blood pressure monitoring recommended?\n'+question]:
    print('QUERY',query, 'HINT',infer_diagnosis_hint(query),'MANAGEMENT',is_management_query(query),flush=True)
    for item in retrieve(query, diagnosis_hint=infer_diagnosis_hint(query), only_recommendations=is_management_query(query),top_k=5):
        print('MATCH',item['source'],item['page'],item['relevance'],item['text'][:650],flush=True)
