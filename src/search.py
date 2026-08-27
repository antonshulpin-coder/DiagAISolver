"""Локальный детерминированный поиск с ранжированием.

Алгоритм:
1. Запрос разбивается на уникальные термы ( нижний регистр, множественные пробелы убираются).
2. Для каждого терма вычисляется.score по полям записи:
   - title (точное совпадение / contains) —ighest weight
   - tags   (точное совпадение / contains) —edium weight
   - text   (contains)                     —ower weight
3. Итоговый score = сумма по термам + бонус за количество уникальных термов.
4. Результаты сортируются по score  убыванию.

Score доступен в возвращаемых данных, но не обязателен для CLI.
"""

TITLE_EXACT = 10.0
TITLE_CONTAINS = 6.0
TAG_EXACT = 8.0
TAG_CONTAINS = 5.0
TEXT_CONTAINS = 3.0
TERM_COVERAGE_BONUS = 2.0


def _normalize(text):
    return " ".join(text.lower().split())


def _tokenize(query):
    normalized = _normalize(query)
    return sorted(set(normalized.split()))


def _field_exact_score(field_value, term):
    if _normalize(field_value) == term:
        return 1.0
    return 0.0


def _field_contains_score(field_value, term):
    if term in _normalize(field_value):
        return 1.0
    return 0.0


def _score_record(record, terms):
    title = record.get("title", "")
    text = record.get("text", "")
    tags = record.get("tags", [])

    score = 0.0
    matched_terms = 0

    for term in terms:
        term_score = 0.0

        # title
        term_score += _field_exact_score(title, term) * TITLE_EXACT
        term_score += _field_contains_score(title, term) * TITLE_CONTAINS

        # tags
        for tag in tags:
            term_score += _field_exact_score(tag, term) * TAG_EXACT
            term_score += _field_contains_score(tag, term) * TAG_CONTAINS

        # text
        term_score += _field_contains_score(text, term) * TEXT_CONTAINS

        if term_score > 0:
            matched_terms += 1
            score += term_score

    if terms:
        coverage = matched_terms / len(terms)
        score += coverage * TERM_COVERAGE_BONUS * len(terms)

    return round(score, 4), matched_terms


def rank_records(query, records, min_coverage=1.0):
    """Возвращает список (record, score) отсортированный по score  убыванию.

    min_coverage: минимальная доля термов, которые должны совпасть (0.0-1.0).
                  По умолчанию 1.0 — все термы должны быть найдены.
    """
    terms = _tokenize(query)
    if not terms:
        return []

    scored = []
    for record in records:
        score, matched = _score_record(record, terms)
        coverage = matched / len(terms) if terms else 0
        if score > 0 and coverage >= min_coverage:
            scored.append((record, score))

    scored.sort(key=lambda x: (-x[1], x[0].get("created_at", "")))
    return scored
