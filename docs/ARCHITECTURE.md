# Arquitetura — LabGateway

Aluno (browser) → Flask (autenticação, submissão) → SQLite + uploads

Professor (browser) → Flask (solicita execução) → SQLite (fila)

Worker separado → Docker (rede desativada, usuário não-root, limites) → saída limitada → SQLite

## Limites de confiança
- O processo Flask **não** deve ter acesso ao Docker socket.
- O worker só deve acessar diretórios validados.
- Código de alunos é não confiável, mesmo após a validação de ZIP.
- Containers Linux não constituem sandbox de alta segurança.
- A Raspberry não deve expor SSH, Docker daemon nem controles administrativos na internet.
- Starlink não é necessária para testes locais; ngrok fica para a etapa de homologação.

## Premissas
Python sem dependências de terceiros, `main.py` na raiz, sem rede nem GPIO. Uma execução por vez, solicitada pelo professor. Fazer backup do projeto do forno antes de implantar.
