// Languages for the coding round. The ids match the backend (coding/languages.py) and Monaco's language ids.
export const LANGUAGES = {
    python: { label: 'Python', badge: 'Py', className: 'bg-[#3776ab] text-[#ffd43b]' },
    javascript: { label: 'JavaScript', badge: 'JS', className: 'bg-[#f7df1e] text-black' },
    cpp: { label: 'C++', badge: 'C++', className: 'bg-[#00599c] text-white' },
    c: { label: 'C', badge: 'C', className: 'bg-[#a8b9cc] text-[#283593]' },
    java: { label: 'Java', badge: 'Jv', className: 'bg-[#e76f00] text-white' },
    go: { label: 'Go', badge: 'Go', className: 'bg-[#00add8] text-white' },
};

export const LANGUAGE_IDS = Object.keys(LANGUAGES);
export const languageLabel = (lang) => LANGUAGES[lang]?.label || lang;
