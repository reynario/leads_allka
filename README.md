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
  main.py            # FastAPI + lifespan que sobe o scheduler
  config.py          # pydantic-settings
  database.py        # engine async + SessionLocal
  scheduler.py       # APScheduler: cron 08:00
  models/            # Lead, LeadAnalysis (schema "leads")
  repositories/      # lead_repository (CRUD)
  services/          # redrive, website, instagram, ads, ai, bitrix
  workers/           # lead_worker (orquestra um lead)
  routers/           # health + leads (listar / run-now / retry)
alembic/             # migrações (cria schema "leads")
tests/               # smoke
Dockerfile           # multi-stage
docker-compose.yml   # labels Traefik
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
| `ADMIN_TOKEN` | Você define. Protege `POST /leads/run-now` e `POST /leads/{id}/retry`. |
| `APP_DOMAIN` | Domínio que o Traefik vai rotear. Ex.: `leads.allka.com.br`. |

Flags de operação importantes:

- `SCHEDULER_ENABLED=true` — desliga o cron sem precisar mexer no código.
- `PLAYWRIGHT_ENABLED=false` — quando `true`, sites com pouco HTML são re-analisados com Chromium.
- `GOOGLE_ADS_ENABLED=false` — anúncios Google ficam como stub até definir provedor.

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

- `GET /` — info do serviço
- `GET /health` — checa banco
- `GET /leads?status=&limit=&offset=` — lista leads
- `GET /leads/{id}` — detalhe + análise
- `POST /leads/run-now` — dispara o job agora (header `X-Admin-Token`)
- `POST /leads/{id}/retry` — reseta lead para `pending` (header `X-Admin-Token`)

## Trigger manual

```bash
curl -X POST https://leads.allka.com.br/leads/run-now \
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
- Dashboard web
