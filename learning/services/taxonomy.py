"""Skill taxonomy helpers: name normalisation, prerequisite graph checks and ordering."""
import heapq
import re

from learning.taxonomy_data import SKILLS

_SUFFIXES = (' programming', ' language', ' framework', ' library', ' basics', ' fundamentals', ' concepts')


def normalize_key(name):
    key = re.sub(r'[^a-z0-9+#./& ]', ' ', str(name).lower())
    return re.sub(r'\s+', ' ', key).strip()


def build_index(skills):
    """Map every name, slug and alias (normalised) to its Skill."""
    index = {}
    for skill in skills:
        for key in [skill.slug, skill.name, skill.slug.replace('-', ' '), *skill.aliases]:
            index.setdefault(normalize_key(key), skill)
    return index


def match_skill(name, index):
    """Return the canonical Skill for a free-text skill name, or None. Exact alias match only:
    unrelated skills are never merged just because they share a word."""
    key = normalize_key(name)
    if not key:
        return None
    if key in index:
        return index[key]
    for suffix in _SUFFIXES:
        if key.endswith(suffix) and key[: -len(suffix)] in index:
            return index[key[: -len(suffix)]]
    return None


def prerequisite_map(links):
    """links: iterable of (skill_id, prerequisite_id) -> {skill_id: {prereq ids}}"""
    graph = {}
    for skill_id, prereq_id in links:
        graph.setdefault(skill_id, set()).add(prereq_id)
    return graph


def find_cycle(graph):
    """Return a list of skill ids forming a cycle, or None. graph = {skill: {prerequisites}}"""
    WHITE, GREY, BLACK = 0, 1, 2
    colour, stack = {}, []

    def visit(node):
        colour[node] = GREY
        stack.append(node)
        for nxt in graph.get(node, ()):
            if colour.get(nxt, WHITE) == GREY:
                return stack[stack.index(nxt):] + [nxt]
            if colour.get(nxt, WHITE) == WHITE:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        colour[node] = BLACK
        return None

    for node in list(graph):
        if colour.get(node, WHITE) == WHITE:
            found = visit(node)
            if found:
                return found
    return None


def would_create_cycle(skill_id, prereq_id):
    from learning.models import SkillPrerequisite
    graph = prerequisite_map(SkillPrerequisite.objects.values_list('skill_id', 'prerequisite_id'))
    graph.setdefault(skill_id, set()).add(prereq_id)
    return find_cycle(graph) is not None


def all_prerequisites(skill_id, graph):
    """Every direct and indirect prerequisite of a skill."""
    seen, todo = set(), list(graph.get(skill_id, ()))
    while todo:
        node = todo.pop()
        if node not in seen:
            seen.add(node)
            todo.extend(graph.get(node, ()))
    return seen


def ordered_by_prerequisites(skill_ids, graph, priority):
    """Kahn's algorithm restricted to `skill_ids`: prerequisites always come first; among skills
    that are ready, higher `priority[id]` goes first."""
    ids = set(skill_ids)
    indeg = {s: len(graph.get(s, set()) & ids) for s in ids}
    dependents = {}
    for s in ids:
        for p in graph.get(s, set()) & ids:
            dependents.setdefault(p, []).append(s)
    ready = [(-priority.get(s, 0), s) for s in ids if indeg[s] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        _, s = heapq.heappop(ready)
        order.append(s)
        for d in dependents.get(s, []):
            indeg[d] -= 1
            if indeg[d] == 0:
                heapq.heappush(ready, (-priority.get(d, 0), d))
    # Anything left is part of a cycle (should not happen: the taxonomy is checked) - append it.
    order += sorted(ids - set(order))
    return order


def sync_taxonomy(Skill, SkillPrerequisite):
    """Upsert SKILLS into the database. Works with real models or migration (historical) models."""
    by_slug = {}
    for row in SKILLS:
        skill, _ = Skill.objects.update_or_create(slug=row['slug'], defaults={
            'name': row['name'], 'category': row['category'], 'aliases': [a.lower() for a in row.get('aliases', [])],
            'assessable_via': row.get('assessable_via', []), 'coding_topic': row.get('coding_topic', ''),
            'interview_type': row.get('interview_type', ''), 'description': row.get('description', ''),
        })
        by_slug[row['slug']] = skill
    for row in SKILLS:
        skill = by_slug[row['slug']]
        parent = by_slug.get(row.get('parent'))
        if skill.parent_id != (parent.id if parent else None):
            skill.parent = parent
            skill.save(update_fields=['parent'])
        for pre in row.get('prerequisites', []):
            SkillPrerequisite.objects.get_or_create(skill=skill, prerequisite=by_slug[pre])
    graph = prerequisite_map(SkillPrerequisite.objects.values_list('skill_id', 'prerequisite_id'))
    cycle = find_cycle(graph)
    if cycle:
        raise ValueError(f'Skill prerequisites contain a cycle: {cycle}')
