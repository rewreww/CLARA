import unittest
from unittest.mock import Mock, patch

import llm_client as service
import guideline_grounding as grounding
from rag import retriever
from rag.lexical import PassageIndex

QUESTION = 'What antihypertensives should be used according to what comorbid conditions are present?'


class RetrievalFocusTests(unittest.TestCase):
    def test_new_question_does_not_inherit_measurement_topic(self):
        history = [{'role': 'doctor', 'content': 'How is ambulatory blood pressure measured?'}]
        self.assertEqual(service.general_retrieval_query(QUESTION, history), QUESTION)
        self.assertEqual(service.general_retrieval_query('What antihypertensives are safe while breast feeding?', history),
                         'What antihypertensives are safe while breast feeding?')
        followup = service.general_retrieval_query('What about treatment?', history)
        self.assertTrue(followup.startswith('What about treatment?'))
        self.assertIn('ambulatory', followup)

    def test_condition_comparison_allows_multiple_citations(self):
        self.assertFalse(grounding.wants_brief_answer(QUESTION))
        self.assertTrue(grounding.wants_brief_answer('What is hypertension?'))
        self.assertTrue(retriever.is_management_query(QUESTION))

    def test_breastfeeding_word_variants_match_lactation_evidence(self):
        index = PassageIndex({'documents': ['Lactating women and antihypertensive medication.',
                                             'Antihypertensive treatment for resistant hypertension.']})
        self.assertEqual(index.search('What antihypertensives are safe while breast feeding?')[0][0], 0)

    def test_keyword_match_recovers_passage_excluded_by_old_tags(self):
        records = {'ids': ['measurement', 'drug-selection'],
            'documents': ['Blood pressure measurement cuff sizing ambulatory monitoring.',
                          'Background. ' * 400 + 'Antihypertensive drug selection depends on comorbid disease and compelling indications.'],
            'metadatas': [{'source': 'local', 'page': 75, 'country': 'philippines'},
                          {'source': 'other', 'page': 27, 'country': 'international',
                           'diagnosis_category': 'heart_failure', 'is_recommendation': False}]}
        index = PassageIndex(records)
        self.assertEqual(index.search(QUESTION)[0][0], 1)
        self.assertEqual(index.search('quuxneverfound'), [])
        collection = Mock()
        collection.count.return_value = 2
        collection.query.return_value = {'ids': [['measurement']], 'documents': [[records['documents'][0]]],
            'metadatas': [[records['metadatas'][0]]], 'distances': [[.8]]}
        with patch.object(retriever.chromadb, 'PersistentClient') as client, \
             patch.object(retriever, '_passage_index', return_value=index), \
             patch.object(retriever, 'get_embedding', return_value=[0.1]) as embed:
            client.return_value.get_collection.return_value = collection
            results = retriever.retrieve(QUESTION, diagnosis_hint='hypertension', only_recommendations=True)
        self.assertEqual(results[0]['chunk_id'], 'drug-selection')
        self.assertNotIn('where', collection.query.call_args.kwargs)
        embed.assert_called_once_with(QUESTION)

    def test_bundle_preserves_relevance_before_geography(self):
        chunks = [{'source': name, 'page': i + 1, 'text': name, 'retrieval_score': 10 - i,
                   'is_philippine': i > 0} for i, name in enumerate(['best', 'local', 'third', 'fourth', 'fifth', 'sixth'])]
        def verified(chunk):
            return {'source': chunk['source'], 'title': chunk['source'], 'pdf_file': chunk['source'] + '.pdf',
                    'page': chunk['page'], 'page_end': chunk['page'], 'pages': [chunk['page']]}
        with patch.object(service, 'retrieve', return_value=chunks), \
             patch.object(grounding, 'verified_source', side_effect=verified):
            _, sources = service.build_guideline_bundle(QUESTION)
        self.assertEqual(sources[0]['source'], 'best')
        self.assertEqual(len(sources), 6)

    def test_verified_anchor_keeps_next_page_answer(self):
        chunks = [{'source': 'guide', 'page': 64, 'text': 'Question on lactation', 'chunk_id': 'q'}]
        neighbor = {'source': 'guide', 'page': 65, 'text': 'The answer continues here', 'chunk_id': 'a'}
        def verified(chunk):
            return {'source': 'guide', 'title': 'Guide', 'pdf_file': 'guide.pdf',
                    'page': chunk['page'], 'page_end': chunk['page'], 'pages': [chunk['page']]}
        with patch.object(service, 'retrieve', return_value=chunks), \
             patch.object(service, 'following_passage', return_value=neighbor) as following, \
             patch.object(grounding, 'verified_source', side_effect=verified):
            context, sources = service.build_guideline_bundle('Which drugs are safe while breastfeeding?')
        self.assertEqual([source['page'] for source in sources], [64, 65])
        self.assertIn('The answer continues here', context)
        following.assert_called_once()


if __name__ == '__main__':
    unittest.main()
