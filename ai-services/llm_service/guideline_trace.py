"""Opt-in, request-local evaluation tracing. Nothing is stored by normal chat."""
from contextvars import ContextVar
from contextlib import contextmanager
from copy import deepcopy

_trace = ContextVar('guideline_evaluation_trace', default=None)


@contextmanager
def capture():
    trace = {'passages': [], 'generation_calls': []}
    token = _trace.set(trace)
    try:
        yield trace
    finally:
        _trace.reset(token)


def passage(chunk):
    trace = _trace.get()
    if trace is not None:
        trace['passages'].append(deepcopy(chunk))


def validation(answer, accepted):
    trace = _trace.get()
    if trace is not None:
        trace.setdefault('answer_validation', []).append({'raw_answer': answer, 'accepted': accepted})


def generation(prompt, provider):
    trace = _trace.get()
    if trace is None:
        return
    # Other adapters may truncate input or fall back to another model. Until
    # instrumented at their token boundary, never claim exact context for them.
    if provider not in {'groq', 'openrouter'}:
        raise ValueError('Exact guideline evaluation capture supports the Groq and OpenRouter adapters only.')
    cursor = 0
    for chunk in trace['passages']:
        text = str(chunk.get('text') or '').strip()
        start = prompt.find(text, cursor)
        if not text or start < 0:
            raise ValueError('Captured passage is not present in the generation prompt in supplied order.')
        cursor = start + len(text)
    trace['generation_calls'].append({'prompt': prompt, 'provider': provider,
                                       'passages': deepcopy(trace['passages'])})
