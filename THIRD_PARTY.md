# Third-party software

The authored project is MIT-licensed. Third-party components retain their own licenses.
All selected application components are open source. No paid API/subscription is required.
This inventory records installed package metadata; review upstream licenses for redistribution.

## Python packages

| Package | Version | License metadata |
|---|---|---|
| asgiref | 3.12.1 | BSD-3-Clause |
| cffi | 2.1.1 | MIT-0 |
| cryptography | 50.0.1 | Apache-2.0 OR BSD-3-Clause |
| Django | 5.2.17 | BSD-3-Clause |
| et_xmlfile | 2.0.0 | MIT |
| gunicorn | 26.2.0 | MIT |
| openpyxl | 3.1.5 | MIT |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pillow | 12.3.0 | MIT-CMU |
| psycopg | 3.3.5 | LGPL-3.0-only |
| psycopg-binary | 3.3.5 | LGPL-3.0-only |
| pycparser | 3.0 | BSD-3-Clause |
| PyOTP | 2.10.0 | MIT |
| pypdfium2 | 5.13.0 | BSD-3-Clause, Apache-2.0, dependency licenses |
| pytesseract | 0.3.13 | Apache License 2.0 |
| sqlparse | 0.6.0 | License :: OSI Approved :: BSD License |
| typing_extensions | 4.16.0 | PSF-2.0 |
| whitenoise | 6.12.0 | MIT |

## Frontend runtime

- react 19.3.0: MIT
- react-dom 19.3.0: MIT
- scheduler 0.28.0: MIT

## System software and development tools

- Tesseract OCR and language data: Apache-2.0. https://github.com/tesseract-ocr/tesseract
- PostgreSQL: PostgreSQL License. https://www.postgresql.org/about/licence/
- Caddy: Apache-2.0. https://github.com/caddyserver/caddy
- Docker Engine/Moby: Apache-2.0; Compose: Apache-2.0. No Docker Desktop dependency.
- age: BSD-3-Clause. https://github.com/FiloSottile/age
- React/Vite: MIT; TypeScript: Apache-2.0.
- Python: PSF license; Ubuntu/Debian package collections have individual free-software licenses.
- PDFium embedded in pypdfium2: BSD-style licenses and third-party notices provided by the upstream wheel.
- OpenSSL: Apache-2.0; system dependencies retain their distribution copyright notices.

Upstream wheels/system packages are downloaded by setup with their license files. Bundled frontend runtime licenses are in licenses/. Initial installation requires internet; operation does not call cloud OCR.
