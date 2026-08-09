#!/usr/bin/env python3
"""index.html(아티팩트용 콘텐츠)을 docs/index.html(완전한 HTML 문서)로 빌드.

아티팩트는 게시 시 doctype/head/body 스켈레톤으로 감싸므로 index.html에는
스켈레톤을 넣지 않는다. GitHub Pages는 파일을 그대로 서빙하므로 여기서
정식 문서 구조(doctype, lang, charset, viewport)를 입힌다.
"""
import os

src = open('index.html', encoding='utf-8').read()

cut = src.index('</style>') + len('</style>')
head_part, body_part = src[:cut], src[cut:]

html = (
    '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
    + head_part
    + '\n</head>\n<body>\n'
    + body_part
    + '\n</body>\n</html>\n'
)

os.makedirs('docs', exist_ok=True)
open('docs/index.html', 'w', encoding='utf-8').write(html)
print('built docs/index.html:', len(html), 'bytes')
