"""
Seed data for the skill taxonomy. Loaded into the Skill / SkillPrerequisite tables by a data
migration and by `python manage.py sync_skills` (safe to run again; it upserts).

To add a skill: add a row here and run `python manage.py sync_skills`, or add it in the admin.
Fields: slug, name, category, parent, aliases, prerequisites, assessable_via, coding_topic, interview_type.
"""

MCQ, CODING, TECH = 'mcq', 'coding', 'technical'

SKILLS = [
    # ---------------------------------------------------------------- programming
    dict(slug='python', name='Python', category='programming', aliases=['python3', 'py'],
         assessable_via=[MCQ, TECH], interview_type='programming'),
    dict(slug='java', name='Java', category='programming', aliases=['core java', 'java 8', 'java se'],
         assessable_via=[MCQ, TECH], interview_type='programming'),
    dict(slug='cpp', name='C++', category='programming', aliases=['c++', 'cpp', 'c plus plus', 'stl'],
         assessable_via=[MCQ, TECH], interview_type='programming'),
    dict(slug='c', name='C', category='programming', aliases=['c language', 'c programming'],
         assessable_via=[MCQ, TECH], interview_type='programming'),
    dict(slug='javascript', name='JavaScript', category='programming', aliases=['js', 'es6', 'ecmascript'],
         assessable_via=[MCQ, TECH], interview_type='programming'),
    dict(slug='typescript', name='TypeScript', category='programming', aliases=['ts'], prerequisites=['javascript'],
         assessable_via=[MCQ, TECH], interview_type='programming'),

    # ---------------------------------------------------------------- DSA
    dict(slug='dsa', name='Data Structures & Algorithms', category='dsa',
         aliases=['data structures', 'algorithms', 'data structures and algorithms', 'ds and algo', 'ds&a',
                  'problem solving', 'competitive programming', 'dsa'],
         assessable_via=[MCQ, CODING, TECH], interview_type='dsa'),
    dict(slug='arrays', name='Arrays', category='dsa', parent='dsa', aliases=['array', 'prefix sums'],
         assessable_via=[MCQ, CODING, TECH], coding_topic='arrays', interview_type='dsa'),
    dict(slug='strings', name='Strings', category='dsa', parent='dsa', aliases=['string manipulation'],
         prerequisites=['arrays'], assessable_via=[MCQ, CODING, TECH], coding_topic='strings', interview_type='dsa'),
    dict(slug='hashing', name='Hashing', category='dsa', parent='dsa', aliases=['hash tables', 'hash maps', 'hashmap'],
         prerequisites=['arrays'], assessable_via=[MCQ, CODING, TECH], coding_topic='hashing', interview_type='dsa'),
    dict(slug='two-pointers', name='Two Pointers', category='dsa', parent='dsa', aliases=['two pointer'],
         prerequisites=['arrays'], assessable_via=[CODING, TECH], coding_topic='two pointers', interview_type='dsa'),
    dict(slug='sliding-window', name='Sliding Window', category='dsa', parent='dsa',
         prerequisites=['two-pointers', 'hashing'], assessable_via=[CODING, TECH], coding_topic='sliding window',
         interview_type='dsa'),
    dict(slug='binary-search', name='Binary Search', category='dsa', parent='dsa',
         aliases=['searching', 'searching and sorting', 'sorting'], prerequisites=['arrays'],
         assessable_via=[MCQ, CODING, TECH], coding_topic='binary search', interview_type='dsa'),
    dict(slug='linked-lists', name='Linked Lists', category='dsa', parent='dsa', aliases=['linked list'],
         prerequisites=['arrays'], assessable_via=[MCQ, TECH], interview_type='dsa'),
    dict(slug='stacks', name='Stacks', category='dsa', parent='dsa', aliases=['stack', 'monotonic stack'],
         prerequisites=['arrays'], assessable_via=[MCQ, CODING, TECH], coding_topic='stack', interview_type='dsa'),
    dict(slug='queues', name='Queues', category='dsa', parent='dsa', aliases=['queue', 'deque'],
         prerequisites=['arrays'], assessable_via=[MCQ, TECH], interview_type='dsa'),
    dict(slug='recursion', name='Recursion', category='dsa', parent='dsa', aliases=['backtracking'],
         prerequisites=['arrays'], assessable_via=[MCQ, CODING, TECH], coding_topic='backtracking', interview_type='dsa'),
    dict(slug='trees', name='Trees', category='dsa', parent='dsa', aliases=['tree', 'binary trees', 'bst', 'binary search tree'],
         prerequisites=['recursion', 'linked-lists'], assessable_via=[MCQ, TECH], interview_type='dsa'),
    dict(slug='heaps', name='Heaps', category='dsa', parent='dsa', aliases=['heap', 'priority queue'],
         prerequisites=['trees'], assessable_via=[MCQ, CODING, TECH], coding_topic='heaps', interview_type='dsa'),
    dict(slug='graphs', name='Graphs', category='dsa', parent='dsa', aliases=['graph', 'bfs', 'dfs', 'graph algorithms'],
         prerequisites=['trees', 'queues'], assessable_via=[MCQ, CODING, TECH], coding_topic='graphs', interview_type='dsa'),
    dict(slug='advanced-graphs', name='Advanced Graph Algorithms', category='dsa', parent='dsa',
         aliases=['shortest path', 'dijkstra', 'topological sort', 'minimum spanning tree'],
         prerequisites=['graphs', 'heaps'], assessable_via=[CODING, TECH], coding_topic='graphs', interview_type='dsa'),
    dict(slug='dynamic-programming', name='Dynamic Programming', category='dsa', parent='dsa', aliases=['dp', 'memoization'],
         prerequisites=['recursion'], assessable_via=[MCQ, CODING, TECH], coding_topic='dynamic programming',
         interview_type='dsa'),
    dict(slug='greedy', name='Greedy Algorithms', category='dsa', parent='dsa', aliases=['greedy', 'intervals'],
         prerequisites=['binary-search'], assessable_via=[MCQ, CODING, TECH], coding_topic='intervals', interview_type='dsa'),

    # ---------------------------------------------------------------- core CS
    dict(slug='oop', name='Object-Oriented Programming', category='core_cs',
         aliases=['oops', 'object oriented programming', 'object-oriented design', 'ood', 'design patterns'],
         assessable_via=[MCQ, TECH], interview_type='oop'),
    dict(slug='dbms', name='DBMS', category='core_cs',
         aliases=['database management systems', 'databases', 'database', 'rdbms', 'normalization',
                  'relational databases', 'relational database', 'relational database management systems'],
         assessable_via=[MCQ, TECH], interview_type='dbms'),
    dict(slug='sql', name='SQL', category='core_cs', aliases=['mysql', 'postgresql', 'postgres', 'sqlite', 'sql server', 'oracle sql'],
         prerequisites=['dbms'], assessable_via=[MCQ, TECH], interview_type='dbms'),
    dict(slug='operating-systems', name='Operating Systems', category='core_cs', aliases=['os', 'operating system'],
         assessable_via=[MCQ, TECH], interview_type='os'),
    dict(slug='computer-networks', name='Computer Networks', category='core_cs',
         aliases=['networking', 'cn', 'tcp/ip', 'http', 'networks'], assessable_via=[MCQ, TECH], interview_type='networks'),
    dict(slug='system-design', name='System Design', category='core_cs',
         aliases=['low level design', 'high level design', 'lld', 'hld', 'scalable systems', 'distributed systems'],
         prerequisites=['dbms', 'computer-networks', 'oop'], assessable_via=[TECH], interview_type='system_design'),

    # ---------------------------------------------------------------- web
    dict(slug='html', name='HTML', category='web', aliases=['html5'], assessable_via=[MCQ, TECH], interview_type='web'),
    dict(slug='css', name='CSS', category='web', aliases=['css3', 'tailwind', 'tailwind css', 'bootstrap', 'sass'],
         prerequisites=['html'], assessable_via=[MCQ, TECH], interview_type='web'),
    dict(slug='react', name='React', category='web', aliases=['react.js', 'reactjs', 'react js', 'next.js', 'nextjs'],
         prerequisites=['javascript', 'html', 'css'], assessable_via=[MCQ, TECH], interview_type='web'),
    dict(slug='nodejs', name='Node.js', category='web', aliases=['node', 'node js', 'express', 'express.js', 'expressjs'],
         prerequisites=['javascript'], assessable_via=[MCQ, TECH], interview_type='web'),
    dict(slug='rest-apis', name='REST APIs', category='web', aliases=['rest', 'restful apis', 'rest api', 'api development', 'apis', 'rest api design', 'api design',
                  'restful services', 'web apis'],
         prerequisites=['computer-networks'], assessable_via=[MCQ, TECH], interview_type='web'),
    dict(slug='django', name='Django', category='web', aliases=['django rest framework', 'drf'],
         prerequisites=['python', 'rest-apis'], assessable_via=[MCQ, TECH], interview_type='web'),

    # ---------------------------------------------------------------- tools and data
    dict(slug='git', name='Git', category='tools', aliases=['github', 'version control', 'gitlab'], assessable_via=[MCQ]),
    dict(slug='docker', name='Docker', category='tools', aliases=['containers', 'containerization'], assessable_via=[MCQ, TECH]),
    dict(slug='linux', name='Linux', category='tools', aliases=['unix', 'bash', 'shell scripting'], assessable_via=[MCQ]),
    dict(slug='cloud', name='Cloud Computing', category='tools', aliases=['aws', 'azure', 'gcp', 'google cloud'],
         assessable_via=[MCQ, TECH]),
    dict(slug='machine-learning', name='Machine Learning', category='data',
         aliases=['ml', 'deep learning', 'scikit-learn', 'tensorflow', 'pytorch'], prerequisites=['python'],
         assessable_via=[MCQ, TECH]),
]

# Coding round topic -> skill slug, used to turn coding results into skill evidence.
CODING_TOPIC_TO_SKILL = {
    'arrays': 'arrays', 'strings': 'strings', 'hashing': 'hashing', 'two pointers': 'two-pointers',
    'stack': 'stacks', 'monotonic stack': 'stacks', 'sliding window': 'sliding-window',
    'binary search': 'binary-search', 'intervals': 'greedy', 'prefix sums': 'arrays',
    'bfs/dfs on grids': 'graphs', 'graphs': 'graphs', 'dynamic programming': 'dynamic-programming',
    'heaps': 'heaps', 'backtracking': 'recursion', 'math': 'arrays',
}

# Default role profiles: importance (0-1) of skills for common target roles, used when no job
# description is selected (and merged with it when one is).
ROLE_PROFILES = {
    'software engineer': {'dsa': 0.9, 'arrays': 0.9, 'strings': 0.8, 'hashing': 0.9, 'two-pointers': 0.7,
                          'sliding-window': 0.6, 'binary-search': 0.7, 'linked-lists': 0.6, 'stacks': 0.6,
                          'queues': 0.5, 'recursion': 0.7, 'trees': 0.8, 'graphs': 0.7, 'heaps': 0.5,
                          'dynamic-programming': 0.7, 'greedy': 0.5, 'oop': 0.8, 'dbms': 0.6, 'sql': 0.6,
                          'operating-systems': 0.6, 'computer-networks': 0.5, 'system-design': 0.4},
    'backend developer': {'arrays': 0.7, 'hashing': 0.8, 'strings': 0.6, 'trees': 0.5, 'graphs': 0.4, 'oop': 0.8,
                          'dbms': 0.9, 'sql': 0.9, 'rest-apis': 0.9, 'computer-networks': 0.7,
                          'operating-systems': 0.6, 'system-design': 0.7, 'docker': 0.5, 'git': 0.5},
    'frontend developer': {'html': 0.9, 'css': 0.9, 'javascript': 0.9, 'react': 0.9, 'typescript': 0.6,
                           'rest-apis': 0.7, 'arrays': 0.6, 'strings': 0.6, 'hashing': 0.5, 'git': 0.5},
    'full stack developer': {'html': 0.7, 'css': 0.7, 'javascript': 0.9, 'react': 0.8, 'nodejs': 0.8,
                             'rest-apis': 0.9, 'dbms': 0.8, 'sql': 0.8, 'arrays': 0.6, 'hashing': 0.6,
                             'oop': 0.6, 'system-design': 0.5, 'git': 0.5},
    'data scientist': {'python': 0.9, 'machine-learning': 0.9, 'sql': 0.8, 'dbms': 0.5, 'arrays': 0.5,
                       'hashing': 0.4, 'dynamic-programming': 0.3},
}
ROLE_ALIASES = {
    'sde': 'software engineer', 'software development engineer': 'software engineer',
    'software developer': 'software engineer', 'swe': 'software engineer', 'backend engineer': 'backend developer',
    'frontend engineer': 'frontend developer', 'full stack engineer': 'full stack developer',
    'fullstack developer': 'full stack developer', 'data analyst': 'data scientist',
    'ml engineer': 'data scientist', 'machine learning engineer': 'data scientist',
}
