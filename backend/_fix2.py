c = open('backend/app/api/chat.py', 'r', encoding='utf-8').read()
old = 'return best_part\n\nTOOLS = ['
new = 'return best_part\n\n\ndef _continue_across_chunks(qa: str, all_contents: list) -> str:\n'
new += '    """若 QA 被截断（结尾无句号），从其他块续接直到完整"""\n'
new += '    import re\n'
new += '    if re.search(r\'[。！？]$\', qa.strip()):\n'
new += '        return qa\n'
new += '    for other in all_contents:\n'
new += '        if other is None:\n'
new += '            continue\n'
new += "        next_title = re.search(r'\\*\\*\\d+', other)\n"
new += '        continuation = other[:next_title.start()] if next_title else other[:300]\n'
new += '        if continuation.strip():\n'
new += '            qa += continuation\n'
new += "        if re.search(r'[。！？]', continuation[-100:]):\n"
new += '            break\n'
new += '    return qa\n'
new += '\n\nTOOLS = ['
c = c.replace(old, new)
open('backend/app/api/chat.py', 'w', encoding='utf-8').write(c)
print('Done')
