"""Small, cached BM25 index over stored passages; no second model call."""
import math
import re
from collections import Counter

STOPWORDS = set('a an the of to in on for and or with without while during is are was were be been being do does did can could should would what which how when where why who according present used use among patient patients condition conditions'.split())
STOPWORDS.update('someone person people choice treat treatment please tell give'.split())
ALIASES = {'antihypertensives': 'antihypertensive', 'comorbidities': 'comorbid',
           'comorbidity': 'comorbid', 'medications': 'medication', 'drugs': 'drug',
           'indications': 'indication', 'diseases': 'disease', 'treatments': 'treatment',
           'lactating': 'breastfeeding', 'lactation': 'breastfeeding'}


def tokens(text):
    # PDF line wraps should not hide hyphenated clinical terms.
    text = re.sub(r'(?<=\w)-\s*\n\s*(?=\w)', '', text.lower())
    text = re.sub(r'\bbreast[\s-]+feeding\b', 'breastfeeding', text)
    # Retrieval synonyms only: this does not equate severity/stage or add a
    # clinical condition such as albuminuria to the user's question.
    text = re.sub(r'\bchronic\s+(?:renal\s+(?:failure|disease)|kidney\s+disease)\b', 'ckd', text)
    text = re.sub(r'\brenal\b', 'kidney', text)
    return [ALIASES.get(word, word) for word in re.findall(r'[a-z][a-z0-9]+', text)
            if word not in STOPWORDS]


class PassageIndex:
    def __init__(self, records):
        self.records = records
        self.counts = [Counter(tokens(text)) for text in records['documents']]
        self.lengths = [sum(count.values()) for count in self.counts]
        self.average = sum(self.lengths) / max(len(self.lengths), 1) or 1
        frequency = Counter(term for count in self.counts for term in count)
        self.idf = {term: math.log(1 + (len(self.counts) - n + .5) / (n + .5))
                    for term, n in frequency.items()}

    def search(self, query, limit=30):
        original = set(tokens(query))
        terms = {term: 1.0 for term in original}
        # Vocabulary expansion, not medication recommendations.
        if 'antihypertensive' in original:
            terms.update({term: terms.get(term, .3) for term in ('hypertension', 'drug', 'medication')})
        if 'comorbid' in original:
            terms.update({term: terms.get(term, .3) for term in ('compelling', 'indication', 'disease')})
        ranked = []
        for i, counts in enumerate(self.counts):
            if not original.intersection(counts):
                continue
            score = 0.0
            for term, weight in terms.items():
                frequency = counts.get(term, 0)
                if frequency:
                    # Emphasize discriminating clinical terms over repeated
                    # generic treatment words (e.g. lactation versus medication).
                    score += weight * self.idf[term] * frequency * 2.5 / (
                        frequency + 1.5 * (.25 + .75 * self.lengths[i] / self.average))
            if score:
                ranked.append((i, score))
        return sorted(ranked, key=lambda item: item[1], reverse=True)[:limit]
