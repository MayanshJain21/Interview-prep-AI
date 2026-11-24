// Sorts resume skills into readable sections. Anything not recognised goes under "Others".

const GROUPS = [
    {
        name: 'Languages',
        names: ['python', 'java', 'c', 'c++', 'c#', 'javascript', 'typescript', 'go', 'golang', 'rust', 'kotlin', 'swift',
            'ruby', 'php', 'scala', 'r', 'matlab', 'sql', 'html', 'html5', 'css', 'css3', 'bash', 'shell', 'shell scripting',
            'dart', 'perl', 'haskell', 'objective-c', 'solidity', 'assembly', 'verilog', 'vhdl'],
    },
    {
        name: 'Frameworks & libraries',
        names: ['django', 'django rest framework', 'drf', 'flask', 'fastapi', 'spring', 'spring boot', 'react', 'react.js',
            'reactjs', 'next.js', 'nextjs', 'angular', 'vue', 'vue.js', 'node.js', 'nodejs', 'node', 'express', 'express.js',
            'tensorflow', 'pytorch', 'scikit-learn', 'sklearn', 'pandas', 'numpy', 'keras', 'matplotlib', 'seaborn',
            'bootstrap', 'tailwind', 'tailwind css', 'jquery', 'redux', 'hibernate', '.net', 'asp.net', 'laravel', 'rails',
            'ruby on rails', 'flutter', 'react native', 'opencv', 'celery', 'langchain', 'hugging face', 'transformers',
            'streamlit', 'junit', 'pytest', 'jest', 'selenium', 'three.js', 'socket.io', 'graphql',
            'sentence transformers', 'litellm', 'faster whisper', 'whisper', 'piper', 'piper tts', 'llamaindex',
            'llama index', 'langgraph', 'crewai', 'autogen', 'haystack', 'openai api', 'gemini api', 'groq',
            'hugging face transformers', 'huggingface', 'spacy', 'nltk', 'xgboost', 'lightgbm', 'gradio',
            'context api', 'react context api', 'react hooks', 'react router', 'redux toolkit', 'zustand', 'axios',
            'mongoose', 'prisma', 'sequelize', 'sqlalchemy', 'pydantic', 'material ui', 'mui', 'shadcn', 'framer motion'],
    },
    {
        name: 'Databases',
        names: ['postgresql', 'postgres', 'mysql', 'mongodb', 'redis', 'sqlite', 'oracle', 'cassandra', 'dynamodb',
            'firebase', 'firestore', 'elasticsearch', 'mariadb', 'neo4j', 'sql server', 'ms sql', 'supabase', 'chromadb',
            'pinecone', 'snowflake', 'bigquery', 'qdrant', 'weaviate', 'milvus', 'faiss', 'pgvector',
            'vector database', 'vector databases'],
    },
    {
        name: 'Dev tools & cloud',
        names: ['git', 'github', 'gitlab', 'bitbucket', 'github actions', 'docker', 'kubernetes', 'k8s', 'linux', 'unix',
            'aws', 'azure', 'gcp', 'google cloud', 'jenkins', 'ci/cd', 'terraform', 'postman', 'jira', 'vs code', 'vscode',
            'nginx', 'heroku', 'vercel', 'netlify', 'ansible', 'maven', 'gradle', 'npm', 'yarn', 'webpack', 'vite',
            'figma', 'jupyter', 'anaconda', 'excel', 'power bi', 'tableau', 'apache kafka', 'kafka', 'rabbitmq', 'airflow',
            'spark', 'hadoop', 'firebase hosting', 'ollama', 'vllm', 'mlflow', 'weights & biases', 'wandb',
            'langsmith', 'dvc', 'colab', 'google colab', 'kaggle', 'hugging face hub', 'render', 'railway', 'supabase cli'],
        prefixes: ['aws ', 'azure ', 'gcp ', 'google cloud '],
    },
    {
        name: 'Concepts',
        names: ['rest apis', 'rest api', 'rest', 'restful apis', 'microservices', 'oop', 'oops', 'object-oriented programming',
            'operating system', 'problem solving', 'competitive programming',
            'dsa', 'data structures', 'algorithms', 'data structures and algorithms', 'system design', 'dbms',
            'operating systems', 'computer networks', 'machine learning', 'deep learning', 'nlp',
            'natural language processing', 'computer vision', 'agile', 'scrum', 'multithreading', 'concurrency',
            'caching', 'containerization', 'design patterns', 'unit testing', 'integration testing', 'testing', 'tdd',
            'ci/cd pipelines', 'web development', 'api development', 'data analysis', 'data visualization',
            'statistics', 'cloud computing', 'distributed systems', 'networking', 'sockets', 'authentication', 'jwt',
            'rag', 'retrieval augmented generation', 'hybrid retrieval', 'semantic search', 'vector search',
            'embeddings', 'llm', 'llms', 'large language models', 'generative ai', 'gen ai', 'genai',
            'prompt engineering', 'fine tuning', 'ai agents', 'agents', 'agentic ai', 'speech to text', 'text to speech',
            'tts', 'stt', 'asr', 'websockets', 'websocket', 'oauth', 'responsive design', 'state management',
            'server side rendering', 'ssr', 'mlops', 'feature engineering', 'model deployment', 'transformers'],
        contains: ['testing', 'learning', 'hashing', 'design', 'analysis', 'similarity', 'tf-idf', 'log', 'retrieval',
            'search', 'generation', 'embedding', 'prompt', 'websocket', 'recognition', 'classification'],
    },
];

const key = (s) => String(s).trim().toLowerCase();

// Spellings resumes use for the same thing.
const ALIASES = {
    js: 'javascript', es6: 'javascript', ecmascript: 'javascript', ts: 'typescript', py: 'python',
    golang: 'go', 'go lang': 'go', cpp: 'c++', 'c plus plus': 'c++', 'c sharp': 'c#', 'react js': 'react', 'node js': 'node.js',
    'next js': 'next.js', 'vue js': 'vue', 'express js': 'express', 'mongo db': 'mongodb', 'mongo': 'mongodb',
    'postgre sql': 'postgresql', 'ms excel': 'excel', 'microsoft excel': 'excel', 'amazon web services': 'aws',
    'google cloud platform': 'gcp', 'github actions ci': 'github actions', 'data structures & algorithms': 'dsa',
    'data structures and algorithms (dsa)': 'dsa', 'object oriented programming': 'oop', 'c programming': 'c',
    'c language': 'c',
};

// The ways one skill can be written: "JavaScript (ES6+)" -> "javascript"; "Python 3.11" -> "python";
// "C/C++" -> "c" and "c++"; "ReactJS" -> "react".
function variants(skill) {
    const base = key(skill).replace(/\([^)]*\)/g, ' ').replace(/\s+/g, ' ').trim();
    const parts = [base, ...base.split(/\s*(?:\/|,|&|\+(?!\+)|\band\b)\s*/)].map((p) => p.trim()).filter(Boolean);
    const out = new Set();
    for (const p of parts) {
        const noVersion = p.replace(/\s*v?\d+(\.\d+)*\+?$/, '').trim();
        for (const v of [p, noVersion, noVersion.replace(/-/g, ' '), noVersion.replace(/\.?js$/, '').trim(),
            noVersion.replace(/(\w)js$/, '$1.js')]) {
            if (v) out.add(ALIASES[v] || v);
        }
    }
    return [...out];
}

function groupOf(skill) {
    const forms = variants(skill);
    for (const g of GROUPS) {
        if (forms.some((k) => g.names.includes(k) || (g.prefixes || []).some((p) => k.startsWith(p)))) return g.name;
    }
    // A known product name followed by more words: "MongoDB Atlas", "Docker Compose", "AWS Lambda".
    // Very short names (c, r, go) are skipped here because they start too many unrelated phrases.
    for (const g of GROUPS) {
        if (forms.some((k) => g.names.some((n) => n.length >= 3 && k.startsWith(`${n} `)))) return g.name;
    }
    for (const g of GROUPS) {
        if (forms.some((k) => (g.contains || []).some((c) => k.includes(c)))) return g.name;
    }
    return 'Others';
}

// Returns [{ name, skills }] in a fixed order, leaving out empty sections.
export function groupSkills(skills) {
    const order = [...GROUPS.map((g) => g.name), 'Others'];
    const buckets = Object.fromEntries(order.map((n) => [n, []]));
    const seen = new Set();
    for (const s of skills || []) {
        if (!s || seen.has(key(s))) continue;
        seen.add(key(s));
        buckets[groupOf(s)].push(s);
    }
    return order.map((name) => ({ name, skills: buckets[name] })).filter((g) => g.skills.length);
}
