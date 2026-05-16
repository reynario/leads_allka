# Sistema de Leads Allka

Robô diário que enriquece leads do **Redrive** com análise de site, Instagram (Apify),
anúncios Meta/Google e geração de briefing comercial por IA, criando o lead no
**Bitrix24** automaticamente. Roda em VPS atrás do **Traefik**.

---

## Fluxo

```
08:00 (America/Sao_Paulo)
  ↓
Busca 20 leads no Redrive
  ↓
Salva no banco como pending
  ↓
Para cada lead:
  → Analisa site (HTML: Meta Pixel, GTag, GTM, WhatsApp, formulário, links)
  → Analisa Instagram via Apify
  → Consulta anúncios Meta (Ad Library) + Google (stub)
  → Gera análise IA (OpenAI, JSON mode)
  → Cria lead no Bitrix24 com campos UF_CRM_*
  → Marca como sent_to_bitrix
```

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2 async · Alembic · APScheduler · httpx · BeautifulSoup4 ·
Playwright (opcional) · OpenAI · Apify · Bitrix24 REST · Docker · Traefik · Postgres (Supabase)

## Estrutura

```
app/
  main.py            # FastAPI + lifespan (scheduler + bootstrap admin)
  config.py          # pydantic-settings
  database.py        # engine async + SessionLocal
  scheduler.py       # APScheduler: cron 08:00
  bootstrap.py       # cria admin do .env no primeiro start
  deps.py            # dependências (sessão, current_user, admin)
  templating.py      # Jinja2Templates + filters
  models/            # Lead, LeadAnalysis, User (schema "leads")
  repositories/      # lead_repository (CRUD + métricas)
  services/          # redrive, website, instagram, ads, ai, bitrix, auth_service
  workers/           # lead_worker (orquestra um lead)
  routers/
    health.py        # /, /health
    auth.py          # /login, /logout
    ui.py            # /dashboard, /leads, /leads/{id}, /run-now, /leads/{id}/retry
    users.py         # /users (CRUD — apenas admin)
    api_leads.py     # /api/leads/* (REST programatica, header X-Admin-Token)
  templates/         # Jinja2: base, login, dashboard, leads_list, lead_detail, users
alembic/             # migrações (schema "leads": leads, lead_analysis, users)
tests/               # smoke
Dockerfile           # multi-stage
docker-compose.yml   # labels Traefik (Swarm/Portainer)
entrypoint.sh        # `alembic upgrade head` + uvicorn
```

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha. Mínimo para subir:

| Variável | Como obter |
|---|---|
| `DATABASE_URL` | Supabase → Project Settings → Database → **Connection string (URI)**. Substitua `postgres://` por `postgresql+asyncpg://`. |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `META_ACCESS_TOKEN` | https://developers.facebook.com → seu app → Access Token (com permissão `ads_read`). |
| `APIFY_TOKEN` | Apify Console → Settings → Integrations → API tokens. |
| `REDRIVE_API_TOKEN` + `REDRIVE_BASE_URL` | Painel Redrive (quando o token for emitido). |
| `BITRIX_WEBHOOK_URL` | Bitrix24 → Aplicativos → Webhooks → Webhook de entrada → URL completa (sem barra no fim). |
| `ADMIN_TOKEN` | Você define. Protege a **API REST** (`POST /api/leads/run-now` etc.) via header. |
| `SESSION_SECRET` | Chave para assinar o cookie de login. Gere com `openssl rand -hex 32`. |
| `BOOTSTRAP_ADMIN_EMAIL` + `BOOTSTRAP_ADMIN_PASSWORD` | Admin criado no **primeiro start** (só se a tabela `users` estiver vazia). Depois você gerencia pela UI. |
| `APP_DOMAIN` | Domínio que o Traefik vai rotear. Ex.: `allkaleads.rndigitalmidia.com.br`. |

Flags de operação importantes:

- `SCHEDULER_ENABLED=true` — desliga o cron sem precisar mexer no código.
- `PLAYWRIGHT_ENABLED=false` — quando `true`, sites com pouco HTML são re-analisados com Chromium.
- `GOOGLE_ADS_ENABLED=false` — anúncios Google ficam como stub até definir provedor.

## Interface web (login + dashboard)

Acesse `https://<APP_DOMAIN>/` e você é redirecionado para `/login`. Use o e-mail e senha
definidos em `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` no primeiro acesso.

Páginas:

- `/dashboard` — métricas (pendentes, processados, taxa de sucesso 7d, score médio, próxima execução)
- `/leads` — listagem com filtros por status, botão de execução manual
- `/leads/{id}` — detalhe completo (análise de site, Instagram, anúncios, IA, payload bruto)
- `/users` — CRUD de usuários (só administradores)

A interface usa Jinja2 + Pico.css (sem build de frontend). Cookies de sessão são assinados
com `SESSION_SECRET`, válidos por `SESSION_MAX_AGE_SECONDS` (padrão 8h), httpOnly + SameSite=Lax.

## Rodar local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env       # preencher
alembic upgrade head
uvicorn app.main:app --reload
```

Sanity: `curl http://localhost:8000/health` deve retornar `{"status":"ok","database":"ok"}`.

## Rodar produção (VPS com Portainer + Traefik Swarm)

A imagem é publicada automaticamente em `ghcr.io/reynario/leads_allka:latest`
sempre que há push na branch `main` (veja `.github/workflows/build.yml`).

Pré-requisitos na VPS:
- Docker Swarm inicializado (`docker swarm init` se ainda não estiver).
- Traefik rodando em modo Swarm com `certresolver: letsencryptresolver`.
- Rede overlay externa **`RNNet`** já criada.
- DNS de `allkaleads.rndigitalmidia.com.br` apontando para a VPS.

**Deploy via Portainer (Stacks):**

1. **Portainer → Stacks → Add stack**.
2. Nome: `leads-allka`.
3. Build method: **Web editor** (cole o conteúdo do `docker-compose.yml` do repo)
   ou **Repository** apontando para `https://github.com/reynario/leads_allka` no path `docker-compose.yml`.
4. Em **Environment variables** (no próprio Portainer), adicione cada variável do `.env`
   (`DATABASE_URL`, `OPENAI_API_KEY`, `META_ACCESS_TOKEN`, `APIFY_TOKEN`, `BITRIX_WEBHOOK_URL`,
   `ADMIN_TOKEN`, etc.). O `docker-compose.yml` usa `${VAR}` para puxá-las.
5. **Deploy the stack**.

Na primeira execução, o `entrypoint.sh` roda `alembic upgrade head` e cria o
schema `leads` no Supabase (sem mexer no `public` que pertence ao `ia_allka`).

**Atualizar a imagem depois de novos commits:** force pull no Portainer
(Stack → Editor → "Re-pull image and redeploy") ou `docker service update --image ghcr.io/reynario/leads_allka:latest leads-allka_leads-allka`.

## Endpoints

**UI (sessão via cookie — login web):**

- `GET /` → redireciona para `/dashboard`
- `GET /health` — checa banco
- `GET /login` + `POST /login` — autenticação
- `POST /logout`
- `GET /dashboard` — métricas
- `GET /leads`, `GET /leads/{id}` — listagem e detalhe
- `POST /run-now` — dispara o job (form)
- `POST /leads/{id}/retry` — reset de um lead
- `GET /users`, `GET /users/new`, `GET /users/{id}/edit` — gestão (admin)

**API REST programática (header `X-Admin-Token`):**

- `GET /api/leads?status=&limit=&offset=`
- `GET /api/leads/{id}`
- `POST /api/leads/run-now`
- `POST /api/leads/{id}/retry`

## Trigger manual via API

```bash
curl -X POST https://allkaleads.rndigitalmidia.com.br/api/leads/run-now \
     -H "X-Admin-Token: <ADMIN_TOKEN>"
```

## Bitrix24 — campos UF_CRM_*

Antes da primeira execução, crie em **Configurações → CRM → Campos personalizados → Lead**:

| Campo | Tipo |
|---|---|
| `UF_CRM_ANALISE_IA` | Texto longo |
| `UF_CRM_SCORE_IA` | Número |
| `UF_CRM_META_PIXEL` | Texto |
| `UF_CRM_GOOGLE_TAG` | Texto |
| `UF_CRM_INSTAGRAM_STATUS` | Texto |
| `UF_CRM_META_ADS` | Texto |
| `UF_CRM_GOOGLE_ADS` | Texto |

Mapping fica em [app/services/bitrix.py](app/services/bitrix.py) (`UF_FIELDS`) caso precise renomear.

## Testes

```bash
pytest -q
```

Smoke tests não exigem banco — só checam que o app sobe e o OpenAPI carrega.

## Próximos passos (v2)

- Celery + Redis para escala horizontal
- Screenshots reais de anúncios via Playwright
- Provedor real de Google Ads (Transparency Center / SerpAPI)
- Alertas Slack/Telegram em falha do job
- Gráficos no dashboard (Chart.js / Plotly)
- Reset de senha por e-mail
